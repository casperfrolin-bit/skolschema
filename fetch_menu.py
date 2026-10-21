"""Hämtar Svensgårdsskolans offentliga matsedel och uppdaterar menu.json/index.html.

Försöker först Skolmatens publika RSS/JSON-flöde (ingen API-nyckel behövs).
Om det inte fungerar kan den gamla officiella API-metoden användas via SKOLMATEN_TOKEN.
"""
import email.utils
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")
OUT = pathlib.Path("menu.json")
SCHEDULE = pathlib.Path("schedule.json")
INDEX = pathlib.Path("index.html")
API = "https://skolmaten.se/api/4"
SCHOOL_NAME = "Svensgårdsskolan"
SCHOOL_CACHE = pathlib.Path("school_id.txt")
# Vanliga slug-varianter; varje svar verifieras mot skolans namn i feedens titel.
PUBLIC_SLUGS = ("svensgardsskolan", "svensgårdsskolan", "svensgardsskolan-helsingborg")


def get_text(url, headers=None):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SkolmatSida/1.0)",
            "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml, */*",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def api_get(path, token, **params):
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    return json.loads(get_text(url, {"client-token": token, "Accept": "application/json"}))


def _norm(value):
    return re.sub(r"[^a-zåäö0-9]", "", (value or "").lower())


def find_school_id(token):
    sid = os.environ.get("SKOLMATEN_SCHOOL_ID", "").strip()
    if sid:
        return sid
    if SCHOOL_CACHE.exists() and SCHOOL_CACHE.read_text(encoding="utf-8").strip():
        return SCHOOL_CACHE.read_text(encoding="utf-8").strip()
    want = _norm(SCHOOL_NAME)
    for province in api_get("provinces", token).get("provinces", []):
        for district in api_get("districts", token, province=province["id"]).get("districts", []):
            time.sleep(0.1)
            for school in api_get("schools", token, district=district["id"]).get("schools", []):
                if _norm(school.get("name", "")) == want:
                    SCHOOL_CACHE.write_text(str(school["id"]), encoding="utf-8")
                    print(f"Hittade {school['name']} (id {school['id']})")
                    return str(school["id"])
    raise RuntimeError(f"Hittade ingen skola som heter {SCHOOL_NAME} via API:t")


def menu_from_api(token, today):
    sid = find_school_id(token)
    out = {}
    for i, offset in enumerate((0, 7)):
        year, week, _ = (today + timedelta(days=offset)).isocalendar()
        try:
            data = api_get(f"menu/{sid}", token, year=year, week=week)
        except Exception as exc:
            if i == 0:
                raise
            print(f"Vecka {week} kunde inte hämtas: {exc}")
            continue
        for day in (data.get("WeekState") or {}).get("Days") or []:
            if day.get("cancelled"):
                continue
            rows = [m["name"].strip() for m in day.get("Meals") or [] if m.get("name", "").strip()]
            if rows and day.get("date"):
                out[day["date"][:10]] = rows
    return out


def _xml_local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element, wanted):
    for child in element.iter():
        if _xml_local(child.tag) == wanted.lower() and child.text:
            return child.text.strip()
    return ""


def _clean_meals(value):
    value = html.unescape(value or "")
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:p|div|li)>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    rows = []
    for part in value.splitlines():
        part = re.sub(r"\s+", " ", part).strip(" ,\t\r\n")
        if part and part not in rows:
            rows.append(part)
    return rows


def _parse_public_feed(raw, expected_week):
    root = ET.fromstring(raw)
    title = _child_text(root, "title")
    if _norm(SCHOOL_NAME) not in _norm(title):
        return {}
    out = {}
    entries = [el for el in root.iter() if _xml_local(el.tag) in ("item", "entry")]
    for entry in entries:
        date_text = (_child_text(entry, "pubDate") or _child_text(entry, "published")
                     or _child_text(entry, "updated") or _child_text(entry, "date"))
        if not date_text:
            continue
        try:
            parsed = email.utils.parsedate_to_datetime(date_text)
            if parsed is None:
                parsed = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
            day = parsed.date().isoformat()
        except Exception:
            try:
                day = datetime.fromisoformat(date_text.replace("Z", "+00:00")).date().isoformat()
            except Exception:
                continue
        if datetime.fromisoformat(day).date().isocalendar().week != expected_week:
            continue
        summary = (_child_text(entry, "description") or _child_text(entry, "summary")
                   or _child_text(entry, "content"))
        meals = _clean_meals(summary)
        if meals:
            out[day] = meals
    return out


