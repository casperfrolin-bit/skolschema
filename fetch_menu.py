"""Hämtar veckans skolmat för Svensgårdsskolan och uppdaterar data/menu.json.

Skolmaten.se:s gamla RSS-flöden är borttagna och deras API kräver en klienttoken.
Därför öppnar skriptet sidan i en riktig (headless) webbläsare och läser av de
JSON-svar som sidan själv hämtar. Då behövs ingen hemlig token.
Går något fel sparas en felsökningsfil (data/debug_skolmaten.json) och skriptet
avslutas med fel, så att GitHub visar ett rött kryss. Gamla menu.json ligger kvar.
"""
import json, re, sys, pathlib
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")
URL = "https://skolmaten.se/svensgardsskolan"
OUT = pathlib.Path("data/menu.json")
SCHEDULE = pathlib.Path("data/schedule.json")
INDEX = pathlib.Path("index.html")
DEBUG = pathlib.Path("data/debug_skolmaten.json")
TEXT_KEYS = ("value", "name", "text", "title", "description", "label")
MEAL_KEYS = ("meals", "items", "menu", "dishes", "courses", "food", "lunch")
DAYNAMES = ["måndag", "tisdag", "onsdag", "torsdag", "fredag"]


def parse_date(s):
    """'2026-10-04T22:00:00Z' -> 2026-10-05 (svensk tid)."""
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (d.astimezone(TZ) if d.tzinfo else d).date().isoformat()
    except Exception:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
        return "-".join(m.groups()) if m else None


def meal_text(x):
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, dict):
        for k, v in x.items():
            if k.lower() in TEXT_KEYS and isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def find_days(node, out):
    """Letar generellt igenom JSON efter 'dag med datum + lista med rätter'."""
    if isinstance(node, dict):
        d = None
        for k, v in node.items():
            if "date" in k.lower() and isinstance(v, str):
                d = parse_date(v)
                if d:
                    break
        if d:
            for k, v in node.items():
                if k.lower() in MEAL_KEYS and isinstance(v, list):
                    rows = [t for t in (meal_text(i) for i in v) if t]
                    if rows:
                        out[d] = rows
                        break
        for v in node.values():
            find_days(v, out)
    elif isinstance(node, list):
        for v in node:
            find_days(v, out)


def parse_body_text(text, today):
    """Reserv: läser veckodagsrubriker i sidans text (aktuell vecka)."""
    monday = today - timedelta(days=today.weekday())
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    skip = re.compile(r"^(vecka|v\.|\d{1,2}\s+\w+|\d{4}-\d{2}-\d{2})", re.I)
    out, cur = {}, None
    for l in lines:
        low = l.lower()
        hit = next((i for i, n in enumerate(DAYNAMES) if low.startswith(n)), None)
        if hit is not None and len(l) < 30:
            cur = (monday + timedelta(days=hit)).isoformat()
            out.setdefault(cur, [])
        elif cur and not skip.match(l) and len(out[cur]) < 2:
            out[cur].append(l)
    out = {d: r for d, r in out.items() if r}
    return out if len(out) >= 3 else {}


def fetch():
    from playwright.sync_api import sync_playwright
    captured, body = [], ""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale="sv-SE", timezone_id="Europe/Stockholm")

        def on_response(r):
            try:
                if "json" in r.headers.get("content-type", ""):
                    captured.append({"url": r.url, "json": r.json()})
            except Exception:
                pass

        pg.on("response", on_response)
        pg.goto(URL, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(4000)
        body = pg.inner_text("body")
        b.close()
    return captured, body


def inline_seed(tag, path):
    """Skriver in senaste datan direkt i index.html så att sidan visar den utan att vänta på nätverket."""
    try:
        html = INDEX.read_text(encoding="utf-8")
        data = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False).replace("<", "\\u003c")
        pat = re.compile(r'(<script id="%s" type="application/json">).*?(</script>)' % tag, re.S)
        new, n = pat.subn(lambda m: m.group(1) + data + m.group(2), html, count=1)
        if n and new != html:
            INDEX.write_text(new, encoding="utf-8")
    except Exception as e:
        print("Kunde inte uppdatera inbyggd data i index.html:", e)


def main():
    inline_seed("seed-schedule", SCHEDULE)
    today = datetime.now(TZ).date()
    found, source, captured, body = {}, "", [], ""
    for attempt in range(3):
        try:
            captured, body = fetch()
        except Exception as e:
            print("Försök", attempt + 1, "misslyckades:", e)
            continue
        for c in captured:
            find_days(c["json"], found)
        source = "api"
        if not found:
            found, source = parse_body_text(body, today), "text"
        if found:
            break

    if not found:
        DEBUG.write_text(json.dumps({"time": str(datetime.now(TZ)), "responses": captured,
                                     "body": body[:5000]}, ensure_ascii=False)[:400000], encoding="utf-8")
        print("Hittade ingen meny. Felsökningsfil sparad:", DEBUG)
        sys.exit(1)

    days = {}
    if OUT.exists():
        try:
            for d in json.loads(OUT.read_text(encoding="utf-8")).get("days", []):
                days[d["date"]] = d
        except Exception:
            pass
    for d, rows in found.items():
        days[d] = {"date": d, "main": rows[0], "alt": " / ".join(rows[1:])}
    cutoff = (today - timedelta(days=21)).isoformat()
    days = {k: v for k, v in days.items() if k >= cutoff}
    OUT.write_text(json.dumps({"updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
                               "days": sorted(days.values(), key=lambda d: d["date"])},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    inline_seed("seed-menu", OUT)
    DEBUG.unlink(missing_ok=True)
    print(f"Sparade {len(found)} dagar (källa: {source})")


if __name__ == "__main__":
    main()
