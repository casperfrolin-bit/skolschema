# Schema & Matsedel

Sida för en skärm: klocka med internettid, schema, nuvarande lektion och veckans matsedel.

## Filer
- `index.html` – hela sidan (kod och utseende ligger i filen)
- `data/schedule.json` – lektioner per klass: `{"9A": [...], "9B": [...]}` (dag, start, slut, ämne, sal). Används för "nuvarande lektion" och nedräkning
- `images/schema-9A.png`, `images/schema-9B.png` – schemabilderna. Byt bild genom att ersätta filen med exakt samma namn (annars ändra `SCHEMA_IMG` i `index.html`). Bilden ska vara utklippt till bara tabellen, 1090 × 1064 px, med vit (inte genomskinlig) bakgrund, annars hamnar den röda tidslinjen fel
- Valfritt: `images/schema-morkt-9A.png` / `schema-morkt-9B.png` för mörkt läge (annars inverteras den ljusa)
- `data/menu.json` – matsedeln, skrivs av `scripts/fetch_menu.py`
- `scripts/fetch_menu.py` + `.github/workflows/update-menu.yml` – hämtar matsedeln från Skolmatens API och skriver även in den direkt i `index.html`

## GitHub Pages
Settings → Pages → Deploy from a branch → `main` / `(root)`.

## Matsedel via Skolmatens officiella API
Matsedeln hämtas bara när en token finns – tills dess visas "Ingen uppgift".
1. Kontakta Skolmaten och be om en client token för en registrerad applikation (se https://skolmaten.se/about/api).
2. Lägg nyckeln i GitHub: Settings → Secrets and variables → Actions → New repository secret, namn `SKOLMATEN_TOKEN`.
3. Kör Actions → Uppdatera skolmat → Run workflow. Skriptet hittar skolan själv första gången och sparar id:t i `data/school_id.txt`.
4. Vill du ha automatisk hämtning: ta bort `#` framför `schedule`-raderna i `.github/workflows/update-menu.yml` (varje timme kl. 03–10 UTC på vardagar samt söndag kväll).

Nyckeln ska aldrig skrivas in i koden. Sidan läser alltid färsk `menu.json` vid varje öppning/uppdatering och visar senast kända matsedel direkt medan den hämtas.

## Välja klass
Rullgardinsmenyn under klockan växlar mellan 9A och 9B (bild, rubrik, nuvarande lektion). Valet sparas i webbläsaren. Länk direkt till en klass: `index.html?klass=9A`.

## Zoom och storlek
Allt på sidan skalas ihop med webbläsarens zoom (Ctrl +/–) och hamnar centrerat på skärmen. Storleken räknas om när fönstret ändrar storlek eller enheten vrids. Matsedeln skalas efter enhetens storlek.

## Token direkt i sidan (valfritt)
I `index.html` finns `SKOLMATEN = {token: "", ...}`. Är token tom görs ingen hämtning. Obs: allt i `index.html` är publikt – föredra GitHub-secret `SKOLMATEN_TOKEN` (se ovan).

## Fyll i matsedeln för hand (tills token finns)
Sidan läser `data/menu.json` vid varje öppning, så du kan skriva in matsedeln själv:
```json
{"updated": "2026-10-19 07:00", "days": [
  {"date": "2026-10-19", "main": "Köttbullar med potatis", "alt": "Vegetariska bullar"},
  {"date": "2026-10-20", "main": "Fiskgratäng", "alt": "Linsgryta"}
]}
```
`date` är ÅÅÅÅ-MM-DD, `main` är huvudrätten och `alt` är alternativet (kan vara tomt). Dagar som saknas visas som "Ingen uppgift". Senast kända matsedel sparas i webbläsaren och försvinner inte om filen en gång är tom.

## Schemabild utan manuell beskärning
Schemabilden laddas som en vanlig `<img>` (funktionen `loadSchema`). Är bilden redan 1090 × 1064 px används den som den är. Är det en hel A4-sida klipps tabellen ut med ren CSS (klassen `crop`), så ingen pixelavläsning, fetch eller SVG-omväg behövs. Ändra bara filnamnen i `SCHEMA_IMG`.

Går bilden inte att ladda försöker sidan en gång till förbi cachen och visar sedan ett felmeddelande med filnamnet i stället för en trasig bildikon. Den mörka bilden används bara om den faktiskt finns och har laddats, annars inverteras den ljusa.
