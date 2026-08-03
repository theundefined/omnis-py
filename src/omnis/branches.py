"""Branch directory (address/hours/phone) for Biblioteka Raczyńskich.

Unlike the rest of this package, this module is specific to a single tenant
(Biblioteka Raczyńskich, bracz.edu.pl) rather than the generic Primo/OMNIS API:
there is no cross-network endpoint for branch metadata, so this scrapes the
library's own public WordPress site instead.
"""

import html as htmllib
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

BRACZ_PAGES_URL = "https://bracz.edu.pl/wp-json/wp/v2/pages"
BRACZ_FILIE_SLUG = "filie"

_HEADING_BLOCK_RE = re.compile(
    r"<h2[^>]*>(?:<a[^>]*>)?(.*?)(?:</a>)?</h2>\s*(?:<p></p>\s*)?<p>(.*?)</p>",
    re.DOTALL,
)
_MAILTO_RE = re.compile(r'mailto:([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>")

_FIELD_LABELS = ["Adres", "Godziny otwarcia", "telefon", "email"]


class BranchInfo(BaseModel):
    name: str
    address: Optional[str] = None
    hours: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    @property
    def maps_url(self) -> Optional[str]:
        if not self.address:
            return None
        short_name = re.split(r"\s*[(–]", self.name)[0].strip()
        query = f"Biblioteka Raczyńskich {short_name}, {self.address}, Poznań"
        return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"


def _strip_tags(text: str) -> str:
    return htmllib.unescape(_TAG_RE.sub("", text)).strip()


def _parse_fields(body: str) -> Dict[str, str]:
    mail_match = _MAILTO_RE.search(body)
    body = _BR_RE.sub("\n", body)
    body = _strip_tags(body)
    lines = [line.strip().lstrip("\xa0").strip() for line in body.split("\n")]
    lines = [line for line in lines if line]

    fields: Dict[str, str] = {}
    current: Optional[str] = None
    for line in lines:
        matched_label = None
        value = ""
        for label in _FIELD_LABELS:
            if line.lower().startswith(label.lower() + ":"):
                matched_label = label
                value = line[len(label) + 1 :].strip()
                break
        if matched_label:
            current = matched_label
            fields[current] = value
        elif current:
            fields[current] = (fields.get(current, "") + " " + line).strip()

    if mail_match:
        fields["email"] = mail_match.group(1)
    return fields


def parse_branches(page_content_html: str) -> List[BranchInfo]:
    branches = []
    for raw_name, raw_body in _HEADING_BLOCK_RE.findall(page_content_html):
        name = _strip_tags(raw_name)
        if not name:
            continue
        fields = _parse_fields(raw_body)
        branches.append(
            BranchInfo(
                name=name,
                address=fields.get("Adres"),
                hours=fields.get("Godziny otwarcia"),
                phone=fields.get("telefon"),
                email=fields.get("email"),
            )
        )
    return branches


async def fetch_branches(client: httpx.AsyncClient) -> List[BranchInfo]:
    """Fetch and parse the Biblioteka Raczyńskich branch directory (bracz.edu.pl/filie/)."""
    response = await client.get(BRACZ_PAGES_URL, params={"slug": BRACZ_FILIE_SLUG})
    response.raise_for_status()
    pages: List[Dict[str, Any]] = response.json()
    if not pages:
        return []
    content_html = pages[0].get("content", {}).get("rendered", "")
    return parse_branches(content_html)
