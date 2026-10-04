import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import csv

import click
import yaml
from datetime import datetime, date
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel
from rich import print as rprint

import httpx

from omnis.client import (
    OmnisClient,
    UserInfo,
    Loan,
    BookDetails,
    SearchResult,
    Fine,
    RequestItem,
    HoldableItem,
    PickupLocation,
)
from omnis.tenants import KNOWN_TENANTS, MOCK_TENANT
from omnis.branches import fetch_branches, BranchInfo

CONFIG_DIR = Path.home() / ".config" / "omnis-py"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# omnis-mock's fixed demo account — publicly documented as not-secret in its own SPEC.md,
# safe to keep in source.
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"

console = Console()

# Seconds to wait before each re-check of myaccount/requests after --place-hold.
HOLD_CONFIRM_DELAYS = (1.0, 2.0, 3.0, 5.0)


def parse_date(date_str: str) -> Optional[date]:
    """Try to parse date from common formats."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def format_due_date(date_str: str) -> str:
    """Format due date with color and relative time (e.g. '2023-10-01 (za 2 dni)')."""
    d = parse_date(date_str)
    if not d:
        return date_str

    today = date.today()
    delta = (d - today).days

    # Determine relative text
    if delta < 0:
        relative = f"{abs(delta)} dni po terminie"
    elif delta == 0:
        relative = "dziś"
    elif delta == 1:
        relative = "jutro"
    else:
        relative = f"za {delta} dni"

    full_text = f"{d.strftime('%Y.%m.%d')} ({relative})"

    # Determine color
    if delta <= 0:
        return f"[bold red]{full_text}[/bold red]"
    elif delta <= 7:
        return f"[bold yellow]{full_text}[/bold yellow]"
    else:
        return f"[green]{full_text}[/green]"


def _redact_account(account: Dict[str, Any]) -> Dict[str, Any]:
    """Strip the plaintext password before an account dict enters any result destined for --format json/csv."""
    return {k: v for k, v in account.items() if k != "password"}


def load_config() -> List[Dict[str, Any]]:
    if not CONFIG_FILE.exists():
        return []
    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f)
            return data.get("accounts", []) if data else []
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {e}")
        return []


def save_config(accounts: List[Dict[str, Any]]):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump({"accounts": accounts}, f)
    console.print(f"[green]Configuration saved to {CONFIG_FILE}[/green]")


def add_account_wizard() -> Dict[str, Any]:
    rprint(Panel.fit("Add New Library Account", style="bold blue"))

    # Select Tenant
    rprint("\n[bold]Select Library:[/bold]")
    for idx, tenant in enumerate(KNOWN_TENANTS, 1):
        rprint(f"{idx}. {tenant['name']}")

    choice = IntPrompt.ask("Choose option", choices=[str(i) for i in range(1, len(KNOWN_TENANTS) + 1)])
    selected_tenant = KNOWN_TENANTS[choice - 1]

    if selected_tenant["name"] == "Custom / Własna...":
        base_url = Prompt.ask("Enter Base URL (e.g. https://omnis-br.primo.exlibrisgroup.com)")
        institution = Prompt.ask("Enter Institution Code (e.g. 48OMNIS_BRP)")
        view = Prompt.ask("Enter View ID (e.g. 48OMNIS_BRP:BRACZ)")
        tenant_name = Prompt.ask("Enter a friendly name for this library")
    else:
        base_url = selected_tenant["base_url"]
        institution = selected_tenant["institution"]
        view = selected_tenant["view"]
        tenant_name = selected_tenant["name"]
        rprint(f"[dim]Selected: {tenant_name}[/dim]")

    username = Prompt.ask("Username (Card Number)")
    password = Prompt.ask("Password", password=True)

    account: Dict[str, Any] = {
        "username": username,
        "password": password,
        "base_url": base_url,
        "institution": institution,
        "view": view,
        "tenant_name": tenant_name,
    }
    if selected_tenant.get("is_demo"):
        account["is_demo"] = True
    if "default_timeout" in selected_tenant:
        account["timeout"] = selected_tenant["default_timeout"]
    return account


def _enabled_accounts(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Accounts with enabled != False. A missing key counts as enabled, so configs
    written before this field existed keep working unchanged."""
    return [a for a in accounts if a.get("enabled", True)]


def _set_account_enabled(accounts: List[Dict[str, Any]], index: int, enabled: bool) -> None:
    """index is 1-based, matching the numbering shown by --list-accounts/add_account_wizard."""
    account = accounts[index - 1]
    account["enabled"] = enabled
    if enabled:
        # Manually re-enabling clears the demo-mode marker so a later --exit-demo won't
        # also try to toggle an account the user already restored themselves.
        account.pop("disabled_by_demo", None)


def _set_account_timeout(accounts: List[Dict[str, Any]], index: int, seconds: float) -> None:
    accounts[index - 1]["timeout"] = seconds


def _make_demo_account() -> Dict[str, Any]:
    return {
        "username": DEMO_USERNAME,
        "password": DEMO_PASSWORD,
        "base_url": MOCK_TENANT["base_url"],
        "institution": MOCK_TENANT["institution"],
        "view": MOCK_TENANT["view"],
        "tenant_name": MOCK_TENANT["name"],
        "is_demo": True,
        "enabled": True,
        "timeout": MOCK_TENANT["default_timeout"],
    }


