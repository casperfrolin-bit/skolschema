"""Hämtar skolmaten för Svensgårdsskolan (RSS) och skriver data/menu.json."""
import json, re, html, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "https://skolmaten.se/svensgardsskolan/rss/weeks/?offset={}"
TZ = ZoneInfo("Europe/Stockholm")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read()

days = {}
for offset in (0, 1):
    try:
        root = ET.fromstring(get(BASE.format(offset)))
    except Exception as e:
        print("Kunde inte hämta offset", offset, e); continue
    for item in root.iter("item"):
        pub = item.findtext("pubDate")
        if not pub: continue
        date = parsedate_to_datetime(pub).astimezone(TZ).date().isoformat()
        desc = html.unescape(item.findtext("description") or "")
        rows = [re.sub(r"<[^>]+>", "", r).strip() for r in re.split(r"<br\s*/?>|\n", desc)]
        rows = [r for r in rows if r]
        if rows:
            days[date] = {"date": date, "main": rows[0], "alt": " / ".join(rows[1:])}

if days:
    out = {"updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"), "days": sorted(days.values(), key=lambda d: d["date"])}
    json.dump(out, open("data/menu.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("Sparade", len(days), "dagar")
else:
    print("Inga dagar hittades - behåller gamla menu.json")
