import asyncio
import re
import httpx
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError


class Loan(BaseModel):
    id: str = Field(alias="loanid")
    mmsid: str
    title: str
    author: Optional[str] = None
    due_date: str = Field(alias="duedate")
    due_hour: str = Field(alias="duehour")
    loan_date: str = Field(alias="loandate")
    status: str = Field(alias="loanstatus")
    library_name: str = Field(alias="ilsinstitutionname")
    location_name: str = Field(alias="mainlocationname")
    sub_location_name: Optional[str] = Field(None, alias="secondarylocationname")
    barcode: str = Field(alias="itembarcode")
    renewable: bool = False

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Loan":
        data["renewable"] = data.get("renew") == "Y"
        return cls(**data)


_FINE_AMOUNT_RE = re.compile(r"([\d,.]+)\s*(\S+)")


def _parse_fine_amount(value: str) -> Tuple[float, str]:
    """Parse a Polish-formatted fine amount like "0,20 PLN" (comma decimal, currency suffix).

    Distinct from the plain "0.00" format used by myaccount/counters.
    """
    match = _FINE_AMOUNT_RE.match((value or "").strip())
    if not match:
        return 0.0, ""
    number, currency = match.groups()
    return float(number.replace(",", ".")), currency


class Fine(BaseModel):
    id: str = Field(alias="fineid")
    status: str = Field(alias="finestatus")
    amount: float
    currency: str
    original_amount: float
    date: str = Field(alias="finedate")
    location: str = Field(alias="finemainlocation")
    title: str
    type: str
    description: str
    is_alert: bool = Field(alias="isAlert")

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Fine":
        amount, currency = _parse_fine_amount(data.get("finesum", ""))
        original_amount, _ = _parse_fine_amount(data.get("originalfinesum", ""))
        data["amount"] = amount
        data["currency"] = currency
        data["original_amount"] = original_amount
        return cls(**data)


class Hold(BaseModel):
    """A single `hold` entry from myaccount/requests, shape verified live (see
    docs/plans/account-actions-api.md). Only the `hold` category has been observed
    against a real account so far — photocopy/booking/cdl/ill/acq entries stay as
    raw dicts on `RequestItem` until one of those is verified too.
    """

    request_id: str = Field(alias="requestid")
    title: str
    status: str = Field(alias="holdstatus")
    available: bool
    cancellable: bool
    author: Optional[str] = None
    pickup_location: Optional[str] = Field(None, alias="pickuplocationname")
    request_date: Optional[str] = Field(None, alias="requestdate")
    mmsid: Optional[str] = None
    ils_institution_name: Optional[str] = Field(None, alias="ilsinstitutionname")
    ils_institution_code: Optional[str] = Field(None, alias="ilsinstitutioncode")

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Hold":
        data = dict(data)
        data["available"] = data.get("available") == "Y"
        data["cancellable"] = data.get("cancel") == "Y"
        return cls(**data)


class RequestItem(BaseModel):
    """A single hold/photocopy/booking/cdl/ill/acq entry from myaccount/requests.

    Kept as a raw dict rather than named fields for categories other than `hold`:
    no family account has had an active photocopy/booking/cdl/ill/acq to observe
    the real per-item shape against (see docs/plans/account-actions-api.md), so
    those field names are deliberately not guessed. `hold` is populated whenever
    the raw entry parses cleanly against the verified `Hold` shape; `raw` is kept
    regardless so nothing is lost if a future account shows an unverified variant.
    """

    category: str
    raw: Dict[str, Any]
    hold: Optional[Hold] = None


class BookDetails(BaseModel):
    mmsid: str
    cover_url: Optional[str] = None
    isbns: List[str] = []
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    subjects: List[str] = []
    genres: List[str] = []
    physical_description: Optional[str] = None
    original_title: Optional[str] = None


class UserInfo(BaseModel):
    display_name: str
    user_name: str
    loans_count: int = 0
    requests_count: int = 0
    fines_amount: float = 0.0
    fines_currency: str = "PLN"


class BranchAvailability(BaseModel):
    library_name: str
    library_code: str
    sub_location: Optional[str] = None
    maps_url: Optional[str] = None
    status: str
    due_date: Optional[str] = None
    overdue: bool = False


