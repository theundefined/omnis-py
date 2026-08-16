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
    # Discovered via almaInstitutionsList (see scripts/discover_tenants.py) and verified
    # individually (base_url/view confirmed against each institution's own live Primo
    # instance) in 2026-08. 48OMNIS_LIS was found but has no confirmed `view` and is
    # deliberately omitted - do not guess it.
    {
        "name": "Europejskie Centrum Solidarności (Gdańsk)",
        "base_url": "https://katalog.ecs.gda.pl",
        "institution": "48FAR_ECS",
        "view": "48FAR_ECS:TEST_AF",
    },
    {
        "name": "Gdański Uniwersytet Medyczny",
        "base_url": "https://katalog.gumed.edu.pl",
        "institution": "48FAR_GUM",
        "view": "48FAR_GUM:48GUM",
    },
    {
        "name": "Biblioteka Politechniki Gdańskiej",
        "base_url": "https://katalogbpg.pg.edu.pl",
        "institution": "48FAR_PGD",
        "view": "48FAR_PGD:48PGD",
    },
    {
        "name": "Uniwersytet Gdański",
        "base_url": "https://katalog-bug.ug.edu.pl",
        "institution": "48FAR_UGD",
        "view": "48FAR_UGD:48UGD",
    },
    {
        "name": "Akademia Górniczo-Hutnicza (Kraków)",
        "base_url": "https://katalog.agh.edu.pl",
        "institution": "48OMNIS_AGH",
        "view": "48OMNIS_AGH:48AGH",
    },
    {
        "name": "Biblioteka Elbląska im. Cypriana Norwida",
        "base_url": "https://omnis-be.primo.exlibrisgroup.com",
        "institution": "48OMNIS_BE",
        "view": "48OMNIS_BE:BE",
    },
    {
        "name": "Miejska Biblioteka Publiczna – Centrum Wiedzy (Bolesławiec)",
        "base_url": "https://omnis-mbpb.primo.exlibrisgroup.com",
        "institution": "48OMNIS_BOL",
        "view": "48OMNIS_BOL:23901",
    },
    {
        "name": "Biblioteka Publiczna m.st. Warszawy – Biblioteka Główna Woj. Mazowieckiego",
        "base_url": "https://omnis-wbpw.primo.exlibrisgroup.com",
        "institution": "48OMNIS_BPW",
        "view": "48OMNIS_BPW:48OMNIS_BPW_BPWKoszykowa",
    },
    {
        "name": "Chełmska Biblioteka Publiczna (Chełm)",
        "base_url": "https://omnis-chelmski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_CHE",
        "view": "48OMNIS_CHE:CHE_1",
    },
    {
        "name": "Miejska Biblioteka Publiczna im. Galla Anonima (Głogów)",
        "base_url": "https://eu05.primo.exlibrisgroup.com",
        "institution": "48OMNIS_GLO",
        "view": "48OMNIS_GLO:48GLO",
    },
    {
        "name": "Biblioteki powiatu janowskiego (Janów Lubelski)",
        "base_url": "https://omnis-janowski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_JAN",
        "view": "48OMNIS_JAN:JAN",
    },
    {
        "name": "Książnica Pomorska im. Stanisława Staszica (Szczecin)",
        "base_url": "https://omnis-kps.primo.exlibrisgroup.com",
        "institution": "48OMNIS_KPS",
        "view": "48OMNIS_KPS:48KPS",
    },
    {
        "name": "Biblioteki powiatu kraśnickiego (Kraśnik)",
        "base_url": "https://omnis-krasnicki.primo.exlibrisgroup.com",
        "institution": "48OMNIS_KR",
        "view": "48OMNIS_KR:48OMNIS_KR_5",
    },
    {
        "name": "Biblioteki powiatów kraśnickiego i krasnostawskiego (Krasnystaw)",
        "base_url": "https://omnis-krasnicki-krasnostawski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_KRA",
        "view": "48OMNIS_KRA:KRA_4",
    },
    {
        "name": "Katolicki Uniwersytet Lubelski Jana Pawła II (Lublin)",
        "base_url": "https://katalog.kul.pl",
        "institution": "48OMNIS_KUL",
        "view": "48OMNIS_KUL:KUL",
    },
    {
        "name": "Biblioteki powiatu kutnowskiego (Kutno)",
        "base_url": "https://omnis-kutnowski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_KUT",
        "view": "48OMNIS_KUT:KUT_2",
    },
    {
        "name": "Biblioteki powiatów lubartowskiego i ryckiego",
        "base_url": "https://omnis-lubartowski-rycki.primo.exlibrisgroup.com",
        "institution": "48OMNIS_LIR",
        "view": "48OMNIS_LIR:LIR_2",
    },
    {
        "name": "Biblioteki powiatów brzezińskiego, łódzkiego wsch., opoczyńskiego, pajęczańskiego, "
        "piotrkowskiego i poddębickiego",
        "base_url": "https://omnis-lodzkie1.primo.exlibrisgroup.com",
        "institution": "48OMNIS_LO1",
        "view": "48OMNIS_LO1:LO1_5",
    },
    {
        "name": "Powiatowa Biblioteka Publiczna (powiat łowicki)",
        "base_url": "https://omnis-lowicki.primo.exlibrisgroup.com",
        "institution": "48OMNIS_LOW",
        "view": "48OMNIS_LOW:LOW_3",
    },
    {
        "name": "MBP im. T. Różewicza (Wrocław)",
        "base_url": "https://omnis-mbpwr.primo.exlibrisgroup.com",
        "institution": "48OMNIS_MBP",
        "view": "48OMNIS_MBP:MBP",
    },
    {
        "name": "Miejska Biblioteka Publiczna (Gdynia)",
        "base_url": "https://omnis-mbpg.primo.exlibrisgroup.com",
        "institution": "48OMNIS_MBPG",
        "view": "48OMNIS_MBPG:48MBPG",
    },
    {
        "name": "Biblioteka Miejska w Łodzi",
        "base_url": "https://katalog.biblioteka.lodz.pl",
        "institution": "48OMNIS_MBPL",
        "view": "48OMNIS_MBPL:48MBPL",
    },
    {
        "name": "Wojewódzka Biblioteka Publiczna im. H. Łopacińskiego (Lublin)",
        "base_url": "https://bn-mpl.primo.exlibrisgroup.com",
        "institution": "48OMNIS_MPL",
        "view": "48OMNIS_MPL:48OMNIS_MPL",
    },
    {
        "name": "Powiatowa Biblioteka Publiczna (Opole Lubelskie)",
        "base_url": "https://omnis-opolski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_OPO",
        "view": "48OMNIS_OPO:OPO_1",
    },
    {
        "name": "Powiatowa Biblioteka Publiczna – Centrum Kultury (Parczew)",
        "base_url": "https://omnis-parczewski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_PAR",
        "view": "48OMNIS_PAR:PAR_4",
    },
    {
        "name": "Biblioteka Naukowa PAU i PAN (Kraków)",
        "base_url": "https://omnis-pau.primo.exlibrisgroup.com",
        "institution": "48OMNIS_PAU",
        "view": "48OMNIS_PAU:48PAU",
    },
    {
        "name": "Biblioteka Główna UPJP2 (Kraków)",
        "base_url": "https://omnis-upjp.primo.exlibrisgroup.com",
        "institution": "48OMNIS_PUJP",
        "view": "48OMNIS_PUJP:48PUJP",
    },
    {
        "name": "Biblioteki powiatu radzyńskiego (Radzyń Podlaski)",
        "base_url": "https://omnis-radzynski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_RAD",
        "view": "48OMNIS_RAD:RAD_4",
    },
    # Same physical library as 48OMNIS_SW2 above under a newer/different BN-hosted
    # institution code (bn-rpl.primo... vs omnis-swietokrzyskie2.primo...); which one is
    # currently canonical is unconfirmed, so both are kept until that's resolved. This
    # tenant also only exposes Primo's "New Discovery Experience" (/nde/home), not the
    # classic /discovery/search OmnisClient.login() primes cookies against - it may not
    # work with this client without a code change.
    {
        "name": "Wojewódzka Biblioteka Publiczna im. W. Gombrowicza (Kielce, NDE)",
        "base_url": "https://bn-rpl.primo.exlibrisgroup.com",
        "institution": "48OMNIS_RPL",
        "view": "48OMNIS_RPL:NDE",
    },
    {
        "name": "Miejska Biblioteka Publiczna (Skierniewice)",
        "base_url": "https://omnis-skierniewicki.primo.exlibrisgroup.com",
        "institution": "48OMNIS_SKI",
        "view": "48OMNIS_SKI:SKI_1",
    },
    {
        "name": "Biblioteki powiatów buskiego, jędrzejowskiego, kieleckiego i koneckiego",
        "base_url": "https://omnis-swietokrzyskie1.primo.exlibrisgroup.com",
        "institution": "48OMNIS_SW1",
        "view": "48OMNIS_SW1:SW1_7",
    },
    {
        "name": "Miejska Biblioteka Publiczna im. T. Zamoyskiego (Tomaszów Lubelski)",
        "base_url": "https://omnis-tomaszowski-lubelski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_TL",
        "view": "48OMNIS_TL:48OMNIS_TL_4",
    },
    {
        "name": "Miejska Biblioteka Publiczna (Tomaszów Mazowiecki)",
        "base_url": "https://omnis-tomaszowski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_TOM",
        "view": "48OMNIS_TOM:TOM_1",
    },
    {
        "name": "Politechnika Wrocławska",
        "base_url": "https://omnis-pwr.primo.exlibrisgroup.com",
        "institution": "48OMNIS_TUR",
        "view": "48OMNIS_TUR:48TUR",
    },
    {
        "name": "Uniwersytet Kardynała Stefana Wyszyńskiego (Warszawa)",
        "base_url": "https://omnis-uksw.primo.exlibrisgroup.com",
        "institution": "48OMNIS_UKSW",
        "view": "48OMNIS_UKSW:PRIMO",
    },
    {
        "name": "Biblioteka Główna UMCS (Lublin)",
        "base_url": "https://omnis-umcs.primo.exlibrisgroup.com",
        "institution": "48OMNIS_UMCS",
        "view": "48OMNIS_UMCS:UMCS",
    },
    {
        "name": "Uniwersytet Opolski",
        "base_url": "https://omnis-uo.primo.exlibrisgroup.com",
        "institution": "48OMNIS_UOP",
        "view": "48OMNIS_UOP:48UOP",
    },
    {
        "name": "Uniwersytet Warszawski",
        "base_url": "https://omnis-buw.primo.exlibrisgroup.com",
        "institution": "48OMNIS_UOW",
        "view": "48OMNIS_UOW:48UOW",
    },
    {
        "name": "Uniwersytet Wrocławski",
        "base_url": "https://katalog.uwr.edu.pl",
        "institution": "48OMNIS_UWR",
        "view": "48OMNIS_UWR:STG",
    },
    {
        "name": "Wojewódzka Biblioteka Publiczna im. Marszałka J. Piłsudskiego (Łódź)",
        "base_url": "https://omnis-wbpl.primo.exlibrisgroup.com",
        "institution": "48OMNIS_WBPL",
        "view": "48OMNIS_WBPL:48OMNIS_WBPL",
    },
    {
        "name": "Wojewódzka Biblioteka Publiczna (Olsztyn)",
        "base_url": "https://omnis-wbpo.primo.exlibrisgroup.com",
        "institution": "48OMNIS_WBPO",
        "view": "48OMNIS_WBPO:WBPO",
    },
    {
        "name": "Powiatowa Biblioteka Publiczna (Wieluń)",
        "base_url": "https://omnis-wielunski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_WIE",
        "view": "48OMNIS_WIE:WIE_1",
    },
    {
        "name": "Miejska Biblioteka Publiczna (Zduńska Wola)",
        "base_url": "https://omnis-zdunskowolski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_ZDU",
        "view": "48OMNIS_ZDU:ZDU_1",
    },
    {
        "name": "Miejsko-Powiatowa Biblioteka Publiczna (Zgierz)",
        "base_url": "https://omnis-zgierski.primo.exlibrisgroup.com",
        "institution": "48OMNIS_ZGI",
        "view": "48OMNIS_ZGI:ZGI_1",
    },
    {
        "name": "Zakład Narodowy im. Ossolińskich (Wrocław)",
        "base_url": "https://omnis-zno.primo.exlibrisgroup.com",
        "institution": "48OMNIS_ZNO",
        "view": "48OMNIS_ZNO:ZNO",
    },
    {
        "name": "Uniwersytet Warmińsko-Mazurski (Olsztyn)",
        "base_url": "https://uwm.primo.exlibrisgroup.com",
        "institution": "48UWM_INST",
        "view": "48UWM_INST:48UWM",
    },
    MOCK_TENANT,
    {"name": "Custom / Własna...", "base_url": "", "institution": "", "view": ""},
]
