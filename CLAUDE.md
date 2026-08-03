# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`omnis-py` is a Python library + CLI for programmatic access to patron accounts in libraries running Ex Libris Primo (the Polish OMNIS network — Biblioteka Raczyńskich, Biblioteka Narodowa, UAM, UJ, UMK, and others). It handles login, fetching active/historical loans, user account status (fines, counts), loan renewal, catalog search with per-branch availability, and book cover/metadata lookup via OpenLibrary.

## Commands

```bash
# Install with dev dependencies (editable)
pip install -e ".[dev]"

# Lint
ruff check .

# Format check / format
black --check .
black .

# Type check
mypy src

# Run all tests
pytest

# Run a single test
pytest tests/test_client.py::test_login_success

# Run the CLI locally
python -m omnis.cli
# or, once installed:
omnis-cli
```

CI (`.github/workflows/ci.yml`) runs ruff, black --check, mypy, and pytest on Python 3.11 and 3.12 for every push/PR to `main`. Tags matching `v*` additionally trigger a PyPI publish job after tests pass.

Line length for both black and ruff is 120 (`pyproject.toml`).

## Architecture

The package is small and lives entirely under `src/omnis/`:

- **`client.py`** — `OmnisClient`, the async httpx-based client that talks to a Primo instance. All Primo API interaction lives here:
  - `login()` — performs the two-step Primo login flow (cookie-priming GET to `/discovery/search`, then POST to `/primaws/suprimaLogin`) and extracts a JWT (`self.token`) from the response.
  - `get_user_info()` — decodes the JWT payload locally (no signature verification — it's just base64) to get the display name, and calls `/primaws/rest/priv/myaccount/counters` for loan/request/fine counts.
  - `get_loans()` — paginates `/primaws/rest/priv/myaccount/loans` using the `showmore` flag in the response until exhausted.
  - `get_record_details()` — fetches the full PNX record for a book by `mmsid` and tries to resolve a cover image via OpenLibrary (`get_cover_url`, matched by ISBN).
  - `renew_loan()` — POSTs to `/primaws/rest/priv/myaccount/renew_loans`.
  - `search_books()` — catalog search by title/keyword, returning `SearchResult` (one per distinct work/`frbrgroupid`) each holding multiple `BookVersion`s (editions), each with a list of `BranchAvailability`. This is the most involved flow in the client and relies on undocumented Primo endpoints reverse-engineered from browser network captures (`curls/` locally, gitignored) — see the design notes below before changing it.
  - Pydantic models `Loan`, `BookDetails`, `UserInfo`, `SearchResult`, `BookVersion`, `BranchAvailability` define the data shapes; `Loan` uses field aliases matching Primo's raw JSON keys (e.g. `loanid`, `duedate`) and `Loan.from_api()` normalizes the `renew` flag into a `renewable` bool. The search models are built manually (not via aliases) since they merge data from multiple endpoints.
  - A client instance is tied to one logged-in account: `base_url`/`institution`/`view`/`token` are all instance state set by `login()`. Concurrent multi-account use means creating one `OmnisClient` per account.

### Catalog search (`search_books`) — non-obvious API constraints

Primo's public search API (`/primaws/rest/pub/pnxs`) collapses results one-per-work by default (grouped by `frbrgroupid`); getting all editions of one work requires a second call with `qInclude=facet_frbrgroupid,exact,<id>&sort=date_d`. `search_books()` therefore always does a top-level search, then one group-expansion call per resulting work (concurrently via `asyncio.gather`).

**Critical gotcha:** `/primaws/rest/pub/delivery` (POST, body = list of `alma`-prefixed record ids) does *not* return availability for arbitrary ids you pass it — it re-runs its own internal search using the query params you send (`q`/`qInclude`/`sort`) and only reports on ids that fall within that query's own result page. So `delivery` must be called once per distinct query variant, with the exact same params used to produce that group's docs, and only that group's ids in the body. Batching all ids from every group into one `delivery` call silently drops most of them — this was empirically verified against the live API, not assumed.

`delivery` only reports `availabilityStatus` (`available`/`unavailable`) per branch, never a due date — Primo doesn't expose that at the aggregate holdings level. Getting a due date for an `unavailable` branch requires two more calls per holding: `GET /primaws/rest/pub/getPhysicalService/{bare_mmsid}` (note: bare MMS id, no `alma` prefix — unlike `delivery`'s ids) to get a `physicalServiceId`, then `POST /primaws/rest/priv/ILSServices/holdings/{physicalServiceId}` with a body whose `locations` list contains *only that one holding* (sending the full holdings list here returns an empty `items` array instead of item-level detail). The due date is embedded in a human-readable Polish string on the returned item (`itemstatusname`, e.g. `"Wypożyczenie do 31/08/2026"` or `"Wypożyczony - termin zwrotu przekroczony od 20/03/2026"` when overdue) and is extracted via regex (`_get_due_date_for_holding`) rather than a structured field.

