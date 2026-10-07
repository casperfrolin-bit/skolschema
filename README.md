# Schema & Matsedel

## Lägg in matsedeln själv (enklast)
Öppna `data/matsedel.txt` på GitHub, tryck på pennan (Edit), skriv in veckan och spara (Commit changes). Efter ca en minut syns maten på sidan, och den ligger sparad. Varje dag har två rader: `måndag: Huvudrätt` och under den `alt: Alternativ`. Instruktioner finns högst upp i filen.
Det är workflowet "Bygg matsedel från textfil" (`.github/workflows/build-menu.yml`) som gör jobbet varje gång filen ändras.

Sida för en skärm: klocka med internettid, schema, nuvarande lektion och veckans matsedel.

## Filer
- `index.html` – hela sidan (kod och utseende ligger i filen)
- `data/schedule.json` – lektioner (dag, start, slut, ämne, sal)
- `data/menu.json` – matsedeln, skrivs automatiskt av GitHub Actions
- `scripts/fetch_menu.py` + `.github/workflows/update-menu.yml` – hämtar matsedeln varje timme på vardagsmorgnar och skriver även in den direkt i `index.html`
- `images/` – valfritt: `schema-morkt.png` för eget mörkt schema

## GitHub Pages
Settings → Pages → Deploy from a branch → `main` / `(root)`.

## Matsedel
Den automatiska hämtningen är avstängd tills en API-nyckel finns (instruktion i `.github/workflows/update-menu.yml`). Då körs den varje timme kl. 03–10 UTC på vardagar samt söndag kväll. Sidan läser alltid färsk `menu.json` vid varje öppning/uppdatering och visar senast kända matsedel direkt medan den hämtas. Kör manuellt under Actions → Uppdatera skolmat → Run workflow.
Misslyckas hämtningen skapas `data/debug_skolmaten.json` och körningen blir röd.

## Matsedel via Skolmatens officiella API (rekommenderas)
1. Kontakta Skolmaten och be om en client token för en registrerad applikation (se https://skolmaten.se/about/api).
2. Lägg nyckeln i GitHub: Settings → Secrets and variables → Actions → New repository secret, namn `SKOLMATEN_TOKEN`.
3. Kör Actions → Uppdatera skolmat → Run workflow. Skriptet hittar skolan själv första gången och sparar id:t i `data/school_id.txt`.
Utan nyckel provar skriptet i stället att läsa webbsidan med en webbläsare (osäkrare). Nyckeln ska aldrig skrivas in i koden.
