import pytest
import respx
import httpx

from omnis.branches import fetch_branches, parse_branches

SAMPLE_CONTENT = """
<div class="wp-block-column is-style-stand-out">
<h2 class="wp-block-heading"><a href="https://bracz.edu.pl/filia-35">Filia 35 (dla dorosłych i dzieci)</a></h2>
<p><strong>Adres:</strong>&nbsp;ul. Druskienicka 32<br>(nowy pawilon)<br><strong>Godziny otwarcia:<br></strong>poniedziałki, środy i piątki: 13:00-19:00<br>wtorki i czwartki 9:00-14:30<br><strong>telefon:</strong>&nbsp;61 822 10 41<br><strong>email:</strong> <a href="mailto:filia35@bracz.edu.pl">filia35@bracz.edu.pl</a></p>
</div>
<div class="wp-block-column is-style-stand-out">
<h2 class="wp-block-heading"><a href="https://bracz.edu.pl/filia-2">Filia 2 (dla dorosłych i dzieci)</a></h2>
<p><strong>Adres:&nbsp;</strong>os. Oświecenia 59<br><strong>Godziny otwarcia:<br></strong>od poniedziałku do piątku: 9:00-19:00<br><strong>telefon:&nbsp;</strong>61 876 71 21<br><strong>email:&nbsp;</strong><a href="mailto:filia2@bracz.edu.pl">filia2@bracz.edu.pl</a></p>
</div>
"""


def test_parse_branches_extracts_all_fields():
    branches = parse_branches(SAMPLE_CONTENT)

    assert len(branches) == 2

    f35 = branches[0]
    assert f35.name == "Filia 35 (dla dorosłych i dzieci)"
    assert f35.address == "ul. Druskienicka 32 (nowy pawilon)"
    assert "13:00-19:00" in f35.hours
    assert f35.phone == "61 822 10 41"
    assert f35.email == "filia35@bracz.edu.pl"
    assert f35.maps_url is not None
    assert f35.maps_url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Filia+35" in f35.maps_url or "Filia%2035" in f35.maps_url

    f2 = branches[1]
    assert f2.address == "os. Oświecenia 59"
    assert f2.phone == "61 876 71 21"


def test_parse_branches_empty_content_returns_empty_list():
    assert parse_branches("<p>no branches here</p>") == []


@pytest.mark.asyncio
async def test_fetch_branches_calls_wp_api_and_parses():
    with respx.mock:
        respx.get("https://bracz.edu.pl/wp-json/wp/v2/pages", params={"slug": "filie"}).respond(
            200,
            json=[{"content": {"rendered": SAMPLE_CONTENT}}],
        )
        async with httpx.AsyncClient() as client:
            branches = await fetch_branches(client)

    assert len(branches) == 2
    assert branches[0].name.startswith("Filia 35")
