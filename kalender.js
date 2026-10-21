
/*
 * AUTOMATISK SKOLKALENDER
 * Hämtar alla händelser från calendar.json.
 * Inga manuella händelser kan läggas till i denna fil.
 *
 * calendar.json ska innehålla:
 * {
 *   "events": [
 *     {
 *       "id": "event-id",
 *       "title": "Matteprov",
 *       "start": "2026-10-28T07:00:00.000Z",
 *       "end": "2026-10-28T08:00:00.000Z",
 *       "allDay": false
 *     }
 *   ]
 * }
 */

var KALENDER = [];

(function () {
  "use strict";

  const CALENDAR_FILE = "./calendar.json";
  const TIME_ZONE = "Europe/Stockholm";
  let isLoading = false;
  let lastJson = "";

  // Hämtar ett datum i svensk tidszon i formatet ÅÅÅÅ-MM-DD.
  function stockholmDate(value) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).formatToParts(date);

    const get = type => parts.find(part => part.type === type).value;

    return `${get("year")}-${get("month")}-${get("day")}`;
  }

  // Flyttar ett datum ett antal dagar utan att påverkas av tidszonens sommartid.
  function addDateDays(dateString, amount) {
    const [year, month, day] = dateString.split("-").map(Number);
    const date = new Date(Date.UTC(year, month - 1, day + amount));

    return [
      date.getUTCFullYear(),
      String(date.getUTCMonth() + 1).padStart(2, "0"),
      String(date.getUTCDate()).padStart(2, "0")
    ].join("-");
  }

  // Hämtar klockslaget i svensk tidszon.
  function stockholmTime(value) {
    return new Intl.DateTimeFormat("sv-SE", {
      timeZone: TIME_ZONE,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23"
    }).format(new Date(value));
  }

  // Kategoriserar händelser så att den befintliga färgkodningen fungerar.
  function getType(title) {
    const text = String(title || "").toLowerCase();

    if (/\bprov\b/.test(text) || text.startsWith("prov")) {
      return "prov";
    }

    if (
      /\bläxa\b/.test(text) ||
      /\blaxa\b/.test(text) ||
      /\bhomework\b/.test(text)
    ) {
      return "läxa";
    }

    return "Aktivitet";
  }

  // Om titeln tydligt gäller 9A eller 9B visas den bara för den klassen.
  function getClass(title) {
    const match = String(title || "").match(/(?:^|\W)(9A|9B)(?=$|\W)/i);
    return match ? match[1].toUpperCase() : "";
  }

  // Gör om Google Calendar-händelser till formatet som index.html använder.
  function convertEvent(event, index) {
    if (!event || !event.title || !event.start || !event.end) {
      return null;
    }

    const startDate = stockholmDate(event.start);
    let endDate = stockholmDate(event.end);

    if (!startDate || !endDate) {
      return null;
    }

    if (event.allDay) {
      /*
       * Google Kalender använder ett exklusivt slutdatum för
       * heldagshändelser. En händelse 28–29 oktober slutar alltså
       * vid midnatt den 29:e, men ska bara visas den 28:e.
       */
      endDate = addDateDays(endDate, -1);
    } else {
      /*
       * En tidsbestämd händelse som slutar exakt vid midnatt
       * ska inte visas som en extra händelse nästa dag.
       */
      if (
        endDate > startDate &&
        stockholmTime(event.end) === "00:00"
      ) {
        endDate = addDateDays(endDate, -1);
      }
    }

    // Skydd mot felaktiga eller tomma datum.
    if (endDate < startDate) {
      endDate = startDate;
    }

    const title = String(event.title).trim();
    const allDay = Boolean(event.allDay);
    const startTime = allDay ? "" : stockholmTime(event.start);
    const endTime = allDay ? "" : stockholmTime(event.end);

    let text = title;

    // Lägg till tider för tidsbestämda händelser.
    if (!allDay) {
      text = `${startTime}–${endTime} · ${title}`;
    }

    const converted = {
      datum: startDate,
      typ: getType(title),
      amne: "",
      text: text,
      klass: getClass(title),
      _id: String(event.id || `${title}-${event.start}-${index}`)
    };

    if (endDate > startDate) {
      converted.till = endDate;
    }

    return converted;
  }

  // Ritar om kalendern efter att nya data har hämtats.
  function refreshCalendar() {
    if (typeof window.renderCal === "function") {
      window.renderCal();
      return;
    }

    // Om filen laddas före kalenderns huvudskript.
    window.addEventListener("load", function () {
      if (typeof window.renderCal === "function") {
        window.renderCal();
      }
    }, { once: true });
  }

  async function loadCalendar() {
    if (isLoading) {
      return;
    }

    isLoading = true;

    try {
      const response = await fetch(
        `${CALENDAR_FILE}?t=${Date.now()}`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      const rawEvents = Array.isArray(data)
        ? data
        : Array.isArray(data.events)
          ? data.events
          : null;

      if (!rawEvents) {
        throw new Error("calendar.json saknar en events-lista.");
      }

      const converted = rawEvents
        .map(convertEvent)
        .filter(Boolean)
        .sort((a, b) => {
          const dateCompare = a.datum.localeCompare(b.datum);
          if (dateCompare !== 0) return dateCompare;
          return a.text.localeCompare(b.text, "sv");
        });

      // Undvik att rita om kalendern om datan är oförändrad.
      const json = JSON.stringify(converted);

      if (json !== lastJson) {
        lastJson = json;
        KALENDER = converted;
        refreshCalendar();
      }

      console.info(
        `Skolkalendern är uppdaterad: ${KALENDER.length} händelser.`
      );
    } catch (error) {
      console.error(
        "Kunde inte hämta skolkalendern från calendar.json:",
        error
      );

      // Behåll senast hämtade data om nätverket tillfälligt inte fungerar.
    } finally {
      isLoading = false;
    }
  }

  // Hämta direkt när sidan öppnas.
  loadCalendar();

  // Kontrollera om Google Kalender har synkats till GitHub.
  // Sidan hämtar den nya filen automatiskt var femte minut.
  window.setInterval(loadCalendar, 5 * 60 * 1000);

  // Hämta igen när besökaren återvänder till fliken.
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      loadCalendar();
    }
  });
})();