def _apply_demo_mode(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Disable every currently-enabled non-demo account (tagged disabled_by_demo=True so
    _exit_demo_mode knows what to restore), then ensure exactly one enabled demo account
    exists — reusing an existing demo account if present (refreshing its credentials/tenant
    fields in case they were ever hand-edited), otherwise appending a fresh one. Idempotent:
    calling this twice in a row does not create a second demo account."""
    demo_account = None
    for account in accounts:
        if account.get("is_demo"):
            demo_account = account
            continue
        if account.get("enabled", True):
            account["enabled"] = False
            account["disabled_by_demo"] = True

    if demo_account is not None:
        demo_account.update(_make_demo_account())
    else:
        accounts.append(_make_demo_account())

    return accounts


def _exit_demo_mode(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Disable every enabled demo account, and re-enable (clearing the marker) every account
    that _apply_demo_mode had disabled. Accounts the user had disabled before --demo, unrelated
    to it, are deliberately left disabled."""
    for account in accounts:
        if account.get("is_demo") and account.get("enabled", True):
            account["enabled"] = False
        if account.pop("disabled_by_demo", False):
            account["enabled"] = True
    return accounts


def display_accounts_table(accounts: List[Dict[str, Any]]) -> None:
    table = Table(title="Configured Accounts")
    table.add_column("Index", justify="right")
    table.add_column("Library", style="magenta")
    table.add_column("Username", style="cyan")
    table.add_column("Enabled", justify="center")
    table.add_column("Timeout (s)", justify="right")

    if not accounts:
        console.print("[italic]No accounts configured. Add one with --add.[/italic]")
        return

    for idx, account in enumerate(accounts, 1):
        name = account.get("tenant_name", "Unknown")
        if account.get("is_demo"):
            name = f"{name} [dim](demo)[/dim]"
        enabled_display = "[green]✓[/green]" if account.get("enabled", True) else "[red]✗[/red]"
        table.add_row(
            str(idx),
            name,
            account.get("username", ""),
            enabled_display,
            str(account.get("timeout", 30.0)),
        )

    console.print(table)


async def fetch_account_data(account: Dict[str, Any], details: bool = False, history: bool = False) -> Dict[str, Any]:
    client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])
        user_info = await client.get_user_info()
        loans = await client.get_loans(loan_type="history" if history else "active")

        loans_with_details: List[Dict[str, Any]] = []
        if details:
            # Fetch details for each loan concurrently
            detail_tasks = [client.get_record_details(loan.mmsid) for loan in loans]
            detailed_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

            for loan, detail_result in zip(loans, detailed_results):
                if isinstance(detail_result, Exception):
                    # Handle cases where detail fetching fails for a specific book
                    console.print(f"[dim red]Could not fetch details for '{loan.title}': {detail_result}[/dim]")
                    loans_with_details.append({"loan": loan, "details": None})
                else:
                    loans_with_details.append({"loan": loan, "details": detail_result})
        else:
            # If not fetching details, just wrap the loan object
            loans_with_details = [{"loan": loan, "details": None} for loan in loans]

        return {
            "account": _redact_account(account),
            "user_info": user_info,
            "loans": loans_with_details,
            "error": None,
        }
    except Exception as e:
        return {"account": _redact_account(account), "error": str(e)}
    finally:
        await client.close()


def display_results_table(
    results: List[Dict[str, Any]], details: bool = False, history: bool = False, verbose: bool = False
):
    # 1. User Summary Table
    summary_table = Table(title="Users & Status")
    summary_table.add_column("User", style="cyan")
    summary_table.add_column("Library", style="magenta")
    summary_table.add_column("Loans" if history else "Active Loans", justify="center", style="green")
    summary_table.add_column("Fines", justify="right", style="red")

    all_loans_by_location: Dict[str, List[Dict[str, Any]]] = {}

    for res in results:
        account = res["account"]
        if res.get("error"):
            summary_table.add_row(
                account["username"], account.get("tenant_name", "Unknown"), "[red]Error[/red]", "[red]N/A[/red]"
            )
            continue

        user_info: UserInfo = res["user_info"]
        loans: List[Dict[str, Any]] = res["loans"]

        fines_display = f"{user_info.fines_amount:.2f} {user_info.fines_currency}"
        if user_info.fines_amount > 0:
            fines_display = f"[bold red]{fines_display}[/bold red]"
        else:
            fines_display = f"[dim]{fines_display}[/dim]"

        summary_table.add_row(
            f"{user_info.display_name} ({res['account']['username']})",
            account.get("tenant_name", "Unknown"),
            str(len(loans) if history else user_info.loans_count),
            fines_display,
        )

        # Aggregate loans by location
        for single_loan_item in loans:
            loan: Loan = single_loan_item["loan"]
            # Create a unique location key (Library + Branch)
            location_key = f"{loan.library_name} - {loan.location_name}"
            if loan.sub_location_name:
                location_key += f" ({loan.sub_location_name})"

            if location_key not in all_loans_by_location:
                all_loans_by_location[location_key] = []

            all_loans_by_location[location_key].append(
                {"loan": loan, "details": single_loan_item["details"], "owner": user_info.display_name}
            )

    console.print(summary_table)
    console.print()

    # 2. Books by Location Table
    if not all_loans_by_location:
        console.print(f"[italic]No {'historical' if history else 'active'} loans found.[/italic]")
        return

    for location, items in sorted(all_loans_by_location.items()):
        loc_table = Table(title=f"📍 {location}", show_header=True, header_style="bold")
        loc_table.add_column("Due Date" if history else "Return Date")
        if verbose:
            loc_table.add_column("Loan Date", style="dim")
        loc_table.add_column("Author", style="blue")
        loc_table.add_column("Title", style="white")
        loc_table.add_column("Borrowed By", style="cyan")
        loc_table.add_column("Status", style="dim")
        if verbose:
            loc_table.add_column("Renew", justify="center")
        if details:
            loc_table.add_column("Details", style="dim")

        # Sort by due date
        items.sort(key=lambda x: x["loan"].due_date)

        for item in items:
            current_loan: Loan = item["loan"]
            book_details: Optional[BookDetails] = item["details"]
            owner = item["owner"]

            date_display = current_loan.due_date
            if not history:
                date_display = format_due_date(current_loan.due_date)
            else:
                # For history, just show the date nicely formatted if possible, without relative coloring
                d = parse_date(current_loan.due_date)
                if d:
                    date_display = d.strftime("%Y.%m.%d")

            row_data = [
                date_display,
            ]

            if verbose:
                ld = parse_date(current_loan.loan_date)
                row_data.append(ld.strftime("%Y.%m.%d") if ld else current_loan.loan_date)

            row_data.extend(
                [
                    current_loan.author or "",
                    current_loan.title,
                    owner,
                    current_loan.status,
                ]
            )

            if verbose:
                row_data.append("[green]✓[/green]" if current_loan.renewable else "[red]✗[/red]")

            if details:
                if book_details:
                    details_str = f"ISBN: {', '.join(book_details.isbns)}\n"
                    details_str += f"Publisher: {book_details.publisher}\n"
                    details_str += f"Cover: {book_details.cover_url}"
                    row_data.append(details_str)
                else:
                    row_data.append("[dim]Not available[/dim]")

            loc_table.add_row(*row_data)

        console.print(loc_table)
        console.print()


