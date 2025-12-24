import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel
from rich import print as rprint

from omnis.client import OmnisClient, UserInfo, Loan, BookDetails
from omnis.tenants import KNOWN_TENANTS

CONFIG_DIR = Path.home() / ".config" / "omnis-py"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

console = Console()


def load_config() -> List[Dict[str, str]]:
    if not CONFIG_FILE.exists():
        return []
    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f)
            return data.get("accounts", []) if data else []
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {e}")
        return []


def save_config(accounts: List[Dict[str, str]]):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump({"accounts": accounts}, f)
    console.print(f"[green]Configuration saved to {CONFIG_FILE}[/green]")


def add_account_wizard() -> Dict[str, str]:
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

    return {
        "username": username,
        "password": password,
        "base_url": base_url,
        "institution": institution,
        "view": view,
        "tenant_name": tenant_name,
    }


async def fetch_account_data(account: Dict[str, str], details: bool = False) -> Dict[str, Any]:
    client = OmnisClient(account["base_url"])
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])
        user_info = await client.get_user_info()
        loans = await client.get_loans()

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

        return {"account": account, "user_info": user_info, "loans": loans_with_details, "error": None}
    except Exception as e:
        return {"account": account, "error": str(e)}
    finally:
        await client.close()


def display_results(results: List[Dict[str, Any]], details: bool = False):
    # 1. User Summary Table
    summary_table = Table(title="Users & Status")
    summary_table.add_column("User", style="cyan")
    summary_table.add_column("Library", style="magenta")
    summary_table.add_column("Active Loans", justify="center", style="green")
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
            str(user_info.loans_count),
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
        console.print("[italic]No active loans found.[/italic]")
        return

    for location, items in sorted(all_loans_by_location.items()):
        loc_table = Table(title=f"📍 {location}", show_header=True, header_style="bold")
        loc_table.add_column("Return Date", style="bold yellow", width=12)
        loc_table.add_column("Author", style="blue")
        loc_table.add_column("Title", style="white")
        loc_table.add_column("Borrowed By", style="cyan")
        loc_table.add_column("Status", style="dim")
        if details:
            loc_table.add_column("Details", style="dim")

        # Sort by due date
        items.sort(key=lambda x: x["loan"].due_date)

        for item in items:
            current_loan: Loan = item["loan"]
            book_details: Optional[BookDetails] = item["details"]
            owner = item["owner"]

            row_data = [
                f"{current_loan.due_date}",
                current_loan.author or "",
                current_loan.title,
                owner,
                current_loan.status,
            ]

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


async def async_main():
    parser = argparse.ArgumentParser(description="OMNIS Library CLI Manager")
    parser.add_argument("--add", action="store_true", help="Add a new account to configuration")
    parser.add_argument("--details", action="store_true", help="Fetch extended book details (slower)")
    args = parser.parse_args()

    accounts = load_config()

    if args.add or not accounts:
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

    with console.status("[bold green]Fetching library data...[/bold green]", spinner="dots"):
        tasks = [fetch_account_data(acc, args.details) for acc in accounts]
        results = await asyncio.gather(*tasks)

    display_results(results, args.details)


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        console.print("\n[red]Cancelled by user[/red]")
        sys.exit(0)


if __name__ == "__main__":
    main()