def menu_from_public_feed(today):
    """Hämta matsedeln direkt från den publika Skolmaten-endpointen utan API-token."""
    found = {}
    monday = today - timedelta(days=today.weekday())
    errors = []
    # Hämta ungefär ett helt läsår bakåt/framåt så att veckoväljaren fungerar över fler månader.
    # API:t returnerar bara dagar som faktiskt har publicerade maträtter.
    for offset in range(-26, 31):
        target = monday + timedelta(days=7 * offset)
        iso = target.isocalendar()
        url = (
            f"{API}/menu/school/svensgardsskolan?"
            + urllib.parse.urlencode({"year": iso.year, "week": iso.week})
        )
        try:
            payload = json.loads(get_text(url, {"Accept": "application/json"}))
            week_state = payload.get("WeekState") or {}
            for day in week_state.get("Days") or []:
                if day.get("cancelled"):
                    continue
                date_text = str(day.get("date", ""))[:10]
                if not date_text:
                    continue
                rows = [
                    str(meal.get("name", "")).strip()
                    for meal in (day.get("Meals") or [])
                    if str(meal.get("name", "")).strip()
                ]
                if rows:
                    found[date_text] = rows
        except Exception as exc:
            errors.append(f"{iso.year}-v{iso.week}: {exc}")
    if found:
        print(f"Hämtade {len(found)} dagar från Skolmatens publika JSON-API.")
    else:
        print("Skolmatens publika JSON-API gav inga maträtter. " + " | ".join(errors[-3:]))
    return found


def inline_seed(tag, path):
    try:
        if not path.exists():
            return
        html_doc = INDEX.read_text(encoding="utf-8")
        data = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False).replace("<", "\\u003c")
        pattern = re.compile(r'(<script id="%s" type="application/json">).*?(</script>)' % tag, re.S)
        new, count = pattern.subn(lambda match: match.group(1) + data + match.group(2), html_doc, count=1)
        if count and new != html_doc:
            INDEX.write_text(new, encoding="utf-8")
    except Exception as exc:
        print(f"Kunde inte uppdatera inbyggd data ({tag}): {exc}")


def main():
    inline_seed("seed-schedule", SCHEDULE)
    today = datetime.now(TZ).date()
    found = menu_from_public_feed(today)

    # Fallback: det officiella JSON-API:t om den publika RSS-källan inte fungerar.
    if not found:
        token = os.environ.get("SKOLMATEN_TOKEN", "").strip()
        if token:
            found = menu_from_api(token, today)
        else:
            print("Ingen matsedel hittades i publika flöden och SKOLMATEN_TOKEN saknas.")
            sys.exit(1)

    if not found:
        print("Källan svarade men innehöll inga maträtter för denna eller nästa vecka.")
        sys.exit(1)

    days = {}
    if OUT.exists():
        try:
            for item in json.loads(OUT.read_text(encoding="utf-8")).get("days", []):
                days[item["date"]] = item
        except Exception:
            pass
    for date_text, rows in found.items():
        days[date_text] = {"date": date_text, "main": rows[0], "alt": " / ".join(rows[1:])}
    cutoff = (today - timedelta(days=180)).isoformat()
    days = {key: value for key, value in days.items() if key >= cutoff}
    OUT.write_text(
        json.dumps(
            {"updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
             "days": sorted(days.values(), key=lambda item: item["date"])},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    inline_seed("seed-menu", OUT)
    print(f"Sparade {len(found)} dagar.")


if __name__ == "__main__":
    main()
