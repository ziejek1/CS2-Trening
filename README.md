# CS2 Trening E-Sport

Aplikacja desktopowa do planowania i śledzenia treningu CS2.

## Uruchomienie

W PowerShellu, z katalogu projektu:

```powershell
.\.venv\Scripts\python.exe main.py
```

Zależności są zapisane w `requirements.txt`.

## Wersja EXE

Gotowa wersja okienkowa znajduje się w `dist\CS2Trening\CS2Trening.exe`.
Build można odtworzyć poleceniem:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --icon app_icon.ico --add-data "app_icon.ico;." --name CS2Trening main.py
```

Pliki `users.json` i `pro_training_data.json` powinny znajdować się obok pliku EXE, aby zachować konta i postępy.

## Instalator Windows

Gotowy skrypt instalatora znajduje się w `installer\CS2Trening.iss`. Do jego skompilowania potrzebny jest Inno Setup. Po instalacji Inno Setup uruchom PowerShell:

```powershell
.\installer\build_installer.ps1
```

Instalator utworzy skrót na pulpicie i zachowa pliki danych użytkownika przy odinstalowaniu.

## Automatyczne aktualizacje

Aplikacja pokazuje numer wersji na ekranie logowania i sprawdza aktualizacje przed wpuszczeniem użytkownika do aplikacji. Jeśli znajdzie release z nowszym tagiem, np. `v1.0.1`, zablokuje logowanie, zaproponuje pobranie instalatora i zamknie obecną wersję przed aktualizacją. Przy braku internetu logowanie pozostaje dostępne.

Aby opublikować aktualizację:

1. Zmień `APP_VERSION` w `app_constants.py`.
2. Utwórz commit i wypchnij tag, np. `v1.0.1`.
3. GitHub Actions zbuduje instalator i opublikuje go w Releases.

Workflow znajduje się w `.github\workflows\release.yml`.

## Użytkownicy online

Funkcja obecności używa Supabase. Aby ją włączyć:

1. Utwórz projekt w Supabase.
2. Uruchom zawartość `supabase_schema.sql` w SQL Editorze.
3. Skopiuj Project URL i anon key do `app_constants.py`:

```python
SUPABASE_URL = "https://twoj-projekt.supabase.co"
SUPABASE_ANON_KEY = "twoj-anon-key"
```

Aplikacja wysyła heartbeat co 30 sekund. Użytkownik jest online przez 90 sekund od ostatniego heartbeat.

## Synchronizacja statystyk

Aby ranking, XP, historię i statystyki było widać na wszystkich komputerach, uruchom również `supabase_training_schema.sql` w Supabase SQL Editorze. Przy pierwszym logowaniu lokalne dane użytkownika zostaną wysłane do chmury, a późniejsze zapisy będą synchronizowane centralnie.

## Chat

Po utworzeniu tabeli obecności uruchom dodatkowo zawartość `supabase_chat_schema.sql` w Supabase SQL Editorze. Zakładka Chat odświeża wiadomości co 5 sekund i pozwala wysyłać wiadomości do zalogowanych użytkowników.

Uruchom również `supabase_chat_retention.sql`, aby Supabase automatycznie zostawiał tylko 10 najnowszych wiadomości. Starsze wiadomości są usuwane po dodaniu kolejnej.

## Testy

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testy obejmują hasła PBKDF2, rangi, kategorie, serie, odznaki, wykresy oraz zapis i odczyt danych.

## Struktura

- `main.py` - uruchomienie aplikacji i główny przepływ GUI.
- `app_constants.py` - konfiguracja, rangi, kategorie i wartości domyślne.
- `auth_utils.py` - haszowanie PBKDF2 i tokeny logowania.
- `data_store.py` - odczyt i zapis użytkowników oraz danych treningowych.
- `training_utils.py` - rangi, XP, serie, kategorie i agregaty statystyk.
- `leaderboard_view.py` - ranking Top uczniowie.
- `planner_view.py` - kalendarz, plany, przypomnienia i automatyczne sesje.
- `stats_view.py` - filtry kategorii i zakresów dat.
- `tests/test_core.py` - testy logiki niezależnej od GUI.

## Role

Administrator może zarządzać wspólnym katalogiem modułów i standardowymi rutynami Pro. Każdy użytkownik może zarządzać własnymi rutynami, planować treningi i zapisywać historię.

## Dane

- `users.json` przechowuje konta i hashe haseł.
- `pro_training_data.json` przechowuje dane treningowe użytkowników.
- Kopię danych można utworzyć z zakładki profilu.