async def run_search(
    account: Dict[str, Any],
    query: str,
    branch_filter: Optional[str] = None,
    show_address: bool = False,
    verbose: bool = False,
):
    client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])
        with console.status(f"[bold green]Searching for '{query}'...[/bold green]", spinner="dots"):
            results = await client.search_books(query, branch_filter=branch_filter)
        display_search_results(results, query, branch_filter, show_address, verbose)
    except Exception as e:
        console.print(f"[bold red]Search error:[/bold red] {e}")
    finally:
        await client.close()


def display_search_results(
    results: List[SearchResult],
    query: str,
    branch_filter: Optional[str] = None,
    show_address: bool = False,
    verbose: bool = False,
):
    if not results:
        suffix = f" (branch: {branch_filter})" if branch_filter else ""
        console.print(f"[italic]No results for '{query}'{suffix}.[/italic]")
        return

    for result in results:
        title_line = f"📖 {result.title}"
        if result.author:
            title_line += f" — {result.author}"
        series = next((v.series for v in result.versions if v.series), None)
        if series:
            title_line += f"\n[dim]{series}[/dim]"

        table = Table(title=title_line, show_header=True, header_style="bold")
        table.add_column("Edition", style="dim")
        table.add_column("Year", justify="center")
        table.add_column("Branch", style="magenta")
        if show_address:
            table.add_column("Address", style="cyan")
        table.add_column("Status")

        for version in result.versions:
            edition_label = version.edition or "-"
            if version.resource_type and version.resource_type.lower() != "book":
                edition_label = f"{edition_label} [{version.resource_type}]"
            year = version.publication_date or "-"
            # MMS ID shown once per edition: it's what --place-hold takes.
            edition_label_with_id = f"{edition_label}\nMMS {version.mmsid}"

            if not version.branches:
                row = [edition_label_with_id, year, "[dim]no data[/dim]"]
                if show_address:
                    row.append("")
                row.append("")
                table.add_row(*row)
                continue

            for i, branch in enumerate(version.branches):
                if branch.status == "available":
                    status_display = "[green]Available[/green]"
                elif branch.due_date:
                    if branch.overdue:
                        status_display = f"[red]Overdue since {branch.due_date}[/red]"
                    else:
                        status_display = f"[yellow]Borrowed until {branch.due_date}[/yellow]"
                else:
                    status_display = "[yellow]Borrowed[/yellow]"

                row = [edition_label_with_id if i == 0 else edition_label, year, branch.library_name]
                if show_address:
                    address_display = branch.sub_location or "-"
                    if branch.maps_url:
                        address_display = f"{address_display}\n[blue]{branch.maps_url}[/blue]"
                    row.append(address_display)
                row.append(status_display)
                table.add_row(*row)

        console.print(table)

        if verbose:
            for version in result.versions:
                details = []
                if version.isbns:
                    details.append(f"[bold]ISBN:[/bold] {', '.join(version.isbns)}")
                if version.language:
                    details.append(f"[bold]Language:[/bold] {version.language}")
                if version.physical_description:
                    details.append(f"[bold]Physical:[/bold] {version.physical_description}")
                if version.genres:
                    details.append(f"[bold]Genre:[/bold] {', '.join(version.genres)}")
                if version.subjects:
                    details.append(f"[bold]Subject:[/bold] {', '.join(version.subjects)}")
                if version.other_institutions:
                    other_names = ", ".join(inst.name for inst in version.other_institutions)
                    details.append(f"[bold]Also at:[/bold] {other_names}")
                if details:
                    panel_title = version.edition or version.publication_date or version.mmsid
                    console.print(Panel("\n".join(details), title=f"ℹ️  {panel_title}", title_align="left"))

        console.print()


