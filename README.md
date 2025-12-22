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

---

## Home Assistant

Istnieje również integracja dla Home Assistant korzystająca z tej biblioteki: `omnis-ha`.

There is also a Home Assistant integration using this library: `omnis-ha`.

## License

MIT