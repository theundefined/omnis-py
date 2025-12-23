import httpx
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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


class UserInfo(BaseModel):
    display_name: str
    user_name: str
    loans_count: int = 0
    requests_count: int = 0
    fines_amount: float = 0.0
    fines_currency: str = "PLN"


class OmnisClient:
    def __init__(
        self,
        base_url: str = "https://omnis-br.primo.exlibrisgroup.com",
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = base_url
        if client:
            self.client = client
            self._close_client = False
        else:
            self.client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
            self._close_client = True

        self.token: Optional[str] = None
        self.user_data: Dict[str, Any] = {}

    async def login(
        self, username: str, password: str, institution: str = "48OMNIS_BRP", view: str = "48OMNIS_BRP:BRACZ"
    ):
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

    async def get_loans(self) -> List[Loan]:
        if not self.token:
            raise ValueError("Not logged in")

        loans_url = f"{self.base_url}/primaws/rest/priv/myaccount/loans"
        params = {
            "bulk": "50",
            "lang": "pl",
            "offset": "1",
            "type": "active",
        }
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await self.client.get(loans_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        loans_list = data.get("data", {}).get("loans", {}).get("loan", [])
        return [Loan.from_api(loan_data) for loan_data in loans_list]

    async def get_personal_settings(self) -> Dict[str, Any]:
        """Fetch full personal details (address, email, etc.)."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/primaws/rest/priv/myaccount/personal_settings"
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await self.client.get(url, params={"lang": "pl"}, headers=headers)
        response.raise_for_status()
        return response.json().get("data", {})

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

    async def close(self):
        if self._close_client:
            await self.client.aclose()