async def fetch_account_fines(account: Dict[str, Any]) -> Dict[str, Any]:
    client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])
        fines = await client.get_fines()
        return {"account": _redact_account(account), "fines": fines, "error": None}
    except Exception as e:
        return {"account": _redact_account(account), "error": str(e)}
    finally:
        await client.close()


async def run_fines(accounts: List[Dict[str, Any]], output_format: str = "table"):
    with console.status("[bold green]Fetching fines...[/bold green]", spinner="dots"):
        results = await asyncio.gather(*(fetch_account_fines(acc) for acc in accounts))

    if output_format == "json":
        display_fines_json(results)
    elif output_format == "csv":
        display_fines_csv(results)
    else:
        display_fines_table(results)


def display_fines_table(results: List[Dict[str, Any]]):
    any_fines = False
    for res in results:
        account = res["account"]
        if res.get("error"):
            console.print(f"[red]Could not fetch fines for {account['username']}: {res['error']}[/red]")
            continue

        fines: List[Fine] = res["fines"]
        if not fines:
            continue
        any_fines = True

        table = Table(
            title=f"💰 {account.get('tenant_name', 'Unknown')} — {account['username']}",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Date")
        table.add_column("Title", style="white")
        table.add_column("Location", style="magenta")
        table.add_column("Amount", justify="right")
        table.add_column("Status", style="dim")
        table.add_column("Description", style="dim")

        for fine in fines:
            d = parse_date(fine.date)
            date_display = d.strftime("%Y.%m.%d") if d else fine.date

            amount_display = f"{fine.amount:.2f} {fine.currency}"
            amount_display = (
                f"[bold red]{amount_display}[/bold red]" if fine.amount > 0 else f"[dim]{amount_display}[/dim]"
            )

            table.add_row(date_display, fine.title, fine.location, amount_display, fine.status, fine.description)

        console.print(table)
        console.print()

    if not any_fines:
        console.print("[italic]No fines found for any configured account.[/italic]")


def display_fines_json(results: List[Dict[str, Any]]):
    print(json.dumps(results, cls=PydanticEncoder, indent=2))


def display_fines_csv(results: List[Dict[str, Any]]):
    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "account_username",
            "fine_id",
            "status",
            "amount",
            "currency",
            "original_amount",
            "date",
            "location",
            "title",
            "type",
            "description",
            "is_alert",
        ]
    )
    for res in results:
        if res.get("error"):
            continue
        for fine in res["fines"]:
            writer.writerow(
                [
                    res["account"]["username"],
                    fine.id,
                    fine.status,
                    fine.amount,
                    fine.currency,
                    fine.original_amount,
                    fine.date,
                    fine.location,
                    fine.title,
                    fine.type,
                    fine.description,
                    fine.is_alert,
                ]
            )


async def fetch_account_requests(account: Dict[str, Any]) -> Dict[str, Any]:
    client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])
        requests = await client.get_requests()
        return {"account": _redact_account(account), "requests": requests, "error": None}
    except Exception as e:
        return {"account": _redact_account(account), "error": str(e)}
    finally:
        await client.close()


async def run_requests(accounts: List[Dict[str, Any]], output_format: str = "table"):
    with console.status("[bold green]Fetching holds/requests...[/bold green]", spinner="dots"):
        results = await asyncio.gather(*(fetch_account_requests(acc) for acc in accounts))

    if output_format == "json":
        display_requests_json(results)
    elif output_format == "csv":
        display_requests_csv(results)
    else:
        display_requests_table(results)


async def run_cancel_hold(accounts: List[Dict[str, Any]], request_id: str):
    # Search each account for the hold rather than requiring the user to name an
    # account: request IDs are already unique, and this avoids accidentally
    # cancelling on the wrong account if the caller mistypes --add order.
    for account in accounts:
        client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
        try:
            await client.login(account["username"], account["password"], account["institution"], account["view"])
            items = await client.get_requests()
        except Exception as e:
            console.print(f"[red]Could not check {account['username']}: {e}[/red]")
            await client.close()
            continue

        hold = next((item.hold for item in items if item.hold and item.hold.request_id == request_id), None)
        if not hold:
            await client.close()
            continue

        label = account.get("tenant_name", account["username"])
        console.print(f"[bold]Cancelling hold[/bold] '{hold.title}' — {label} ({account['username']})...")
        try:
            await client.cancel_hold(request_id)
            console.print("[green]Hold cancelled.[/green]")
        except Exception as e:
            console.print(f"[red]Cancellation failed: {e}[/red]")
        finally:
            await client.close()
        return

    console.print(f"[red]No active hold with request ID '{request_id}' found on any configured account.[/red]")


