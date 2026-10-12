# Publikacja panelu pod app.dziubekcycling.pl

Jak to działa: GitHub co noc (ok. 5–6 rano) uruchamia `sezon.py`, pobiera dane z intervals.icu, buduje dashboard,
szyfruje go Twoim hasłem i publikuje. W repozytorium jest tylko kod – Twoje dane i klucz nigdy tam nie trafiają
(`.env` i `cache/` są wykluczone w `.gitignore`), a opublikowana strona bez hasła to zaszyfrowany ciąg znaków.

## 1. Konto i aplikacja (raz)

1. Załóż konto na https://github.com/signup (jeśli nie masz).
2. Pobierz **GitHub Desktop** z https://desktop.github.com i zaloguj się.

## 2. Wrzucenie kodu (raz)

1. GitHub Desktop → **File → Add Local Repository** → wybierz folder `analiza-treningu`.
2. Pojawi się „This directory does not appear to be a Git repository” → kliknij **create a repository** → nazwa `panel-treningowy` → **Create repository**.
3. Kliknij **Publish repository**. **Odznacz „Keep this code private”** (darmowy hosting stron działa dla publicznych repozytoriów; w środku jest tylko kod).

## 3. Sekrety (raz)

Na github.com w repozytorium: **Settings → Secrets and variables → Actions → New repository secret**. Dodaj:

| Nazwa | Wartość |
|---|---|
| `INTERVALS_API_KEY` | klucz z intervals.icu (Settings → Developer Settings) |
| `DASHBOARD_PASSWORD` | hasło do panelu – długie i nigdzie indziej nieużywane, np. 4–5 losowych słów |

Hasło musi być mocne: zaszyfrowaną stronę może pobrać każdy, więc chroni ją tylko jego długość.

## 4. Włączenie strony (raz)

1. **Settings → Pages → Source: GitHub Actions**.
2. Zakładka **Actions → Dashboard → Run workflow**. Po ok. 2 minutach panel jest pod
   `https://<twój-login>.github.io/panel-treningowy/`.

## 5. Subdomena (raz)

1. **Settings → Pages → Custom domain**: wpisz `app.dziubekcycling.pl` → Save.
2. U dostawcy domeny (tam, gdzie kupiłaś dziubekcycling.pl) dodaj rekord DNS:
   typ `CNAME`, nazwa `app`, wartość `<twój-login>.github.io`.
3. Po kilkunastu minutach do kilku godzin zaznacz **Enforce HTTPS**.
4. We Framerze dodaj link do `https://app.dziubekcycling.pl` (np. w stopce, bez wyróżniania – to Twój prywatny panel).

## Na co dzień

- Panel odświeża się sam co noc. Od razu: **Actions → Dashboard → Run workflow**.
- Zmiana ustawień (daty sezonu, porównywane okresy): edytuj `config.json` w folderze, w GitHub Desktop **Commit** + **Push** – panel przebuduje się sam.
  Zamiast daty końca możesz wpisać `"dzis"`.
- Jeśli coś nie działa: **Actions** → ostatnie uruchomienie z czerwonym krzyżykiem → skopiuj błąd i wklej mi.
