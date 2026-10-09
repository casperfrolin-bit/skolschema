"""Hämtar skolmaten för Svensgårdsskolan via Skolmatens officiella API och uppdaterar data/menu.json.

Kräver en client token (GitHub-secret SKOLMATEN_TOKEN). Utan token görs ingen hämtning.
Gamla dagar behålls i tre veckor. Senaste matsedeln skrivs även in direkt i index.html.
"""
import json, os, re, sys, time, pathlib, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")
OUT = pathlib.Path("data/menu.json")
SCHEDULE = pathlib.Path("data/schedule.json")
INDEX = pathlib.Path("index.html")
API = "https://skolmaten.se/api/4"
SCHOOL_NAME = "Svensgårdsskolan"
SCHOOL_CACHE = pathlib.Path("data/school_id.txt")


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
    token = os.environ.get("SKOLMATEN_TOKEN", "").strip()
    if not token:
        print("SKOLMATEN_TOKEN saknas – ingen matsedel hämtas.")
        sys.exit(1)
    today = datetime.now(TZ).date()
    found = menu_from_api(token, today)
    if not found:
        print("API:t gav ingen matsedel för denna eller nästa vecka.")
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
    print(f"Sparade {len(found)} dagar")


if __name__ == "__main__":
    main()