def _select_account(
    accounts: List[Dict[str, Any]], index: Optional[int]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Pick the account a single-account action (e.g. --place-hold) runs as.

    Returns `(account, None)` or `(None, error_message)`. Never guesses between several
    enabled accounts — unlike --cancel-hold, the right one can't be inferred."""
    if index is not None:
        if not 1 <= index <= len(accounts):
            return None, f"No account at index {index}. Use --list-accounts to see valid indices."
        account = accounts[index - 1]
        if account.get("enabled", True) is False:
            return None, f"Account {index} is disabled. Enable it first with --enable {index}."
        return account, None
    active = _enabled_accounts(accounts)
    if len(active) == 1:
        return active[0], None
    if not active:
        return None, "No enabled accounts. Use --list-accounts to see accounts and --enable INDEX to enable one."
    return None, "Several accounts are enabled — choose one with --account INDEX (see --list-accounts)."


def _pick_holdable_item(items: List[HoldableItem]) -> HoldableItem:
    # Any copy at a branch can be requested; prefer one that's on the shelf so the hold
    # is fulfilled from stock rather than queued behind a loan.
    on_shelf = [i for i in items if i.status_name and "na półce" in i.status_name.lower()]
    return (on_shelf or items)[0]


def _pick_pickup(pickups: List[PickupLocation], pickup_filter: Optional[str]) -> Optional[PickupLocation]:
    if pickup_filter:
        matches = [p for p in pickups if pickup_filter.lower() in p.name.lower()]
    else:
        matches = pickups
    return matches[0] if len(matches) == 1 else None


async def run_place_hold(
    account: Dict[str, Any],
    mmsid: str,
    branch_filter: Optional[str],
    pickup_filter: Optional[str],
    assume_yes: bool,
):
    label = f"{account.get('tenant_name', 'Unknown')} ({account['username']})"
    client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])

        with console.status("[bold green]Looking up requestable copies...[/bold green]", spinner="dots"):
            items = await client.get_holdable_items(mmsid, branch_filter)
        if not items:
            suffix = f" at a branch matching '{branch_filter}'" if branch_filter else ""
            console.print(f"[red]No requestable copies of MMS {mmsid}{suffix}.[/red]")
            return

        branch_names = list(dict.fromkeys(i.main_location or "?" for i in items))
        if len(branch_names) > 1:
            console.print("[yellow]This record can be requested at several branches — pick one with --branch:[/yellow]")
            for name in branch_names:
                console.print(f"  • {name}")
            return

        item = _pick_holdable_item(items)
        options = await client.get_hold_options(item)
        if not options.pickup_locations:
            console.print("[red]Primo offered no pickup location for this copy.[/red]")
            return
        pickup = _pick_pickup(options.pickup_locations, pickup_filter)
        if not pickup:
            console.print("[yellow]Choose a pickup location with --pickup:[/yellow]")
            for p in options.pickup_locations:
                console.print(f"  • {p.name}")
            return

        # Holds may be reported under the network-zone id, while --search shows local ids.
        record_ids = {mmsid, item.mmsid, item.network_mmsid} - {None}
        holds_before = [r.hold for r in await client.get_requests() if r.hold]
        existing = [h for h in holds_before if h.mmsid in record_ids]
        if existing:
            console.print(
                f"[yellow]Warning: this account already has a hold on this record "
                f"(request ID {existing[0].request_id}, status: {existing[0].status}).[/yellow]"
            )

        console.print(
            Panel(
                "\n".join(
                    [
                        f"[bold]Title:[/bold] {item.title or '-'}",
                        f"[bold]Branch:[/bold] {item.main_location or '-'} ({item.sub_location or '-'})",
                        f"[bold]Copy status:[/bold] {item.status_name or '-'}",
                        f"[bold]Pickup:[/bold] {pickup.name}",
                        f"[bold]Account:[/bold] {label}",
                    ]
                ),
                title="📥 Place hold",
                title_align="left",
            )
        )
        if not assume_yes and not Confirm.ask("Place this hold?"):
            console.print("[dim]Not placed.[/dim]")
            return

        res = await client.place_hold(options, pickup)
        # Primo's success body is just {"status": "ok", ...} with no request ID, and the new
        # hold shows up in myaccount/requests only after a few seconds (observed live:
        # an immediate re-fetch still listed the old holds). Poll briefly to confirm it.
        ids_before = {h.request_id for h in holds_before}
        new_holds = []
        for delay in HOLD_CONFIRM_DELAYS:
            await asyncio.sleep(delay)
            new_holds = [r.hold for r in await client.get_requests() if r.hold and r.hold.request_id not in ids_before]
            if new_holds:
                break
        if new_holds:
            new_hold = new_holds[0]
            console.print(f"[green]Hold placed[/green] — request ID {new_hold.request_id}, status: {new_hold.status}")
        else:
            console.print(
                "[yellow]Primo accepted the request, but the hold hasn't shown up in --requests yet — "
                f"check again in a moment. Response: {res}[/yellow]"
            )
        try:
            queue = await client.get_item_queue(item.item_id)
            if queue:
                console.print(f"Queue: {queue}")
        except httpx.HTTPError:
            pass
    except Exception as e:
        console.print(f"[red]Could not place hold for {label}: {e}[/red]")
    finally:
        await client.close()


