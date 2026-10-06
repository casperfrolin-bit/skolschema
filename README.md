# Schema & Matsedel

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
Körs varje timme kl. 03–10 UTC på vardagar samt söndag kväll. Sidan läser alltid färsk `menu.json` vid varje öppning/uppdatering och visar senast kända matsedel direkt medan den hämtas. Kör manuellt under Actions → Uppdatera skolmat → Run workflow.
Misslyckas hämtningen skapas `data/debug_skolmaten.json` och körningen blir röd.
