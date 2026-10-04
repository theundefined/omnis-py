import json

import httpx
import pytest
import respx
from omnis.client import HoldableItem, HoldRequestOptions, OmnisClient, PickupLocation


def test_client_default_timeout_is_30():
    client = OmnisClient()
    assert client.client.timeout == httpx.Timeout(30.0)


def test_client_custom_timeout_applied():
    client = OmnisClient(timeout=60.0)
    assert client.client.timeout == httpx.Timeout(60.0)


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
        {
            "pnx": version_new["pnx"],
            "delivery": {
                "holding": [holding("Filia 01", "F01", "H1", "available")],
                "almaInstitutionsList": [
                    {"instCode": "48OMNIS_NLOP", "instName": "Biblioteka Narodowa", "instId": "5066", "envURL": ""},
                    {"instCode": "48OMNIS_UJA", "instName": "Uniwersytet Jagielloński", "instId": "5067", "envURL": ""},
                ],
            },
        },
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
    assert [(i.code, i.name) for i in by_mmsid["TOP1"].other_institutions] == [
        ("48OMNIS_NLOP", "Biblioteka Narodowa"),
        ("48OMNIS_UJA", "Uniwersytet Jagielloński"),
    ]

    assert by_mmsid["OLD1"].edition == "Wydanie I."
    unavailable_branch = by_mmsid["OLD1"].branches[0]
    assert unavailable_branch.status == "unavailable"
    assert unavailable_branch.due_date == "20/03/2026"
    assert unavailable_branch.overdue is True
    # No almaInstitutionsList key at all in this holding's delivery response -
    # must default to an empty list, not raise.
    assert by_mmsid["OLD1"].other_institutions == []


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
    assert requests[0].hold is None  # doesn't match the verified Hold shape, falls back to raw
    assert requests[1].category == "ill"
    assert requests[1].raw == {"another": "field"}


@pytest.mark.asyncio
async def test_get_requests_parses_hold_shape():
    # Shape verified live against a real account with an active hold (see
    # docs/plans/account-actions-api.md) — "Y"/"N" flags convert to bool.
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get("https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/requests").respond(
            200,
            json={
                "data": {
                    "holds": {
                        "hold": [
                            {
                                "cancel": "Y",
                                "ilsinstitutionname": "Sprawdź dostępność w innych bibliotekach",
                                "ilsinstitutioncode": "48OMNIS_NETWORK",
                                "mmsid": "9910805835105606",
                                "title": "Przykładowa książka",
                                "author": "Testowy, Autor",
                                "pickuplocationname": "Filia 01",
                                "available": "N",
                                "requestid": "45519739360009337",
                                "requestdate": "20260808",
                                "holdstatus": "W realizacji",
                            }
                        ]
                    }
                }
            },
        )

        requests = await client.get_requests()

    assert len(requests) == 1
    hold = requests[0].hold
    assert hold is not None
    assert hold.title == "Przykładowa książka"
    assert hold.status == "W realizacji"
    assert hold.pickup_location == "Filia 01"
    assert hold.available is False
    assert hold.cancellable is True


@pytest.mark.asyncio
async def test_get_requests_requires_login():
    client = OmnisClient()
    with pytest.raises(ValueError):
        await client.get_requests()


# Verified live 2026-10-04.
CANCEL_OK = {
    "beaconO22": "646",
    "status": "ok",
    "reply-code": "0000",
    "reply-text": "OK",
    "data": {"holds": {"hold": [{"requestid": "45519739360009337", "note": {"type": "info"}}]}},
}


@pytest.mark.asyncio
async def test_cancel_hold_sends_verified_payload():
    # Endpoint/payload captured live from the browser's own cancel action (curls/anulowanie):
    # request_type is "holds" (plural category key), not "hold".
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        route = respx.post(
            "https://omnis-br.primo.exlibrisgroup.com/primaws/rest/priv/myaccount/cancel_requests"
        ).respond(200, json=CANCEL_OK)

        result = await client.cancel_hold("45519739360009337")

    assert route.called
    sent_request = route.calls.last.request
    assert json.loads(sent_request.content) == {"request_id": "45519739360009337", "request_type": "holds"}
    assert result == CANCEL_OK


@pytest.mark.asyncio
async def test_cancel_hold_requires_login():
    client = OmnisClient()
    with pytest.raises(ValueError):
        await client.cancel_hold("45519739360009337")


# --- placing holds (shape from curls/zamowienie; all ids/titles below are invented) ---

BASE = "https://omnis-br.primo.exlibrisgroup.com"
LOCAL_MMS = "991000000000009337"
NZ_MMS = "991000000000005606"
ITEM_ID = "23800000000009337"
SERVICE_ID = "46000000000009337"
REQUEST_PATH = (
    f"/primaws/rest/priv/ILSServices/itemServices/{LOCAL_MMS}/item/{ITEM_ID}/{SERVICE_ID}/AlmaItemRequest"
    "?institution=48OMNIS_BRP&hasHold=true&hasBooking=false"
)