def display_requests_table(results: List[Dict[str, Any]]):
    # `hold` items get a typed table (shape verified live, see
    # docs/plans/account-actions-api.md). Other categories (photocopy/booking/cdl/ill/acq)
    # are still shown as raw JSON: no family account has had one of those to verify the
    # real shape against — only `category` is trustworthy for them.
    any_requests = False
    for res in results:
        account = res["account"]
        if res.get("error"):
            console.print(f"[red]Could not fetch requests for {account['username']}: {res['error']}[/red]")
            continue

        items: List[RequestItem] = res["requests"]
        if not items:
            continue
        any_requests = True

        holds = [item.hold for item in items if item.hold]
        other_items = [item for item in items if not item.hold]

        if holds:
            table = Table(
                title=f"📚 {account.get('tenant_name', 'Unknown')} — {account['username']} — Holds",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Request ID", style="dim")
            table.add_column("Title", style="magenta")
            table.add_column("Status")
            table.add_column("Ready for pickup")
            table.add_column("Pickup location")
            table.add_column("Requested")
            table.add_column("Cancellable")

            for hold in holds:
                available_display = "[green]Yes[/green]" if hold.available else "[yellow]No[/yellow]"
                cancellable_display = "[green]Yes[/green]" if hold.cancellable else "No"
                requested_date = parse_date(hold.request_date) if hold.request_date else None
                requested_display = (
                    requested_date.strftime("%d/%m/%Y") if requested_date else (hold.request_date or "-")
                )
                table.add_row(
                    hold.request_id,
                    hold.title,
                    hold.status,
                    available_display,
                    hold.pickup_location or "-",
                    requested_display,
                    cancellable_display,
                )

            console.print(table)
            console.print()

        if other_items:
            table = Table(
                title=f"📑 {account.get('tenant_name', 'Unknown')} — {account['username']}",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Category", style="magenta")
            table.add_column("Raw data", style="dim")

            for item in other_items:
                table.add_row(item.category, json.dumps(item.raw, ensure_ascii=False))

            console.print(table)
            console.print()

    if not any_requests:
        console.print("[italic]No active holds/requests found for any configured account.[/italic]")


def display_requests_json(results: List[Dict[str, Any]]):
    print(json.dumps(results, cls=PydanticEncoder, indent=2))


def display_requests_csv(results: List[Dict[str, Any]]):
    writer = csv.writer(sys.stdout)
    writer.writerow(["account_username", "category", "raw_json"])
    for res in results:
        if res.get("error"):
            continue
        for item in res["requests"]:
            writer.writerow([res["account"]["username"], item.category, json.dumps(item.raw, ensure_ascii=False)])


async def run_branches(branch_filter: Optional[str] = None):
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            with console.status("[bold green]Fetching branch directory...[/bold green]", spinner="dots"):
                branches = await fetch_branches(client)
        except Exception as e:
            console.print(f"[bold red]Could not fetch branch directory:[/bold red] {e}")
            return

    if branch_filter:
        needle = branch_filter.lower()
        branches = [b for b in branches if needle in b.name.lower()]

    display_branches(branches, branch_filter)


def display_branches(branches: List[BranchInfo], branch_filter: Optional[str] = None):
    if not branches:
        suffix = f" matching '{branch_filter}'" if branch_filter else ""
        console.print(f"[italic]No branches found{suffix}.[/italic]")
        return

    # A table would squeeze the long Maps URL against short columns; a panel per
    # branch instead gives every field (especially the URL) its own full-width line.
    for branch in branches:
        lines = [f"[bold]Address:[/bold] {branch.address or '-'}"]
        lines.append(f"[bold]Hours:[/bold]   {branch.hours or '-'}")
        if branch.phone:
            lines.append(f"[bold]Phone:[/bold]   {branch.phone}")
        if branch.maps_url:
            lines.append(f"[bold]Maps:[/bold]    [blue]{branch.maps_url}[/blue]")
        console.print(Panel("\n".join(lines), title=f"📍 {branch.name}", title_align="left"))


class PydanticEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (Loan, BookDetails, UserInfo, Fine, RequestItem)):
            return o.model_dump()
        return super().default(o)


def display_results_json(results: List[Dict[str, Any]]):
    print(json.dumps(results, cls=PydanticEncoder, indent=2))


def display_results_csv(results: List[Dict[str, Any]]):
    writer = csv.writer(sys.stdout)
    # Header
    header = [
        "account_username",
        "user_name",
        "display_name",
        "loan_id",
        "mmsid",
        "title",
        "author",
        "due_date",
        "due_hour",
        "loan_date",
        "loan_status",
        "library_name",
        "location_name",
        "barcode",
        "cover_url",
        "isbns",
        "publisher",
        "publication_date",
    ]
    writer.writerow(header)

    for res in results:
        if res.get("error"):
            continue
        user_info: UserInfo = res["user_info"]
        for item in res["loans"]:
            loan: Loan = item["loan"]
            details: Optional[BookDetails] = item["details"]
            row = [
                res["account"]["username"],
                user_info.user_name,
                user_info.display_name,
                loan.id,
                loan.mmsid,
                loan.title,
                loan.author,
                loan.due_date,
                loan.due_hour,
                loan.loan_date,
                loan.status,
                loan.library_name,
                loan.location_name,
                loan.barcode,
                details.cover_url if details else "",
                ",".join(details.isbns) if details else "",
                details.publisher if details else "",
                details.publication_date if details else "",
            ]
            writer.writerow(row)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--add", is_flag=True, help="Add a new account to configuration")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    show_default=True,
    help="Output format",
)
@click.option("--renew", is_flag=True, help="Attempt to renew all renewable loans for configured accounts")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show more details: loan date and renewability (default), or genre/subject/ISBN/etc. per edition with --search",
)
@click.option("--history", is_flag=True, help="Show loan history instead of active loans")
@click.option("--search", metavar="QUERY", help="Search the catalog by title/keyword")
@click.option("--branch", metavar="NAME", help="Filter --search/--branches results to names containing this text")
@click.option(
    "--address",
    is_flag=True,
    help="Show branch street address (and maps link) in --search results",
)
@click.option(
    "--branches",
    is_flag=True,
    help="Show the Biblioteka Raczyńskich branch directory (address, hours, phone, maps link)",
)
@click.option("--fines", is_flag=True, help="Show itemized fines for all configured accounts")
@click.option(
    "--requests",
    "show_requests",
    is_flag=True,
    help="Show active holds/requests for all configured accounts "
    "(holds are shown in a typed table; other categories are still raw — see docs/plans/account-actions-api.md)",
)
@click.option(
    "--cancel-hold",
    metavar="REQUEST_ID",
    help="Cancel a hold by its request ID (as shown in --requests output)",
)
@click.option(
    "--place-hold",
    metavar="MMSID",
    help="Place a hold (zamówienie) on a record by MMS ID (as shown in --search output); "
    "narrow with --branch, choose with --account/--pickup",
)
@click.option(
    "--account",
    "account_index",
    type=int,
    metavar="INDEX",
    help="Account to use for --place-hold, by index (see --list-accounts); required if several are enabled",
)
@click.option("--pickup", metavar="NAME", help="Pickup location for --place-hold, when more than one is offered")
@click.option("-y", "--yes", "assume_yes", is_flag=True, help="Don't ask for confirmation before --place-hold")
@click.option(
    "--list-accounts",
    is_flag=True,
    help="List all configured accounts with index, enabled status, and timeout",
)
@click.option("--enable", type=int, metavar="INDEX", help="Enable account by index (see --list-accounts)")
@click.option("--disable", type=int, metavar="INDEX", help="Disable account by index (see --list-accounts)")
@click.option(
    "--set-timeout",
    nargs=2,
    metavar="INDEX SECONDS",
    help="Set per-account HTTP timeout in seconds by index (see --list-accounts)",
)
@click.option(
    "--demo",
    is_flag=True,
    help="Switch to demo mode: disable all non-demo accounts and enable/create the omnis-mock demo account",
)
@click.option(
    "--exit-demo",
    is_flag=True,
    help="Exit demo mode: disable the demo account and re-enable accounts that --demo had disabled",
)
def cli(
    add: bool,
    output_format: str,
    renew: bool,
    verbose: bool,
    history: bool,
    search: Optional[str],
    branch: Optional[str],
    address: bool,
    branches: bool,
    fines: bool,
    show_requests: bool,
    cancel_hold: Optional[str],
    place_hold: Optional[str],
    account_index: Optional[int],
    pickup: Optional[str],
    assume_yes: bool,
    list_accounts: bool,
    enable: Optional[int],
    disable: Optional[int],
    set_timeout: Optional[tuple],
    demo: bool,
    exit_demo: bool,
):
    """OMNIS Library CLI Manager"""
    asyncio.run(
        async_main(
            add=add,
            output_format=output_format,
            renew=renew,
            verbose=verbose,
            history=history,
            search=search,
            branch=branch,
            address=address,
            branches=branches,
            fines=fines,
            show_requests=show_requests,
            cancel_hold=cancel_hold,
            place_hold=place_hold,
            account_index=account_index,
            pickup=pickup,
            assume_yes=assume_yes,
            list_accounts=list_accounts,
            enable=enable,
            disable=disable,
            set_timeout=set_timeout,
            demo=demo,
            exit_demo=exit_demo,
        )
    )


