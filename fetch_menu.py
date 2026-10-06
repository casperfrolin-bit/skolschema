"""Hämtar veckans skolmat för Svensgårdsskolan och uppdaterar data/menu.json.

Skolmaten.se:s gamla RSS-flöden är borttagna och deras API kräver en klienttoken.
Därför öppnar skriptet sidan i en riktig (headless) webbläsare och läser av de
JSON-svar som sidan själv hämtar. Då behövs ingen hemlig token.
Går något fel sparas en felsökningsfil (data/debug_skolmaten.json) och skriptet
avslutas med fel, så att GitHub visar ett rött kryss. Gamla menu.json ligger kvar.
"""
import json, os, re, sys, time, pathlib, urllib.parse, urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")
URL = "https://skolmaten.se/svensgardsskolan"
OUT = pathlib.Path("data/menu.json")
SCHEDULE = pathlib.Path("data/schedule.json")
INDEX = pathlib.Path("index.html")
API = "https://skolmaten.se/api/4"
SCHOOL_NAME = "Svensgårdsskolan"
SCHOOL_CACHE = pathlib.Path("data/school_id.txt")
DEBUG = pathlib.Path("data/debug_skolmaten.json")
TEXT_KEYS = ("value", "name", "text", "title", "description", "label")
MEAL_KEYS = ("meals", "items", "menu", "dishes", "courses", "food", "lunch")
DAYNAMES = ["måndag", "tisdag", "onsdag", "torsdag", "fredag"]
DAY_RE = re.compile(r"^(måndag|tisdag|onsdag|torsdag|fredag|mån|tis|ons|tors|tor|fre)\.?(\s+\d.*)?$", re.I)


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
        m = DAY_RE.match(l)
        hit = next((i for i, n in enumerate(DAYNAMES) if m and n.startswith(m.group(1).lower())), None)
        if hit is not None and len(l) < 30:
            cur = (monday + timedelta(days=hit)).isoformat()
            out.setdefault(cur, [])
        elif cur and not skip.match(l) and len(out[cur]) < 2:
            out[cur].append(l)
    out = {d: r for d, r in out.items() if r}
    return out if len(out) >= 3 else {}


def fetch():
    from playwright.sync_api import sync_playwright
    captured, body, html = [], "", ""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale="sv-SE", timezone_id="Europe/Stockholm")

        def on_response(r):
            try:
                txt = r.text()
                if txt.lstrip()[:1] in "{[":
                    captured.append({"url": r.url, "json": json.loads(txt)})
            except Exception:
                pass

        pg.on("response", on_response)
        pg.goto(URL, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(4000)
        body = pg.inner_text("body")
        html = pg.content()
        b.close()
    # data som ligger inbyggd i sidan (t.ex. Next.js __NEXT_DATA__) räknas som svar
    for m in re.finditer(r'<script[^>]*type="application/(?:json|ld\+json)"[^>]*>(.*?)</script>', html, re.S):
        try:
            captured.append({"url": "inline-script", "json": json.loads(m.group(1))})
        except Exception:
            pass
    return captured, body, html


def api_get(path, token, **params):
    """Anrop mot Skolmatens officiella API (kräver client-token i HTTP-huvudet)."""
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"client-token": token, "Accept": "application/json",
                                               "User-Agent": "skolmat-sida"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _norm(t):
    return re.sub(r"[^a-zåäö0-9]", "", t.lower())


def find_school_id(token):
    """Skol-id: från miljövariabel, sparad fil, eller sökning län -> kommun -> skola (görs en gång)."""
    sid = os.environ.get("SKOLMATEN_SCHOOL_ID", "").strip()
    if sid:
        return sid
    if SCHOOL_CACHE.exists() and SCHOOL_CACHE.read_text(encoding="utf-8").strip():
        return SCHOOL_CACHE.read_text(encoding="utf-8").strip()
    want = _norm(SCHOOL_NAME)
    for prov in api_get("provinces", token).get("provinces", []):
        for dist in api_get("districts", token, province=prov["id"]).get("districts", []):
            time.sleep(0.1)
            for sch in api_get("schools", token, district=dist["id"]).get("schools", []):
                if _norm(sch.get("name", "")) == want:
                    print(f"Hittade {sch['name']} i {dist.get('name')} (id {sch['id']})")
                    SCHOOL_CACHE.write_text(sch["id"], encoding="utf-8")
                    return sch["id"]
    raise RuntimeError(f"Hittade ingen skola som heter {SCHOOL_NAME} via API:t")


def menu_from_api(token, today):
    """Hämtar denna och nästa vecka. Returnerar {'2026-10-09': ['Rätt 1', 'Rätt 2']}."""
    sid = find_school_id(token)
    out = {}
    for i, offset in enumerate((0, 7)):
        y, w, _ = (today + timedelta(days=offset)).isocalendar()
        try:
            data = api_get(f"menu/{sid}", token, year=y, week=w)
        except Exception as e:
            if i == 0:
                raise
            print(f"Vecka {w} kunde inte hämtas (ok om den inte är publicerad än): {e}")
            continue
        for day in (data.get("WeekState") or {}).get("Days") or []:
            if day.get("cancelled"):
                continue
            rows = [m["name"].strip() for m in day.get("Meals") or [] if m.get("name", "").strip()]
            if rows and day.get("date"):
                out[day["date"][:10]] = rows
    return out


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
    found, source, captured, body, html = {}, "", [], "", ""
    token = os.environ.get("SKOLMATEN_TOKEN", "").strip()
    if token:
        try:
            found, source = menu_from_api(token, today), "skolmaten-api"
        except Exception as e:
            print("API-hämtning misslyckades, provar webbläsaren:", e)
            found = {}
    for attempt in range(0 if found else 3):
        try:
            captured, body, html = fetch()
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
        DEBUG.write_text(json.dumps({"time": str(datetime.now(TZ)), "responses": [{"url": c["url"], "json": c["json"]} for c in captured][:40],
                                     "body": body[:6000], "html": html[:30000]}, ensure_ascii=False)[:400000], encoding="utf-8")
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
