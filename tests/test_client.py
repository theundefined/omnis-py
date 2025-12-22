import pytest
import respx
from omnis.client import OmnisClient


@pytest.mark.asyncio
async def test_login_success():
    client = OmnisClient()
    with respx.mock:
        # Initial search request
        respx.get("https://omnis-br.primo.exlibrisgroup.com/discovery/search").respond(200)
        # Login request
        respx.post("https://omnis-br.primo.exlibrisgroup.com/primaws/suprimaLogin").respond(
            200,
            json={
                "jwtData": '"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkaXNwbGF5TmFtZSI6IlRlc3QgVXNlciIsInVzZXJOYW1lIjoidGVzdHVzZXIifQ.signature"'
            },
        )

        token = await client.login("user", "pass")
        assert token.startswith("eyJ")
        assert client.token == token


@pytest.mark.asyncio
async def test_get_loans_success():
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/loans").respond(
            200,
            json={
                "data": {
                    "loans": {
                        "loan": [
                            {
                                "loanid": "123",
                                "mmsid": "mms1",
                                "title": "Test Book",
                                "author": "Test Author",
                                "duedate": "20240101",
                                "duehour": "2359",
                                "loandate": "20231201",
                                "loanstatus": "Active",
                                "ilsinstitutionname": "Library",
                                "mainlocationname": "Branch",
                                "itembarcode": "123456",
                                "renew": "Y",
                            }
                        ]
                    }
                }
            },
        )

        loans = await client.get_loans()
        assert len(loans) == 1
        assert loans[0].title == "Test Book"
        assert loans[0].renewable is True
