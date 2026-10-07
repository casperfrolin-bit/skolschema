"""Bygger data/menu.json (och den inbyggda datan i index.html) från den handskrivna filen data/matsedel.txt.

Format:
    vecka 41
    måndag: Köttbullar med potatis
    alt: Vegetarisk pasta
    tisdag: Fiskgratäng
Alternativet skrivs på en egen rad direkt under dagen (alt: eller alternativ:). Man kan också skriva allt på en rad med |. Rader som börjar med # är kommentarer.
Skriv 'vecka 41 2026' om du vill ange år (annars väljs rätt år automatiskt).
"""
import json, re, pathlib
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fetch_menu import inline_seed, OUT

TZ = ZoneInfo("Europe/Stockholm")
SRC = pathlib.Path("data/matsedel.txt")
DAYS = {"måndag": 1, "mån": 1, "tisdag": 2, "tis": 2, "onsdag": 3, "ons": 3,
        "torsdag": 4, "tors": 4, "tor": 4, "fredag": 5, "fre": 5}
WEEK_RE = re.compile(r"^vecka\s+(\d{1,2})(?:\s+(\d{4}))?\s*:?\s*(?:#.*)?$", re.I)  # tillåter kommentar efter
DAY_RE = re.compile(r"^([A-Za-zåäöÅÄÖ]+)\.?\s*:\s*(.*)$")
ALT_NAMES = {"alt", "alternativ", "alternativet", "veg", "vegetariskt", "vegetarisk"}


def parse(text, today):
    found, warnings = {}, []
    week = year = last = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = WEEK_RE.match(line)
        if m:
            last = None
            week = int(m.group(1))
            year = int(m.group(2)) if m.group(2) else today.year
            if not m.group(2):  # veckoskifte kring nyår
                if week <= 2 and today.month == 12:
                    year += 1
                elif week >= 51 and today.month == 1:
                    year -= 1
            continue
        m = DAY_RE.match(line)
        if m and m.group(1).lower() in ALT_NAMES:      # alternativ på egen rad under dagen
            rows = [r.strip() for r in m.group(2).split("|") if r.strip()]
            if last is None:
                warnings.append(f"Rad {n}: alternativet måste stå direkt under en dag")
            elif rows:
                found.setdefault(last, []).extend(rows)
            continue
        if not m or m.group(1).lower() not in DAYS:
            warnings.append(f"Rad {n} förstods inte: {line}")
            continue
        if week is None:
            warnings.append(f"Rad {n}: skriv 'vecka NN' före första dagen")
            continue
        rows = [r.strip() for r in m.group(2).split("|") if r.strip()]
        try:
            d = date.fromisocalendar(year, week, DAYS[m.group(1).lower()])
        except ValueError:
            warnings.append(f"Rad {n}: vecka {week} finns inte {year}")
            last = None
            continue
        last = d.isoformat()
        if rows:
            found[last] = rows
    return found, warnings


def main():
    today = datetime.now(TZ).date()
    if not SRC.exists():
        print("Ingen data/matsedel.txt – inget att göra.")
        return
    found, warnings = parse(SRC.read_text(encoding="utf-8"), today)
    for w in warnings:
        print("::warning::" + w)
    old = {}
    if OUT.exists():
        try:
            old = {d["date"]: d for d in json.loads(OUT.read_text(encoding="utf-8")).get("days", [])}
        except Exception:
            pass
    days = dict(old)
    for d, rows in found.items():          # handskrivet vinner över allt annat
        days[d] = {"date": d, "main": rows[0], "alt": " / ".join(rows[1:])}
    if days != old:
        OUT.write_text(json.dumps({"updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
                                   "days": sorted(days.values(), key=lambda x: x["date"])},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    inline_seed("seed-menu", OUT)
    print(f"Läste {len(found)} dagar från {SRC} ({len(warnings)} varningar).")


if __name__ == "__main__":
    main()