class OtherInstitution(BaseModel):
    code: str
    name: str


class BookVersion(BaseModel):
    mmsid: str
    title: str
    author: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    isbns: List[str] = []
    frbrgroupid: Optional[str] = None
    series: Optional[str] = None
    genres: List[str] = []
    subjects: List[str] = []
    language: Optional[str] = None
    physical_description: Optional[str] = None
    resource_type: Optional[str] = None
    branches: List[BranchAvailability] = []
    other_institutions: List[OtherInstitution] = []


class SearchResult(BaseModel):
    frbrgroupid: Optional[str] = None
    title: str
    author: Optional[str] = None
    versions: List[BookVersion] = []


class HoldableItem(BaseModel):
    """A single physical copy that Primo offers an `AlmaItemRequest` (hold) service for,
    taken from the item list of `ILSServices/holdings` (shape verified live, see
    `curls/zamowienie`). `request_path` is Primo's own `link-to-service` for that item —
    it embeds a `physicalServiceId` that is session-scoped, so items must not be cached
    across logins."""

    mmsid: str
    item_id: str
    request_path: str
    # Network-zone MMS id of the same record (`pnx.control.originalsourceid`) — the id
    # `myaccount/requests` reports holds under, so needed to match existing holds.
    network_mmsid: Optional[str] = None
    title: Optional[str] = None
    barcode: Optional[str] = None
    status_name: Optional[str] = None
    category: Optional[str] = None
    policy: Optional[str] = None
    material: Optional[str] = None
    call_number: Optional[str] = None
    main_location: Optional[str] = None
    sub_location: Optional[str] = None


class PickupLocation(BaseModel):
    """One pickup option from the hold request form. Primo encodes it as a single
    `"<libraryId>$$<TYPE>"` key (e.g. `"42713777720009337$$LIBRARY"`); the submit
    body needs the two halves separately."""

    id: str
    type: str
    name: str

    @classmethod
    def from_key(cls, key: str, name: str) -> "PickupLocation":
        parts = key.split("$$")
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"Unexpected pickup location key format: {key!r}")
        return cls(id=parts[0], type=parts[1], name=name)


class HoldRequestOptions(BaseModel):
    """The hold request form for one item (`GET .../AlmaItemRequest`)."""

    item: HoldableItem
    request_type: str
    material_type: str
    pickup_locations: List[PickupLocation]


def _raise_for_primo_failure(data: Any) -> None:
    """Primo reports some failures as HTTP 200 with an envelope like
    `{"status": "failed", "reply-code": "0002", "reply-text": "..."}` (successful
    envelopes carry `"status": "ok"`, `"reply-code": "0000"`). Responses without
    those keys are left alone — not every endpoint wraps its body this way."""
    if not isinstance(data, dict):
        return
    reply_code = data.get("reply-code")
    if data.get("status") == "failed" or (reply_code is not None and reply_code != "0000"):
        raise ValueError(f"Primo rejected the request: {data.get('reply-text') or data}")