def _holding(branch, library_id):
    return {
        "mainLocation": branch,
        "subLocation": "ul. Przykładowa 1",
        "availabilityStatus": "available",
        "holdId": f"228{library_id}",
        "holKey": f"HoldingResultKey [mid=228{library_id}, libraryId={library_id}, locationCode=X, callNumber=null]",
    }


def _holdings_response(branch, allowed="Y"):
    return {
        "data": {
            "itemInfo": {
                "locations": [
                    {
                        "main-location": branch,
                        "sub-location": "ul. Przykładowa 1",
                        "items": [
                            {
                                "itemid": ITEM_ID,
                                "mmsid": LOCAL_MMS,
                                "itemstatusname": "Egzemplarz na półce",
                                "itemcategoryname": "30 Days Loan",
                                "itempolicy": "Wypożyczane na 30 dni",
                                "itemmaterial": "Książka",
                                "mainlocationname": branch,
                                "secondarylocationname": "ul. Przykładowa 1",
                                "listofservices": {
                                    "service": [
                                        {
                                            "type": "AlmaItemRequest",
                                            "allowed": allowed,
                                            "link-to-service": REQUEST_PATH,
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ]
            }
        }
    }


def _mock_record_lookup(search_recordid, holdings):
    control = {"recordid": [search_recordid], "originalsourceid": [NZ_MMS]}
    respx.get(f"{BASE}/primaws/rest/pub/pnxs").respond(
        200, json={"docs": [{"pnx": {"control": control, "display": {"title": ["Książka"]}}}]}
    )
    respx.post(f"{BASE}/primaws/rest/pub/delivery").respond(
        200, json=[{"pnx": {"control": {"recordid": [search_recordid]}}, "delivery": {"holding": holdings}}]
    )
    respx.get(f"{BASE}/primaws/rest/pub/getPhysicalService/{search_recordid.removeprefix('alma')}").respond(
        200, json={"physicalServiceId": SERVICE_ID}
    )


@pytest.mark.asyncio
async def test_get_holdable_items_resolves_network_zone_id_to_local_record():
    client = OmnisClient()
    client.token = "fake.token.fake"
    client.institution = "48OMNIS_BRP"
    client.view = "48OMNIS_BRP:BRACZ"
    with respx.mock:
        # Searching by a network-zone id returns the *local* record, with a different id.
        _mock_record_lookup(f"alma{LOCAL_MMS}", [_holding("Filia 1", "111")])
        holdings_route = respx.post(f"{BASE}/primaws/rest/priv/ILSServices/holdings/{SERVICE_ID}").respond(
            200, json=_holdings_response("Filia 1")
        )

        items = await client.get_holdable_items(NZ_MMS)

    assert len(items) == 1
    assert items[0].mmsid == LOCAL_MMS
    assert items[0].network_mmsid == NZ_MMS
    assert items[0].item_id == ITEM_ID
    assert items[0].request_path == REQUEST_PATH
    assert items[0].main_location == "Filia 1"
    body = json.loads(holdings_route.calls.last.request.content)
    assert body["filters"]["ilsRecordList"] == [{"institution": "48OMNIS_BRP", "recordId": LOCAL_MMS}]
    assert len(body["locations"]) == 1 and body["locations"][0]["holKey"]


@pytest.mark.asyncio
async def test_get_holdable_items_skips_items_without_allowed_request_service():
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        _mock_record_lookup(f"alma{LOCAL_MMS}", [_holding("Filia 1", "111")])
        respx.post(f"{BASE}/primaws/rest/priv/ILSServices/holdings/{SERVICE_ID}").respond(
            200, json=_holdings_response("Filia 1", allowed="N")
        )

        items = await client.get_holdable_items(LOCAL_MMS)

    assert items == []


@pytest.mark.asyncio
async def test_get_holdable_items_branch_filter_limits_holdings_calls():
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        _mock_record_lookup(f"alma{LOCAL_MMS}", [_holding("Filia 1", "111"), _holding("Filia 2", "222")])
        holdings_route = respx.post(f"{BASE}/primaws/rest/priv/ILSServices/holdings/{SERVICE_ID}").respond(
            200, json=_holdings_response("Filia 2")
        )

        items = await client.get_holdable_items(LOCAL_MMS, branch_filter="filia 2")

    assert holdings_route.call_count == 1
    assert json.loads(holdings_route.calls.last.request.content)["locations"][0]["mainLocation"] == "Filia 2"
    assert [i.main_location for i in items] == ["Filia 2"]


def _holdable_item():
    return HoldableItem(
        mmsid=LOCAL_MMS,
        item_id=ITEM_ID,
        request_path=REQUEST_PATH,
        status_name="Egzemplarz na półce",
        category="30 Days Loan",
        main_location="Filia 1",
        sub_location="ul. Przykładowa 1",
    )


def _form(pickups):
    return {
        "services-arr": {
            "services": [
                {
                    "itemId": ITEM_ID,
                    "groups-list-map": [
                        {
                            "pickupLocation": pickups,
                            "materialType": {"key": "BOOK", "value": "Książka"},
                            "requestType": "hold",
                        }
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_get_hold_options_parses_pickup_keys():
    client = OmnisClient()
    client.token = "fake.token.fake"
    client.view = "48OMNIS_BRP:BRACZ"
    with respx.mock:
        route = respx.get(f"{BASE}{REQUEST_PATH.split('?')[0]}").respond(
            200,
            json=_form(
                [
                    {"key": "111$$LIBRARY", "value": "Filia 1"},
                    {"key": "222$$LIBRARY", "value": "Filia 2"},
                ]
            ),
        )

        options = await client.get_hold_options(_holdable_item())

    params = route.calls.last.request.url.params
    assert params["institution"] == "48OMNIS_BRP"
    assert params["hasHold"] == "true"
    assert params["itemid"] == ITEM_ID
    assert options.request_type == "hold"
    assert options.material_type == "BOOK"
    assert [(p.id, p.type, p.name) for p in options.pickup_locations] == [
        ("111", "LIBRARY", "Filia 1"),
        ("222", "LIBRARY", "Filia 2"),
    ]


@pytest.mark.asyncio
async def test_get_hold_options_rejects_unexpected_pickup_key():
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get(f"{BASE}{REQUEST_PATH.split('?')[0]}").respond(200, json=_form([{"key": "111", "value": "Filia 1"}]))
        with pytest.raises(ValueError):
            await client.get_hold_options(_holdable_item())


@pytest.mark.asyncio
async def test_place_hold_sends_captured_payload():
    client = OmnisClient()
    client.token = "fake.token.fake"
    pickup = PickupLocation(id="111", type="LIBRARY", name="Filia 1")
    options = HoldRequestOptions(
        item=_holdable_item(), request_type="hold", material_type="BOOK", pickup_locations=[pickup]
    )
    with respx.mock:
        route = respx.post(f"{BASE}{REQUEST_PATH.split('?')[0]}").respond(
            200, json={"beaconO22": "385", "reply-text": "ok", "status": "ok"}
        )

        result = await client.place_hold(options, pickup)

    sent = route.calls.last.request
    assert sent.url.params["institution"] == "48OMNIS_BRP"
    assert sent.url.params["hasHold"] == "true"
    assert json.loads(sent.content) == {
        "requestType": "hold",
        "pickupLocation": "111",
        "materialType": "BOOK",
        "itemId": ITEM_ID,
        "group_id": LOCAL_MMS,
        "pickupLibraryId": "111",
        "pickupType": "LIBRARY",
    }
    assert result == {"beaconO22": "385", "reply-text": "ok", "status": "ok"}


@pytest.mark.asyncio
async def test_get_item_queue():
    client = OmnisClient()
    client.token = "fake.token.fake"
    with respx.mock:
        respx.get(f"{BASE}/primaws/rest/priv/ILSServices/itemQueue/{ITEM_ID}").respond(
            200, json={"itemId": ITEM_ID, "itemQueueString": "(zamówienie: 1)"}
        )
        assert await client.get_item_queue(ITEM_ID) == "(zamówienie: 1)"


@pytest.mark.asyncio
async def test_place_hold_requires_login():
    client = OmnisClient()
    pickup = PickupLocation(id="111", type="LIBRARY", name="Filia 1")
    options = HoldRequestOptions(
        item=_holdable_item(), request_type="hold", material_type="BOOK", pickup_locations=[pickup]
    )
    with pytest.raises(ValueError):
        await client.place_hold(options, pickup)


@pytest.mark.asyncio
async def test_place_hold_raises_on_primo_failure_envelope():
    # Primo reports some failures as HTTP 200 + {"status": "failed", "reply-code": ...}.
    client = OmnisClient()
    client.token = "fake.token.fake"
    pickup = PickupLocation(id="111", type="LIBRARY", name="Filia 1")
    options = HoldRequestOptions(
        item=_holdable_item(), request_type="hold", material_type="BOOK", pickup_locations=[pickup]
    )
    with respx.mock:
        respx.post(f"{BASE}{REQUEST_PATH.split('?')[0]}").respond(
            200, json={"status": "failed", "reply-code": "0002", "reply-text": "Request failed"}
        )
        with pytest.raises(ValueError, match="Request failed"):
            await client.place_hold(options, pickup)
