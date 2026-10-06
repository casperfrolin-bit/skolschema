# Schema & Skolmat – GitHub Pages

En enkel 16:9-sida för en skärm som visar:
- klockan
- lektionen som pågår
- hur många minuter som är kvar
- kommande lektioner
- dagens skolmat
- sparade inställningar med cookie

## Lägg på GitHub Pages

1. Skapa ett GitHub-repository.
2. Ladda upp alla filer i denna mapp.
3. Gå till **Settings → Pages**.
4. Välj **Deploy from a branch**, branch `main`, folder `/root`.
5. Öppna GitHub Pages-adressen.

## Schema

Ändra `data/schedule.json`. Dagarna ska skrivas:
`måndag`, `tisdag`, `onsdag`, `torsdag`, `fredag`.

## Skolmat

Sidan läser `data/menu.json`. Den är gjord så att menyn kan uppdateras automatiskt.

Viktigt: Skolmaten.se:s nuvarande API kräver klienttoken, så lägg inte en hemlig token direkt i `app.js` på GitHub Pages. Den säkra lösningen är att låta GitHub Actions hämta menyn med en secret och sedan skriva en publik `data/menu.json`.

När rätt Svensgårdsskolan-länk/API-uppgifter är kända kan workflowet kopplas in.

## Cookies

Inställningarna sparas i en cookie:
- skolnamn
- uppdateringsintervall

Ingen inloggning behövs.