class OmnisClient:
    def __init__(
        self,
        base_url: str = "https://omnis-br.primo.exlibrisgroup.com",
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        if client:
            # timeout is ignored here: an externally-provided client already has its own.
            self.client = client
            self._close_client = False
        else:
            self.client = httpx.AsyncClient(follow_redirects=True, timeout=timeout)
            self._close_client = True

        self.token: Optional[str] = None
        self.user_data: Dict[str, Any] = {}
        self.view: Optional[str] = None
        self.institution: Optional[str] = None

    async def login(
        self, username: str, password: str, institution: str = "48OMNIS_BRP", view: str = "48OMNIS_BRP:BRACZ"
    ):
        self.view = view
        self.institution = institution
        # Initial request to get cookies
        await self.client.get(f"{self.base_url}/discovery/search", params={"vid": view})

        login_url = f"{self.base_url}/primaws/suprimaLogin"
        params = {"lang": "pl"}
        data = {
            "authenticationProfile": "Alma",
            "username": username,
            "password": password,
            "institution": institution,
            "view": view,
            "targetUrl": f"{self.base_url}/discovery/search?vid={view}",
        }
        headers = {
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/discovery/search?vid={view}",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        response = await self.client.post(login_url, params=params, data=data, headers=headers)
        if response.status_code == 401:
            raise ValueError("Invalid credentials (401)")
        response.raise_for_status()

        result = response.json()
        token = result.get("jwtData", "").strip('"')
        if not token:
            raise ValueError("No token received in login response")

        self.token = token
        # Basic user info from the same response if available, or we get it later
        return token

    async def get_user_info(self) -> UserInfo:
        if not self.token:
            raise ValueError("Not logged in")

        # Get display name from JWT
        import json
        import base64

        _, payload_b64, _ = self.token.split(".")
        # Add padding if needed
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
        display_name = payload.get("displayName", "Unknown")
        user_name = payload.get("userName", "")

        # Get counters
        counters_url = f"{self.base_url}/primaws/rest/priv/myaccount/counters"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = await self.client.get(counters_url, params={"lang": "pl"}, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", {})
        actions = data.get("listofactions", {}).get("action", [])

        counts = {a.get("type"): a.get("value") for a in actions}

        loans_count = int(counts.get("Loans", 0))
        requests_count = int(counts.get("Requests", 0))
        fines_str = counts.get("Fines", "0.00")

        return UserInfo(
            display_name=display_name,
            user_name=user_name,
            loans_count=loans_count,
            requests_count=requests_count,
            fines_amount=float(fines_str),
            fines_currency="PLN",  # Usually fixed or we could find it elsewhere
        )

    async def get_loans(self, loan_type: str = "active") -> List[Loan]:
        if not self.token:
            raise ValueError("Not logged in")

        loans_url = f"{self.base_url}/primaws/rest/priv/myaccount/loans"
        bulk_size = 50
        offset = 1
        all_loans = []

        while True:
            params = {
                "bulk": str(bulk_size),
                "lang": "pl",
                "offset": str(offset),
                "type": loan_type,
            }
            headers = {"Authorization": f"Bearer {self.token}"}

            response = await self.client.get(loans_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            loans_data = data.get("data", {}).get("loans", {})

            current_batch = loans_data.get("loan", [])
            all_loans.extend([Loan.from_api(loan_data) for loan_data in current_batch])

            showmore = loans_data.get("showmore", [])
            # showmore is typically a list like ['Y'] or empty/missing if no more
            if not showmore or "Y" not in showmore:
                break

            offset += bulk_size

        return all_loans

    async def get_cover_url(self, isbns: List[str]) -> Optional[str]:
        """Try to find a cover image from OpenLibrary using ISBNs."""
        base_url = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
        for isbn in isbns:
            url = base_url.format(isbn=isbn)
            try:
                # We use a HEAD request to be efficient and not download the whole image
                response = await self.client.head(url, follow_redirects=True)
                # OpenLibrary redirects to a placeholder if the image doesn't exist.
                # A real cover will have a URL that contains the ISBN.
                if response.status_code == 200 and isbn in str(response.url):
                    return str(response.url)
            except httpx.RequestError:
                # Ignore connection errors and try the next ISBN
                continue
        return None

    async def get_record_details(self, mmsid: str) -> "BookDetails":
        """Fetch full record details (PNX) for a given MMS ID."""
        if not self.view:
            raise ValueError("View not set. Please login first.")

        url = f"{self.base_url}/primaws/rest/pub/pnxs/L/alma{mmsid}"
        params = {"vid": self.view, "lang": "pl"}
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        pnx = data.get("pnx", {})
        display = pnx.get("display", {})
        addata = pnx.get("addata", {})

        isbns = addata.get("isbn", [])
        cover_url = await self.get_cover_url(isbns)

        original_title = None
        if "addtitle" in display:
            for title in display["addtitle"]:
                if title.startswith("Tytuł oryginału:"):
                    original_title = title.replace("Tytuł oryginału:", "").strip()
                    break

        return BookDetails(
            mmsid=mmsid,
            cover_url=cover_url,
            isbns=isbns,
            publisher=display.get("publisher", [None])[0],
            publication_date=display.get("creationdate", [None])[0],
            subjects=display.get("subject", []),
            genres=display.get("genre", []),
            physical_description=display.get("format", [None])[0],
            original_title=original_title,
        )

    async def get_personal_settings(self) -> Dict[str, Any]:
        """Fetch full personal details (address, email, etc.)."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/primaws/rest/priv/myaccount/personal_settings"
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await self.client.get(url, params={"lang": "pl"}, headers=headers)
        response.raise_for_status()
        return response.json().get("data", {})

    async def get_fines(self) -> List[Fine]:
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/primaws/rest/priv/myaccount/fines"
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await self.client.get(url, params={"lang": "pl"}, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", {})
        fines_data = data.get("fines", {}).get("fine", [])
        return [Fine.from_api(f) for f in fines_data]

    async def get_requests(self) -> List[RequestItem]:
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/primaws/rest/priv/myaccount/requests"
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await self.client.get(url, params={"lang": "pl"}, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", {})

        items: List[RequestItem] = []
        for plural, singular in (
            ("holds", "hold"),
            ("photocopies", "photocopy"),
            ("bookings", "booking"),
            ("cdls", "cdl"),
            ("ills", "ill"),
            ("acqs", "acq"),
        ):
            for entry in data.get(plural, {}).get(singular, []) or []:
                hold = None
                if singular == "hold":
                    try:
                        hold = Hold.from_api(entry)
                    except ValidationError:
                        hold = None
                items.append(RequestItem(category=singular, raw=entry, hold=hold))
        return items

    async def renew_loan(self, loan_id: str) -> Dict[str, Any]:
        if not self.token:
            raise ValueError("Not logged in")

        renew_url = f"{self.base_url}/primaws/rest/priv/myaccount/renew_loans"
        params = {"lang": "pl"}
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json;charset=UTF-8"}
        data = {"id": loan_id}

        response = await self.client.post(renew_url, params=params, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    async def cancel_hold(self, request_id: str) -> Dict[str, Any]:
        """Cancel a hold. Endpoint/payload shape captured live from the browser's own
        cancel action (see curls/anulowanie) rather than guessed from convention:
        `request_type` is "holds" (the plural category key), not "hold". Success response
        (verified live): `{"status": "ok", "reply-code": "0000", "reply-text": "OK",
        "data": {"holds": {"hold": [{"requestid": ..., "note": {"type": "info"}}]}}}`."""
        if not self.token:
            raise ValueError("Not logged in")

        cancel_url = f"{self.base_url}/primaws/rest/priv/myaccount/cancel_requests"
        params = {"lang": "pl"}
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json;charset=UTF-8"}
        data = {"request_id": request_id, "request_type": "holds"}

        response = await self.client.post(cancel_url, params=params, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        _raise_for_primo_failure(result)
        return result

    def _build_search_params(
        self, q: str, qInclude: str = "", sort: str = "rank", limit: int = 10, came_from: Optional[str] = None
    ) -> Dict[str, str]:
        params = {
            "acTriggered": "false",
            "blendFacetsSeparately": "false",
            "citationTrailFilterByAvailability": "true",
            "disableCache": "false",
            "getMore": "0",
            "inst": self.institution or "",
            "isCDSearch": "false",
            "lang": "pl",
            "limit": str(limit),
            "newspapersActive": "false",
            "newspapersSearch": "false",
            "offset": "0",
            "otbRanking": "false",
            "pcAvailability": "true",
            "q": f"any,contains,{q}",
            "qExclude": "",
            "qInclude": qInclude,
            "rapido": "false",
            "refEntryActive": "false",
            "rtaLinks": "true",
            "scope": "MyInstitution2",
            "searchInFulltextUserSelection": "true",
            "skipDelivery": "Y",
            "sort": sort,
            "tab": "LibraryCatalog",
            "vid": self.view or "",
        }
        if came_from:
            params["came_from"] = came_from
        return params

    async def _pnxs_search(self, params: Dict[str, str]) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = await self.client.get(f"{self.base_url}/primaws/rest/pub/pnxs", params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _pnxs_delivery(self, params: Dict[str, str], alma_ids: List[str]) -> List[Dict[str, Any]]:
        if not alma_ids:
            return []
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = await self.client.post(
            f"{self.base_url}/primaws/rest/pub/delivery", params=params, headers=headers, json=alma_ids
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _display_first(doc: Dict[str, Any], field: str) -> Optional[str]:
        values = doc.get("pnx", {}).get("display", {}).get(field)
        return values[0] if values else None

    @staticmethod
    def _addata_first(doc: Dict[str, Any], field: str) -> Optional[str]:
        values = doc.get("pnx", {}).get("addata", {}).get(field)
        return values[0] if values else None

    @staticmethod
    def _extract_frbrgroupid(doc: Dict[str, Any]) -> Optional[str]:
        values = doc.get("pnx", {}).get("facets", {}).get("frbrgroupid")
        return values[0] if values else None

    @staticmethod
    def _alma_id(doc: Dict[str, Any]) -> Optional[str]:
        values = doc.get("pnx", {}).get("control", {}).get("recordid")
        return values[0] if values else None

    @staticmethod
    def _bare_mmsid(doc: Dict[str, Any]) -> str:
        values = doc.get("pnx", {}).get("control", {}).get("sourcerecordid")
        if values:
            return values[0]
        alma_id = OmnisClient._alma_id(doc)
        if alma_id and alma_id.startswith("alma"):
            return alma_id[4:]
        return alma_id or ""

    async def _get_physical_service_id(self, bare_mmsid: str) -> Optional[str]:
        params = {
            "vid": self.view or "",
            "lang": "pl",
            "recordOwner": "48OMNIS_NETWORK",
            "sourceRecordId": bare_mmsid,
            "resource_type": "book",
            "isRapido": "false",
        }
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = await self.client.get(
                f"{self.base_url}/primaws/rest/pub/getPhysicalService/{bare_mmsid}", params=params, headers=headers
            )
            response.raise_for_status()
            return response.json().get("physicalServiceId")
        except httpx.HTTPError:
            return None

    async def _post_holdings(
        self, bare_mmsid: str, holding: Dict[str, Any], physical_service_id: str
    ) -> Dict[str, Any]:
        """Fetch item-level detail for a single branch holding. `locations` must contain
        only that one holding (with its `holKey`) — see CLAUDE.md."""
        main_location = holding.get("mainLocation", "")
        body = {
            "filters": {
                "noItem": 10,
                "sublibrary": main_location,
                "collection": "",
                "callnumber": "",
                "holid": holding.get("holdId", ""),
                "sublibs": main_location,
                "ilsRecordList": [{"institution": self.institution, "recordId": bare_mmsid}],
                "vid": self.view,
                "filterCall": True,
            },
            "locations": [holding],
            "hideResourceSharing": False,
        }
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = await self.client.post(
            f"{self.base_url}/primaws/rest/priv/ILSServices/holdings/{physical_service_id}",
            params={"record-institution": self.institution, "lang": "pl"},
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()

    async def _get_due_date_for_holding(
        self, bare_mmsid: str, holding: Dict[str, Any], physical_service_id: str
    ) -> Optional[Tuple[Optional[str], bool]]:
        """Fetch item-level status for a single branch holding to extract its due date, if any."""
        try:
            data = await self._post_holdings(bare_mmsid, holding, physical_service_id)
        except httpx.HTTPError:
            return None

        for loc in data.get("data", {}).get("itemInfo", {}).get("locations", []):
            for item in loc.get("items", []):
                status_name = item.get("itemstatusname", "")
                match = re.search(r"(\d{2}/\d{2}/\d{4})", status_name)
                if match:
                    overdue = "przekroczon" in status_name.lower()
                    return match.group(1), overdue
        return None, False

    async def search_books(
        self, query: str, limit: int = 10, branch_filter: Optional[str] = None, fetch_due_dates: bool = True
    ) -> List[SearchResult]:
        """Search the catalog by title/keyword.

        A single title (frbrgroupid) can have multiple editions/versions; all are fetched and
        kept distinguished under one SearchResult. Availability is resolved per branch, and for
        branches that are currently unavailable, the due date is fetched separately since Primo
        only exposes it at the individual-item level.
        """
        if not self.token:
            raise ValueError("Not logged in")

        top_params = self._build_search_params(query, limit=limit)
        top_data = await self._pnxs_search(top_params)
        top_docs = top_data.get("docs", [])

        async def resolve_versions_with_delivery(
            doc: Dict[str, Any],
        ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
            # The delivery endpoint re-runs its own search internally using the given query
            # params (q/qInclude/sort) and only reports on ids that fall within that same
            # result page, so it must be called once per distinct query variant (i.e. once
            # per version-group), using that group's own params and doc ids.
            frbrgroupid = self._extract_frbrgroupid(doc)
            if frbrgroupid:
                # A work's edition count is independent of how many distinct works the
                # top-level search returned, so use a generously high fixed limit here
                # rather than the (often much smaller) top-level `limit`.
                group_params = self._build_search_params(
                    query,
                    qInclude=f"facet_frbrgroupid,exact,{frbrgroupid}",
                    sort="date_d",
                    limit=50,
                    came_from="addFacet",
                )
                group_data = await self._pnxs_search(group_params)
                version_docs = group_data.get("docs", []) or [doc]
                delivery_query_params = group_params
            else:
                version_docs = [doc]
                delivery_query_params = top_params

            alma_ids = list(dict.fromkeys(i for i in (self._alma_id(d) for d in version_docs) if i))
            delivery_by_id: Dict[str, Dict[str, Any]] = {}
            if alma_ids:
                delivery_items = await self._pnxs_delivery(delivery_query_params, alma_ids)
                for item in delivery_items:
                    rid = self._alma_id(item)
                    if rid:
                        delivery_by_id[rid] = item

            return version_docs, delivery_by_id

        resolved = await asyncio.gather(*(resolve_versions_with_delivery(doc) for doc in top_docs))
        versions_per_work = [r[0] for r in resolved]
        delivery_maps_per_work = [r[1] for r in resolved]

        branch_filter_lower = branch_filter.lower() if branch_filter else None
        enrich_targets: List[Tuple[BranchAvailability, str, Dict[str, Any]]] = []
        results: List[SearchResult] = []

        for doc, versions, delivery_by_id in zip(top_docs, versions_per_work, delivery_maps_per_work):
            frbrgroupid = self._extract_frbrgroupid(doc)
            title = self._addata_first(doc, "btitle") or self._display_first(doc, "title") or "Unknown"
            author = self._addata_first(doc, "au")

            book_versions: List[BookVersion] = []
            for v in versions:
                alma_id = self._alma_id(v)
                delivery_item = delivery_by_id.get(alma_id, {}) if alma_id else {}
                delivery_data = delivery_item.get("delivery") or {}
                holdings = delivery_data.get("holding") or []
                other_institutions = [
                    OtherInstitution(code=inst.get("instCode", ""), name=inst.get("instName", ""))
                    for inst in delivery_data.get("almaInstitutionsList") or []
                ]

                branches: List[BranchAvailability] = []
                for h in holdings:
                    main_location = h.get("mainLocation", "")
                    if branch_filter_lower and branch_filter_lower not in main_location.lower():
                        continue
                    branch = BranchAvailability(
                        library_name=main_location,
                        library_code=h.get("libraryCode", ""),
                        sub_location=h.get("subLocation"),
                        maps_url=h.get("stackMapUrl"),
                        status=h.get("availabilityStatus", "unknown"),
                    )
                    branches.append(branch)
                    if fetch_due_dates and branch.status == "unavailable":
                        bare_mmsid = self._bare_mmsid(v)
                        enrich_targets.append((branch, bare_mmsid, h))

                if branch_filter_lower and not branches:
                    continue

                book_versions.append(
                    BookVersion(
                        mmsid=self._bare_mmsid(v),
                        title=self._display_first(v, "title") or title,
                        author=self._addata_first(v, "au") or author,
                        edition=self._display_first(v, "edition"),
                        publisher=self._addata_first(v, "pub"),
                        publication_date=self._addata_first(v, "date"),
                        isbns=v.get("pnx", {}).get("addata", {}).get("isbn", []),
                        frbrgroupid=frbrgroupid,
                        series=self._addata_first(v, "seriestitle"),
                        genres=v.get("pnx", {}).get("display", {}).get("genre", []),
                        subjects=v.get("pnx", {}).get("display", {}).get("subject", []),
                        language=self._display_first(v, "language"),
                        physical_description=self._display_first(v, "format"),
                        resource_type=self._display_first(v, "type"),
                        branches=branches,
                        other_institutions=other_institutions,
                    )
                )

            if branch_filter_lower and not book_versions:
                continue

            results.append(SearchResult(frbrgroupid=frbrgroupid, title=title, author=author, versions=book_versions))

        if enrich_targets:
            unique_mmsids = list(dict.fromkeys(m for _, m, _ in enrich_targets))
            service_ids = await asyncio.gather(*(self._get_physical_service_id(m) for m in unique_mmsids))
            service_id_map = dict(zip(unique_mmsids, service_ids))

            async def enrich(branch: BranchAvailability, bare_mmsid: str, holding: Dict[str, Any]) -> None:
                service_id = service_id_map.get(bare_mmsid)
                if not service_id:
                    return
                result = await self._get_due_date_for_holding(bare_mmsid, holding, service_id)
                if result:
                    due_date, overdue = result
                    branch.due_date = due_date
                    branch.overdue = overdue

            await asyncio.gather(*(enrich(b, m, h) for b, m, h in enrich_targets))

        return results

    async def _resolve_record_holdings(self, mmsid: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Find the local catalog record for `mmsid` and its per-branch `delivery` holdings.

        Searching by the id itself works for both local (`...9337`) and network-zone
        (`...5606`, as `myaccount/requests` reports them) MMS ids — but a network-zone id
        resolves to a *different* local record id, so callers must continue with the
        returned doc's id, not the one passed in. `delivery` is called with the very same
        search params, per the batching gotcha documented in CLAUDE.md.
        """
        mmsid = mmsid.removeprefix("alma")
        params = self._build_search_params(mmsid, limit=10)
        docs = (await self._pnxs_search(params)).get("docs", [])
        exact = [d for d in docs if self._bare_mmsid(d) == mmsid]
        if exact:
            doc = exact[0]
        elif len(docs) == 1:
            doc = docs[0]
        elif not docs:
            raise ValueError(f"No catalog record found for MMS ID {mmsid}")
        else:
            raise ValueError(f"MMS ID {mmsid} matched {len(docs)} records; use the local id from --search")

        alma_id = self._alma_id(doc)
        holdings: List[Dict[str, Any]] = []
        if alma_id:
            for item in await self._pnxs_delivery(params, [alma_id]):
                if self._alma_id(item) == alma_id:
                    holdings = (item.get("delivery") or {}).get("holding") or []
        return doc, holdings

    async def get_holdable_items(self, mmsid: str, branch_filter: Optional[str] = None) -> List[HoldableItem]:
        """List physical copies of a record that can be requested (held), across branches.

        `branch_filter` is a case-insensitive substring match on the branch name, like
        `search_books`'s. Only items whose `AlmaItemRequest` service is `allowed: "Y"`
        are returned."""
        if not self.token:
            raise ValueError("Not logged in")

        doc, holdings = await self._resolve_record_holdings(mmsid)
        bare_mmsid = self._bare_mmsid(doc)
        title = self._display_first(doc, "title")
        original_ids = doc.get("pnx", {}).get("control", {}).get("originalsourceid") or []
        network_mmsid = original_ids[0] if original_ids else None
        branch_filter_lower = branch_filter.lower() if branch_filter else None
        holdings = [
            h for h in holdings if not branch_filter_lower or branch_filter_lower in h.get("mainLocation", "").lower()
        ]
        if not holdings:
            return []

        # physicalServiceId is session-scoped (observed to change between logins), so it
        # is always fetched fresh rather than cached.
        service_id = await self._get_physical_service_id(bare_mmsid)
        if not service_id:
            raise ValueError(f"No physical service available for MMS ID {bare_mmsid}")

        responses = await asyncio.gather(*(self._post_holdings(bare_mmsid, h, service_id) for h in holdings))

        items: List[HoldableItem] = []
        for data in responses:
            for loc in data.get("data", {}).get("itemInfo", {}).get("locations", []):
                for item in loc.get("items", []):
                    services = item.get("listofservices", {}).get("service", []) or []
                    request_service = next(
                        (
                            s
                            for s in services
                            if s.get("type") == "AlmaItemRequest"
                            and s.get("allowed") == "Y"
                            and s.get("link-to-service")
                        ),
                        None,
                    )
                    if not request_service or not item.get("itemid"):
                        continue
                    items.append(
                        HoldableItem(
                            mmsid=item.get("mmsid") or bare_mmsid,
                            item_id=item["itemid"],
                            request_path=request_service["link-to-service"],
                            network_mmsid=network_mmsid,
                            title=title,
                            barcode=item.get("itembarcode"),
                            status_name=item.get("itemstatusname"),
                            category=item.get("itemcategoryname"),
                            policy=item.get("itempolicy"),
                            material=item.get("itemmaterial"),
                            call_number=item.get("callnumber2"),
                            main_location=item.get("mainlocationname") or loc.get("main-location"),
                            sub_location=item.get("secondarylocationname") or loc.get("sub-location"),
                        )
                    )
        return items

    def _item_request_url(self, item: HoldableItem) -> Tuple[str, Dict[str, str]]:
        # `request_path` is Primo's own link-to-service, already carrying
        # institution/hasHold/hasBooking as query params; reuse it instead of rebuilding.
        url = httpx.URL(f"{self.base_url}{item.request_path}")
        params = dict(url.params)
        params["lang"] = "pl"
        return str(url.copy_with(query=None)), params

    async def get_hold_options(self, item: HoldableItem) -> HoldRequestOptions:
        """Fetch the hold request form for one item: request type, material type and the
        pickup locations Primo offers (read-only, verified live)."""
        if not self.token:
            raise ValueError("Not logged in")

        url, params = self._item_request_url(item)
        # Same extra params the Primo UI sends when opening the form.
        params.update(
            {
                "itemcategoryname": item.category or "",
                "itemid": item.item_id,
                "itemstatusname": item.status_name or "",
                "mainlocationname": item.main_location or "",
                "secondarylocationname": item.sub_location or "",
                "vid": self.view or "",
            }
        )
        response = await self.client.get(url, params=params, headers={"Authorization": f"Bearer {self.token}"})
        response.raise_for_status()
        services = response.json().get("services-arr", {}).get("services", [])

        for service in services:
            for group in service.get("groups-list-map", []) or []:
                request_type = group.get("requestType") or "hold"
                if request_type != "hold":
                    continue
                pickups = [
                    PickupLocation.from_key(p["key"], p.get("value", ""))
                    for p in group.get("pickupLocation", []) or []
                    if p.get("key")
                ]
                material_type = (group.get("materialType") or {}).get("key")
                if not material_type:
                    raise ValueError("Hold request form has no material type")
                return HoldRequestOptions(
                    item=item, request_type=request_type, material_type=material_type, pickup_locations=pickups
                )
        raise ValueError(f"Item {item.item_id} offers no hold request option")

    async def place_hold(self, options: HoldRequestOptions, pickup: PickupLocation) -> Dict[str, Any]:
        """Place a hold on `options.item`, to be picked up at `pickup` (one of
        `options.pickup_locations`).

        Request shape captured from the Primo UI's own submit (`curls/zamowienie`). A
        successful response (verified live) is only the envelope
        `{"beaconO22": ..., "reply-text": "ok", "status": "ok"}` — no request ID — and the
        new hold appears in `get_requests()` with a delay of a few seconds, so callers
        needing the request ID must poll for it. Failure envelopes raise `ValueError`."""
        if not self.token:
            raise ValueError("Not logged in")

        url, params = self._item_request_url(options.item)
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json;charset=UTF-8"}
        data = {
            "requestType": options.request_type,
            "pickupLocation": pickup.id,
            "materialType": options.material_type,
            "itemId": options.item.item_id,
            "group_id": options.item.mmsid,
            "pickupLibraryId": pickup.id,
            "pickupType": pickup.type,
        }
        response = await self.client.post(url, params=params, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        _raise_for_primo_failure(result)
        return result

    async def get_item_queue(self, item_id: str) -> Optional[str]:
        """Human-readable hold queue for one item, e.g. `"(zamówienie: 1)"`."""
        if not self.token:
            raise ValueError("Not logged in")

        response = await self.client.get(
            f"{self.base_url}/primaws/rest/priv/ILSServices/itemQueue/{item_id}",
            params={"record-institution": self.institution or "", "lang": "pl"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        response.raise_for_status()
        return response.json().get("itemQueueString")

    async def close(self):
        if self._close_client:
            await self.client.aclose()
