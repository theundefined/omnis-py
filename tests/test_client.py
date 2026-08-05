import pytest
import respx
from omnis.client import OmnisClient


def _doc(
    recordid,
    sourcerecordid,
    title,
    btitle,
    au,
    edition,
    date,
    pub,
    isbn,
    frbrgroupid,
    seriestitle=None,
    genre=None,
    subject=None,
    language=None,
):
    return {
        "pnx": {
            "display": {
                "title": [title],
                "edition": [edition] if edition else [],
                "genre": genre or [],
                "subject": subject or [],
                "language": [language] if language else [],
            },
            "addata": {
                "btitle": [btitle],
                "au": [au],
                "pub": [pub],
                "date": [date],
                "isbn": [isbn] if isbn else [],
                "seriestitle": [seriestitle] if seriestitle else [],
            },
            "control": {"recordid": [recordid], "sourcerecordid": [sourcerecordid]},
            "facets": {"frbrgroupid": [frbrgroupid]} if frbrgroupid else {},
        }
    }


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


@pytest.mark.asyncio
async def test_search_books_groups_versions_and_resolves_due_dates():
    client = OmnisClient()
    client.token = "fake.token.fake"
    client.view = "48OMNIS_BRP:BRACZ"
    client.institution = "48OMNIS_BRP"

    top_doc = _doc(
        "almaTOP1",
        "TOP1",
        "Płomień i krzyż / Jacek Piekara.",
        "Płomień i krzyż",
        "Piekara, Jacek",
        "Wydanie III.",
        "2012",
        "Fabryka Słów",
        "9788375747775",
        "GROUP1",
    )
    version_old = _doc(
        "almaOLD1",
        "OLD1",
        "Płomień i krzyż / Jacek Piekara.",
        "Płomień i krzyż",
        "Piekara, Jacek",
        "Wydanie I.",
        "2008",
        "Fabryka Słów",
        "9788375740011",
        "GROUP1",
    )
    version_new = _doc(
        "almaTOP1",
        "TOP1",
        "Płomień i krzyż / Jacek Piekara.",
        "Płomień i krzyż",
        "Piekara, Jacek",
        "Wydanie III.",
        "2012",
        "Fabryka Słów",
        "9788375747775",
        "GROUP1",
    )

    def holding(main_location, library_code, hold_id, status):
        return {
            "mainLocation": main_location,
            "libraryCode": library_code,
            "subLocation": "Some address",
            "stackMapUrl": "https://maps.app.goo.gl/fake",
            "availabilityStatus": status,
            "holdId": hold_id,
        }

    delivery_response = [
        {"pnx": version_new["pnx"], "delivery": {"holding": [holding("Filia 01", "F01", "H1", "available")]}},
        {
            "pnx": version_old["pnx"],
            "delivery": {"holding": [holding("BG - Wypożyczalnia", "WYPOZ", "H2", "unavailable")]},
        },
    ]

    with respx.mock:
        respx.get(
            "https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/pnxs",
            params={"qInclude": ""},
        ).respond(200, json={"docs": [top_doc]})
        respx.get(
            "https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/pnxs",
            params={"qInclude": "facet_frbrgroupid,exact,GROUP1"},
        ).respond(200, json={"docs": [version_new, version_old]})
        delivery_route = respx.post("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/delivery").respond(
            200, json=delivery_response
        )
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/getPhysicalService/OLD1").respond(
            200, json={"physicalServiceId": "PS123"}
        )
        respx.post("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/ILSServices/holdings/PS123").respond(
            200,
            json={
                "data": {
                    "itemInfo": {
                        "locations": [
                            {"items": [{"itemstatusname": "Wypożyczony - termin zwrotu przekroczony od 20/03/2026"}]}
                        ]
                    }
                }
            },
        )

        results = await client.search_books("płomień i krzyż")

    # The delivery endpoint re-runs its own search using the given q/qInclude/sort and only
    # reports on ids within that result page, so it must be called once per version-group
    # with that group's own params — never once with every id batched under top-level params.
    assert delivery_route.call_count == 1
    assert delivery_route.calls[0].request.url.params["qInclude"] == "facet_frbrgroupid,exact,GROUP1"

    assert len(results) == 1
    result = results[0]
    assert result.title == "Płomień i krzyż"
    assert len(result.versions) == 2

    by_mmsid = {v.mmsid: v for v in result.versions}
    assert by_mmsid["TOP1"].edition == "Wydanie III."
    assert by_mmsid["TOP1"].branches[0].status == "available"
    assert by_mmsid["TOP1"].branches[0].due_date is None
    assert by_mmsid["TOP1"].branches[0].sub_location == "Some address"
    assert by_mmsid["TOP1"].branches[0].maps_url == "https://maps.app.goo.gl/fake"

    assert by_mmsid["OLD1"].edition == "Wydanie I."
    unavailable_branch = by_mmsid["OLD1"].branches[0]
    assert unavailable_branch.status == "unavailable"
    assert unavailable_branch.due_date == "20/03/2026"
    assert unavailable_branch.overdue is True


