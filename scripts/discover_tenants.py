"""Maintainer-only helper: surface candidate OMNIS tenants not yet in KNOWN_TENANTS.

Runs a handful of broad search queries against an already-configured account and
collects the `other_institutions` (from Primo's `almaInstitutionsList`, parsed by
OmnisClient.search_books) that show up across those results. Diffs the institution
codes seen against `tenants.KNOWN_TENANTS` and prints the ones not yet configured.

This is a research aid, not an automated tenant-list updater: Primo's delivery
response never includes a usable base_url/view for other institutions (envURL is
always empty in observed responses), so each printed candidate still needs manual
lookup before it can be added to tenants.py.

Not wired into omnis-cli - the data here is inherently partial (limited to whatever
institutions happen to hold the queried titles) and heuristic, not something to
present as a complete network directory to end users.

Usage: python scripts/discover_tenants.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from omnis.cli import _enabled_accounts, load_config  # noqa: E402
from omnis.client import OmnisClient  # noqa: E402
from omnis.tenants import KNOWN_TENANTS  # noqa: E402

# Broad, popular queries chosen to span different genres/publishers, so their
# delivery responses touch a varied set of institutions rather than one niche.
QUERIES = [
    "harry potter",
    "pan tadeusz",
    "wiedźmin",
    "lalka prus",
    "sapkowski",
    "krzyżacy sienkiewicz",
    "mały książę",
    "zbrodnia i kara",
]


async def main() -> None:
    accounts = _enabled_accounts(load_config())
    if not accounts:
        print("No enabled accounts configured - run `omnis-cli` to add one first.")
        return
    account = accounts[0]

    known_codes = {t["institution"] for t in KNOWN_TENANTS if t["institution"]}
    seen: dict[str, str] = {}

    client = OmnisClient(account["base_url"], timeout=account.get("timeout", 30.0))
    try:
        await client.login(account["username"], account["password"], account["institution"], account["view"])
        for query in QUERIES:
            print(f"Searching '{query}'...")
            # Due dates require extra per-holding requests and are irrelevant here -
            # only the delivery response's almaInstitutionsList is needed.
            try:
                results = await client.search_books(query, fetch_due_dates=False)
            except Exception as e:
                print(f"  skipped ('{query}' failed: {e})")
                continue
            for result in results:
                for version in result.versions:
                    for inst in version.other_institutions:
                        seen[inst.code] = inst.name
    finally:
        await client.close()

    candidates = {code: name for code, name in seen.items() if code not in known_codes}

    print(f"\nSeen {len(seen)} distinct institutions across {len(QUERIES)} queries.")
    print(f"{len(candidates)} are not yet in KNOWN_TENANTS:\n")
    for code, name in sorted(candidates.items()):
        print(f"  {code:20s} {name}")

    if candidates:
        print(
            "\nFor each candidate above, manually find its Primo base_url and view "
            "(e.g. search '<name> katalog OMNIS Primo') before adding it to tenants.py."
        )


if __name__ == "__main__":
    asyncio.run(main())
