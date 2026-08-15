# omnis-py

Biblioteka Python do obsługi API Ex Libris Primo (sieć OMNIS) oraz narzędzie CLI do zarządzania kontami bibliotecznymi.

---

## Opis (PL)

`omnis-py` to biblioteka umożliwiająca programistyczny dostęp do kont czytelnika w bibliotekach korzystających z systemu **Ex Libris Primo** (w Polsce działających głównie w ramach sieci **OMNIS**).

### Główne funkcjonalności
- **Autentykacja:** Logowanie do systemów bibliotecznych przy użyciu numeru karty i hasła.
- **Wypożyczenia:** Pobieranie listy aktywnych wypożyczeń wraz ze szczegółami (data zwrotu, autor, tytuł, filia).
- **Informacje o użytkowniku:** Pobieranie stanu konta, liczby wypożyczeń, rezerwacji oraz naliczonych kar.
- **Prolongata:** Możliwość przedłużania terminu zwrotu książek.
- **Narzędzie CLI:** Wygodna aplikacja terminalowa do monitorowania wielu kont na raz.

### Obsługiwane biblioteki (znane tenany)
Biblioteka jest uniwersalna i obsługuje m.in.:
- Biblioteka Raczyńskich (Poznań)
- Biblioteka Narodowa (Warszawa)
- Biblioteka UAM (Poznań)
- Dolnośląska Biblioteka Publiczna (Wrocław)
- Uniwersytet Jagielloński (Kraków)
- Uniwersytet Mikołaja Kopernika (Toruń)
- Wojewódzka Biblioteka Publiczna (Kielce)
- Koszalińska Biblioteka Publiczna
- Książnica Zamojska
- ...oraz każdą inną bibliotekę Primo po podaniu jej adresu URL i kodu instytucji.
- **Nieoficjalna Biblioteka OMNIS (Demo)** — publiczny mock serwera Primo ([omnis-mock](https://github.com/theundefined/omnis-mock)) z gotowym kontem testowym, bez potrzeby posiadania prawdziwej karty bibliotecznej. Zobacz `--demo` poniżej.

### Instalacja

```bash
pip install omnis-py
```

Dla narzędzia CLI zalecane jest użycie `pipx`:
```bash
pipx install omnis-py
```

### Użycie CLI

Po instalacji dostępne jest polecenie `omnis-cli`. 

Przy pierwszym uruchomieniu program poprowadzi Cię przez kreator dodawania konta. Konfiguracja jest przechowywana w `~/.config/omnis-py/config.yaml`.

- `omnis-cli` - wyświetla podsumowanie dla wszystkich kont i listę książek pogrupowaną według filii.
- `omnis-cli --add` - dodaje nowe konto do konfiguracji.
- `omnis-cli --renew` - próbuje przedłużyć wszystkie wypożyczenia oznaczone jako odnawialne dla skonfigurowanych kont przed pobraniem danych. Używaj ostrożnie; operacja wykona się bez dodatkowego potwierdzenia.
- `omnis-cli --search "tytuł lub fragment"` - wyszukuje książki w katalogu (na koncie pierwszej skonfigurowanej biblioteki), grupując wyniki wg tytułu i pokazując wszystkie wydania/wersje osobno wraz ze statusem dostępności w poszczególnych filiach (dostępna / wypożyczona do dnia).
- `omnis-cli --search "..." --branch "nazwa filii"` - jak wyżej, ale ogranicza wyniki do filii, których nazwa zawiera podany fragment (bez rozróżniania wielkości liter).
- `omnis-cli --branches` - pokazuje katalog filii Biblioteki Raczyńskich (adres, godziny otwarcia, telefon, link do Google Maps). Nie wymaga skonfigurowanego konta - dane pochodzą bezpośrednio ze strony bracz.edu.pl. Działa wyłącznie dla Biblioteki Raczyńskich.
- `omnis-cli --branches --branch "Filia 35"` - jak wyżej, ograniczone do filii, których nazwa zawiera podany fragment.
- `omnis-cli --list-accounts` - wyświetla skonfigurowane konta z numerem (indeksem), biblioteką, nazwą użytkownika, statusem włączenia i timeoutem.
- `omnis-cli --enable N` / `omnis-cli --disable N` - włącza/wyłącza konto o podanym numerze indeksu (z `--list-accounts`), bez usuwania go z konfiguracji.
- `omnis-cli --set-timeout N SEKUNDY` - ustawia niestandardowy timeout HTTP (w sekundach) dla konta o podanym indeksie.
- `omnis-cli --demo` - przełącza się w tryb demo: wyłącza wszystkie skonfigurowane konta prawdziwych bibliotek i włącza (lub dodaje, jeśli jeszcze nie istnieje) konto testowe wskazujące na [omnis-mock](https://github.com/theundefined/omnis-mock) — publiczny, samowystarczalny mock API Primo z fikcyjnymi wypożyczeniami. Wygodne do wypróbowania narzędzia bez podawania prawdziwych danych logowania. Pierwsze zapytanie może potrwać do ok. 50 sekund, jeśli darmowa instancja mocka na Render "obudziła się" po dłuższej bezczynności.
- `omnis-cli --exit-demo` - wychodzi z trybu demo: wyłącza konto testowe i przywraca (włącza z powrotem) konta, które zostały automatycznie wyłączone przez `--demo`.

Przykład wyszukiwania krok po kroku (cały cykl książek, z priorytetem konkretnych filii): [docs/examples/plomien-i-krzyz.md](docs/examples/plomien-i-krzyz.md).

---

## Description (EN)

`omnis-py` is a Python library providing programmatic access to patron accounts in libraries using the **Ex Libris Primo** system (widely used in Poland under the **OMNIS** network).

### Key Features
- **Authentication:** Login using card number and password.
- **Loans:** Fetch active loans with details (due date, author, title, branch).
- **User Info:** Get account status, number of loans, requests, and fines.
- **Renewal:** Support for renewing book loan terms.
- **CLI Tool:** A convenient terminal application to monitor multiple accounts at once.

### Supported Libraries
The library is generic and supports various institutions including:
- Raczyński Library (Poznań)
- National Library of Poland (Warszawa)
- Adam Mickiewicz University Library (Poznań)
- Lower Silesian Public Library (Wrocław)
- Jagiellonian University (Kraków)
- Nicolaus Copernicus University (Toruń)
- ...and any other Primo library by providing its URL and institution code.
- **Nieoficjalna Biblioteka OMNIS (Demo)** — a public mock Primo server ([omnis-mock](https://github.com/theundefined/omnis-mock)) with a ready-made test account, no real library card needed. See `--demo` below.

### Installation

```bash
pip install omnis-py
```

For the CLI tool, using `pipx` is recommended:
```bash
pipx install omnis-py
```

### CLI Usage

Once installed, the `omnis-cli` command becomes available.

On first run, it will guide you through adding an account. Configuration is stored in `~/.config/omnis-py/config.yaml`.

- `omnis-cli` - shows a summary for all accounts and a book list grouped by branch.
- `omnis-cli --add` - adds a new account to the configuration.
- `omnis-cli --renew` - attempts to renew all loans marked as renewable for configured accounts before fetching data. Use with caution; this action runs without an additional confirmation.
- `omnis-cli --search "title or keyword"` - searches the catalog (using the first configured account), grouping results by title and showing every edition/version separately along with per-branch availability (available / borrowed until date).
- `omnis-cli --search "..." --branch "branch name"` - as above, but limited to branches whose name contains the given text (case-insensitive).
- `omnis-cli --branches` - shows the Biblioteka Raczyńskich branch directory (address, opening hours, phone, Google Maps link). No account required - data comes directly from bracz.edu.pl. Works for Biblioteka Raczyńskich only.
- `omnis-cli --branches --branch "Filia 35"` - as above, limited to branches whose name contains the given text.
- `omnis-cli --list-accounts` - lists configured accounts with their index, library, username, enabled status, and timeout.
- `omnis-cli --enable N` / `omnis-cli --disable N` - enables/disables the account at the given index (from `--list-accounts`), without removing it from the configuration.
- `omnis-cli --set-timeout N SECONDS` - sets a custom HTTP timeout (in seconds) for the account at the given index.
- `omnis-cli --demo` - switches to demo mode: disables all configured real-library accounts and enables (or creates, if it doesn't exist yet) a demo account pointing at [omnis-mock](https://github.com/theundefined/omnis-mock) — a public, self-contained mock of the Primo API with fake loans. Handy for trying out the tool without real login credentials. The first request may take up to ~50 seconds if the free-tier mock instance on Render needs to wake up from being idle.
- `omnis-cli --exit-demo` - exits demo mode: disables the demo account and restores (re-enables) the accounts that `--demo` had automatically disabled.

---

## Home Assistant

Istnieje również integracja dla Home Assistant korzystająca z tej biblioteki: `omnis-ha`.

There is also a Home Assistant integration using this library: `omnis-ha`.

## License

MIT