`branch_filter` (substring match on `mainLocation`, case-insensitive) is applied client-side after fetching delivery data, and narrows which holdings get the due-date enrichment calls — it does not reduce the initial search/group/delivery calls.

- **`tenants.py`** — `KNOWN_TENANTS`, a static list of pre-configured library tenants (base URL, institution code, view ID) used by the CLI's account wizard. Includes a `"Custom / Własna..."` sentinel entry for arbitrary Primo instances.

- **`branches.py`** — unlike every other module here, this is *not* generic across Primo/OMNIS tenants: it scrapes the branch directory (address/hours/phone) specifically for Biblioteka Raczyńskich from its own public WordPress site (`bracz.edu.pl`), since there is no such endpoint in the Primo/Alma API at all. `fetch_branches()` calls the WP REST API (`GET https://bracz.edu.pl/wp-json/wp/v2/pages?slug=filie`, no auth needed) and `parse_branches()` regex-extracts the repeated `<h2>{branch name}</h2><p>Adres: ... Godziny otwarcia: ... telefon: ... email: ...</p>` block per branch from the returned `content.rendered` HTML (verified to parse all 36 branches cleanly; no HTML-parsing dependency was added since a handful of prefix-anchored `<strong>label:</strong>` fields don't need one). `BranchInfo.maps_url` builds a plain `google.com/maps/search` link from the scraped address text (deliberately *not* from the GPS coordinates in the Google My Maps layer also embedded on that page — matching Primo's branch names like `"Filia 47/57"` to that map's inconsistent labels like `"Filia nr 47/57"` was judged not worth the fragility versus a plain address-based search link).

- **`cli.py`** — `omnis-cli` entry point (`omnis.cli:main` in `pyproject.toml`). Responsibilities:
  - Reads/writes YAML config at `~/.config/omnis-py/config.yaml` (list of accounts, each with credentials + tenant info).
  - `add_account_wizard()` drives an interactive Rich-based prompt flow to add accounts, picking from `KNOWN_TENANTS` or entering a custom Primo instance.
  - `fetch_account_data()` logs into and fetches data for one account, optionally with per-book details (`get_record_details`), run concurrently across accounts via `asyncio.gather`.
  - `--renew` performs renewal for all renewable loans *before* the main fetch, so subsequently displayed due dates reflect the renewal.
  - Three output modes: `table` (default, grouped by library/branch via Rich tables), `json`, `csv`. Full per-book details (cover, ISBN, publisher) are only fetched when the output format is `json` or `csv`; `--verbose` in table mode just adds columns (loan date, renewable) without triggering the extra detail fetch.
  - Dates from Primo come as `YYYYMMDD` or similar; `parse_date()`/`format_due_date()` handle formatting and relative-day coloring (red/yellow/green) for the table view.
  - `--search QUERY` (optionally with `--branch NAME`) short-circuits `async_main()` right after `load_config()`, before the account-wizard/loans-fetch logic, and returns — it reuses the first configured account purely to obtain login credentials/tenant info, and has its own renderer (`display_search_results`) rather than touching the loan table/json/csv renderers.
  - `--branches` (optionally with `--branch NAME` reused as a name filter) short-circuits even earlier, *before* `load_config()`, since it needs no OMNIS account at all — it's a plain unauthenticated HTTP call to `bracz.edu.pl` via `omnis.branches.fetch_branches`. Rendered as one `Panel` per branch (`display_branches`), not a `Table` — a single wide table squeezes the long Maps URL against short columns and Rich ellipsizes it to the terminal width; a panel gives every field, especially the URL, a full-width line instead.

There is no ORM/database — all state is either in-memory during a run or in the YAML config file. Credentials are stored in plaintext in `config.yaml`.

## Testing notes

Tests use `pytest-asyncio` and `respx` to mock httpx calls against the real Primo endpoint paths (see `tests/test_client.py`). When adding client methods, mock the exact `base_url + path` respx expects; `OmnisClient()` defaults to the Biblioteka Raczyńskich `base_url`.

## Release process

`release.sh` bumps the version in `pyproject.toml`, commits, tags (`vX.Y.Z`), and pushes — this triggers the CI publish job. `publish_manual.sh` is a fallback for manual PyPI upload via `twine`, reading `PYPI_TOKEN` from `.env` or the shell environment.