async def async_main(
    *,
    add: bool,
    output_format: str,
    renew: bool,
    verbose: bool,
    history: bool,
    search: Optional[str],
    branch: Optional[str],
    address: bool,
    branches: bool,
    fines: bool,
    show_requests: bool,
    cancel_hold: Optional[str],
    place_hold: Optional[str],
    account_index: Optional[int],
    pickup: Optional[str],
    assume_yes: bool,
    list_accounts: bool,
    enable: Optional[int],
    disable: Optional[int],
    set_timeout: Optional[tuple],
    demo: bool,
    exit_demo: bool,
):
    if branches:
        await run_branches(branch)
        return

    accounts = load_config()

    if list_accounts:
        display_accounts_table(accounts)
        return

    if enable is not None:
        try:
            _set_account_enabled(accounts, enable, True)
        except IndexError:
            rprint(f"[red]No account at index {enable}. Use --list-accounts to see valid indices.[/red]")
            return
        save_config(accounts)
        return

    if disable is not None:
        try:
            _set_account_enabled(accounts, disable, False)
        except IndexError:
            rprint(f"[red]No account at index {disable}. Use --list-accounts to see valid indices.[/red]")
            return
        save_config(accounts)
        return

    if set_timeout is not None:
        try:
            idx = int(set_timeout[0])
            seconds = float(set_timeout[1])
            if seconds <= 0:
                raise ValueError("timeout must be positive")
            _set_account_timeout(accounts, idx, seconds)
        except (ValueError, IndexError) as e:
            rprint(f"[red]Invalid --set-timeout arguments: {e}[/red]")
            return
        save_config(accounts)
        return

    if demo:
        accounts = _apply_demo_mode(accounts)
        save_config(accounts)
        rprint("[bold green]Demo mode enabled.[/bold green] Using omnis-mock (https://omnis-mock.onrender.com).")
        rprint(
            "[dim]Note: the first request may take ~50s if the free-tier mock server is cold "
            "(Render cold start).[/dim]"
        )
        return

    if exit_demo:
        accounts = _exit_demo_mode(accounts)
        save_config(accounts)
        rprint("[bold green]Demo mode disabled.[/bold green] Restored previously enabled accounts.")
        return

    active_accounts = _enabled_accounts(accounts)

    if fines:
        if not accounts:
            rprint("[red]No accounts configured. Add one first with --add.[/red]")
            return
        if not active_accounts:
            rprint(
                "[yellow]No enabled accounts. Use --list-accounts to see accounts, --enable INDEX to "
                "enable one, or --demo for the demo account.[/yellow]"
            )
            return
        await run_fines(active_accounts, output_format)
        return

    if show_requests:
        if not accounts:
            rprint("[red]No accounts configured. Add one first with --add.[/red]")
            return
        if not active_accounts:
            rprint(
                "[yellow]No enabled accounts. Use --list-accounts to see accounts, --enable INDEX to "
                "enable one, or --demo for the demo account.[/yellow]"
            )
            return
        await run_requests(active_accounts, output_format)
        return

    if cancel_hold:
        if not accounts:
            rprint("[red]No accounts configured. Add one first with --add.[/red]")
            return
        if not active_accounts:
            rprint(
                "[yellow]No enabled accounts. Use --list-accounts to see accounts, --enable INDEX to "
                "enable one, or --demo for the demo account.[/yellow]"
            )
            return
        await run_cancel_hold(active_accounts, cancel_hold)
        return

    if place_hold:
        if not accounts:
            rprint("[red]No accounts configured. Add one first with --add.[/red]")
            return
        account, error = _select_account(accounts, account_index)
        if account is None:
            rprint(f"[yellow]{error}[/yellow]")
            if account_index is None and len(active_accounts) > 1:
                display_accounts_table(accounts)
            return
        await run_place_hold(account, place_hold, branch, pickup, assume_yes)
        return

    if search:
        if not accounts:
            rprint("[red]No accounts configured. Add one first with --add.[/red]")
            return
        if not active_accounts:
            rprint(
                "[yellow]No enabled accounts. Use --list-accounts to see accounts, --enable INDEX to "
                "enable one, or --demo for the demo account.[/yellow]"
            )
            return
        await run_search(active_accounts[0], search, branch, address, verbose)
        return

    if add or not accounts:
        if not accounts:
            console.print("[yellow]No configuration found. Let's add your first account![/yellow]")

        while True:
            new_account = add_account_wizard()
            accounts.append(new_account)
            save_config(accounts)

            if not Confirm.ask("Do you want to add another account?"):
                break

        # If we just added accounts, we probably want to show data immediately
        rprint("\n[bold green]Fetching data...[/bold green]")

    if not accounts:
        rprint("[red]No accounts configured. Exiting.[/red]")
        return

    active_accounts = _enabled_accounts(accounts)
    if not active_accounts:
        rprint(
            "[yellow]No enabled accounts. Use --list-accounts to see accounts, --enable INDEX to "
            "enable one, or --demo for the demo account.[/yellow]"
        )
        return

    # If requested, attempt to renew loans before fetching data so updated due dates are shown
    if renew and not history:
        rprint("\n[bold green]Attempting to renew renewable loans for all accounts...[/bold green]")
        for account in active_accounts:
            client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
            try:
                await client.login(
                    account["username"],
                    account["password"],
                    account.get("institution", "48OMNIS_BRP"),
                    account.get("view", "48OMNIS_BRP:BRACZ"),
                )
            except Exception as e:
                console.print(f"[red]Login failed for {account.get('username')}: {e}[/red]")
                try:
                    await client.close()
                except Exception:
                    pass
                continue

            try:
                loans = await client.get_loans()
            except Exception as e:
                console.print(f"[red]Could not fetch loans for {account.get('username')}: {e}[/red]")
                await client.close()
                continue

            renewed_any = False
            for loan in loans:
                if getattr(loan, "renewable", False):
                    try:
                        res = await client.renew_loan(loan.id)
                        console.print(
                            f"[green]Renewed '{loan.title}' ({loan.id}) for {account.get('username')}: {res}[/green]"
                        )
                    except Exception as e:
                        console.print(
                            f"[red]Could not renew '{loan.title}' ({loan.id}) for {account.get('username')}: {e}[/red]"
                        )
                    renewed_any = True

            if not renewed_any:
                console.print(f"[dim]No renewable loans for {account.get('username')}[/dim]")

            await client.close()

        rprint("\n[bold green]Renewal attempts finished. Fetching updated data...[/bold green]")

    # Details are needed for json and csv formats
    fetch_details = output_format in ["json", "csv"]

    with console.status(
        f"[bold green]Fetching library {'history' if history else 'data'}...[/bold green]", spinner="dots"
    ):
        tasks = [fetch_account_data(acc, fetch_details, history) for acc in active_accounts]
        results = await asyncio.gather(*tasks)

    if output_format == "table":
        display_results_table(results, details=fetch_details, history=history, verbose=verbose)
    elif output_format == "json":
        display_results_json(results)
    elif output_format == "csv":
        display_results_csv(results)


def main():
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[red]Cancelled by user[/red]")
        sys.exit(0)


if __name__ == "__main__":
    main()