@pytest.mark.asyncio
async def test_search_books_branch_filter_drops_non_matching_versions():
    client = OmnisClient()
    client.token = "fake.token.fake"
    client.view = "48OMNIS_BRP:BRACZ"
    client.institution = "48OMNIS_BRP"

    top_doc = _doc("almaX1", "X1", "Some Book.", "Some Book", "An Author", None, "2020", "Pub", "111", None)

    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/pnxs").respond(
            200, json={"docs": [top_doc]}
        )
        respx.post("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/delivery").respond(
            200,
            json=[
                {
                    "pnx": top_doc["pnx"],
                    "delivery": {
                        "holding": [
                            {"mainLocation": "Filia 01", "libraryCode": "F01", "availabilityStatus": "available"},
                            {"mainLocation": "Filia 02", "libraryCode": "F02", "availabilityStatus": "available"},
                        ]
                    },
                }
            ],
        )

        results = await client.search_books("some book", branch_filter="Filia 02", fetch_due_dates=False)

    assert len(results) == 1
    assert len(results[0].versions) == 1
    assert len(results[0].versions[0].branches) == 1
    assert results[0].versions[0].branches[0].library_name == "Filia 02"


@pytest.mark.asyncio
async def test_search_books_captures_series_and_subject_metadata():
    client = OmnisClient()
    client.token = "fake.token.fake"
    client.view = "48OMNIS_BRP:BRACZ"
    client.institution = "48OMNIS_BRP"

    top_doc = _doc(
        "almaY1",
        "Y1",
        "Kościany Galeon / Jacek Piekara.",
        "Kościany Galeon",
        "Piekara, Jacek",
        None,
        "2015",
        "Fabryka Słów",
        "9788379640157",
        None,
        seriestitle="Ja, inkwizytor / Jacek Piekara",
        genre=["Fantastyka", "Powieść"],
        subject=["Mordimer Madderdin (postać fikcyjna)", "Inkwizycja"],
        language="pol",
    )

    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/pnxs").respond(
            200, json={"docs": [top_doc]}
        )
        respx.post("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/pub/delivery").respond(200, json=[])

        results = await client.search_books("kościany galeon", fetch_due_dates=False)

    assert len(results) == 1
    version = results[0].versions[0]
    assert version.series == "Ja, inkwizytor / Jacek Piekara"
    assert version.genres == ["Fantastyka", "Powieść"]
    assert version.subjects == ["Mordimer Madderdin (postać fikcyjna)", "Inkwizycja"]
    assert version.language == "pol"


@pytest.mark.asyncio
async def test_search_books_requires_login():
    client = OmnisClient()
    with pytest.raises(ValueError):
        await client.search_books("anything")


@pytest.mark.asyncio
async def test_get_fines_parses_polish_amount_format():
    # Shape verified live against a real account (docs/plans/account-actions-api.md);
    # amounts use a comma decimal + trailing currency, unlike myaccount/counters' "0.00".
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/fines").respond(
            200,
            json={
                "data": {
                    "fines": {
                        "fine": [
                            {
                                "fineid": "44652750980009337",
                                "finestatus": "CLOSED",
                                "finesum": "0,00 PLN",
                                "originalfinesum": "0,20 PLN",
                                "finedate": "20260515",
                                "finemainlocation": "Filia 35",
                                "title": "Kocia mowa",
                                "type": "debit",
                                "description": "Opłata za przetrzymanie",
                                "isAlert": False,
                            }
                        ]
                    }
                }
            },
        )

        fines = await client.get_fines()

    assert len(fines) == 1
    assert fines[0].amount == 0.0
    assert fines[0].original_amount == 0.2
    assert fines[0].currency == "PLN"
    assert fines[0].status == "CLOSED"


@pytest.mark.asyncio
async def test_get_fines_empty_account_returns_empty_list():
    # Accounts with no fines return data={} entirely (no "fines" key), not an empty list.
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/fines").respond(
            200, json={"data": {}}
        )

        fines = await client.get_fines()

    assert fines == []


@pytest.mark.asyncio
async def test_get_fines_requires_login():
    client = OmnisClient()
    with pytest.raises(ValueError):
        await client.get_fines()


@pytest.mark.asyncio
async def test_get_requests_empty_account_returns_empty_list():
    # Top-level shape (holds/photocopies/bookings/cdls/ills/acqs) verified live;
    # no family account currently has an active hold to verify per-item fields against.
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/requests").respond(
            200,
            json={
                "data": {
                    "holds": {"hold": []},
                    "photocopies": {"photocopy": []},
                    "bookings": {"booking": []},
                    "cdls": {"cdl": []},
                    "ills": {"ill": []},
                    "acqs": {"acq": []},
                }
            },
        )

        requests = await client.get_requests()

    assert requests == []


@pytest.mark.asyncio
async def test_get_requests_tags_items_by_category_and_preserves_raw():
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/requests").respond(
            200,
            json={
                "data": {
                    "holds": {"hold": [{"some": "unverified-field"}]},
                    "ills": {"ill": [{"another": "field"}]},
                }
            },
        )

        requests = await client.get_requests()

    assert len(requests) == 2
    assert requests[0].category == "hold"
    assert requests[0].raw == {"some": "unverified-field"}
    assert requests[1].category == "ill"
    assert requests[1].raw == {"another": "field"}


@pytest.mark.asyncio
async def test_get_requests_requires_login():
    client = OmnisClient()
    with pytest.raises(ValueError):
        await client.get_requests()
