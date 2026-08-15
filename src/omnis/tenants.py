from typing import List, NotRequired, TypedDict


class Tenant(TypedDict):
    name: str
    base_url: str
    institution: str
    view: str
    is_demo: NotRequired[bool]
    default_timeout: NotRequired[float]


MOCK_TENANT: Tenant = {
    "name": "Nieoficjalna Biblioteka OMNIS (Demo)",
    "base_url": "https://omnis-mock.onrender.com",
    "institution": "MOCK",
    "view": "MOCK:MOCK",
    "is_demo": True,
    # Higher than the client's default 30s timeout: the free Render tier this mock
    # runs on cold-starts after 15 min of inactivity, taking 50s+ to respond.
    "default_timeout": 60.0,
}


KNOWN_TENANTS: List[Tenant] = [
    {
        "name": "Biblioteka Raczyńskich (Poznań)",
        "base_url": "https://omnis-br.primo.exlibrisgroup.com",
        "institution": "48OMNIS_BRP",
        "view": "48OMNIS_BRP:BRACZ",
    },
    {
        "name": "Biblioteka Narodowa",
        "base_url": "https://katalogi.bn.org.pl",
        "institution": "48OMNIS_NLOP",
        "view": "48OMNIS_NLOP:48OMNIS_NLOP",
    },
    {
        "name": "Biblioteka UAM (Poznań)",
        "base_url": "https://katalog.amu.edu.pl",
        "institution": "48OMNIS_AMU",
        "view": "48OMNIS_AMU:AMU",
    },
    {
        "name": "Biblioteka Publiczna w Łukowie",
        "base_url": "https://omnis-lukowski3.primo.exlibrisgroup.com",
        "institution": "48OMNIS_LUK3",
        "view": "48OMNIS_LUK3:LUK3_3",
    },
    {
        "name": "Dolnośląska Biblioteka Publiczna (Wrocław)",
        "base_url": "https://omnis-dbp.primo.exlibrisgroup.com",
        "institution": "48OMNIS_WBP",
        "view": "48OMNIS_WBP:48OMNIS_WBP",
    },
    {
        "name": "Uniwersytet Jagielloński (Kraków)",
        "base_url": "https://katalogi.uj.edu.pl",
        "institution": "48OMNIS_UJA",
        "view": "48OMNIS_UJA:uja",
    },
    {
        "name": "Uniwersytet Mikołaja Kopernika (Toruń)",
        "base_url": "https://szukaj.bu.umk.pl",
        "institution": "48OMNIS_UMKWT",
        "view": "48OMNIS_UMKWT:UMK",
    },
    {
        "name": "Wojewódzka Biblioteka Publiczna (Kielce)",
        "base_url": "https://omnis-swietokrzyskie2.primo.exlibrisgroup.com",
        "institution": "48OMNIS_SW2",
        "view": "48OMNIS_SW2:SW2_4",
    },
    {
        "name": "Koszalińska Biblioteka Publiczna",
        "base_url": "https://omnis-kbp.primo.exlibrisgroup.com",
        "institution": "48OMNIS_KBP",
        "view": "48OMNIS_KBP:48KBP",
    },
    {
        "name": "Książnica Zamojska (Zamość)",
        "base_url": "https://omnis-zamojski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_ZAM",
        "view": "48OMNIS_ZAM:ZAM_1",
    },
    MOCK_TENANT,
    {"name": "Custom / Własna...", "base_url": "", "institution": "", "view": ""},
]
