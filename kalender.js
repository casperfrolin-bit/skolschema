
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
  let rawEventsCache = null;

  const CLASS_9A_CALENDAR = "9A Svensgårdsskolan 26/27";
  const GERMAN_CALENDAR = "Tyska-Deutsch 9";

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

  // Identifiera prov, glosor, lov och studiedagar. Övriga händelser blir aktiviteter.
  function getType(title, calendar, description) {
    const text = `${title || ""} ${description || ""}`.toLowerCase();
    if (/\bprov\b|\btest\b|\bexamination\b/.test(text)) return "prov";
    if (/\bglosor\b|\bglosa\b/.test(text)) return "glosor";
    if (/\bstudiedag(?:ar)?\b|\bstudiedagarna\b/.test(text)) return "studiedag";
    if (/\blov\b|\bhöstlov\b|\bsportlov\b|\bpåsklov\b|\bsommarlov\b|\bjullov\b/.test(text)) return "lov";
    return "aktivitet";
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

    const description = String(event.description || "").trim();
    const calendar = String(event.calendar || "").trim();
    const calendarColor = String(event.calendarColor || event.color || "").trim();
    const converted = {
      datum: startDate,
      typ: getType(title, calendar, description),
      amne: "",
      text: text,
      title: title,
      description: description,
      calendar: calendar,
      calendarColor: calendarColor,
      timeText: allDay ? "Heldag" : `${startTime}–${endTime}`,
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

  // Filtrera om direkt när klassväljaren ändras, utan att hämta sidan igen.
  function applyCalendarForSelectedClass() {
    // Om data inte hunnit hämtas ännu, starta/fortsätt hämtningen.
    if (!Array.isArray(rawEventsCache)) {
      loadCalendar();
      return;
    }

    const selectedClass = String(
      document.getElementById("classSel")?.value || "9B"
    ).toUpperCase();

    const classroomEvents = rawEventsCache.filter(event => {
      const name = String(event && event.calendar || "").trim();
      const calendarId = String(event && event.calendarId || "").trim();

      if (!name || name.includes("@")) return false;
      if (/^helgdagar i sverige$/i.test(name)) return false;
      if (calendarId && !/@group\\.calendar\\.google\\.com$/i.test(calendarId) &&
          !/@group\\.v\\.calendar\\.google\\.com$/i.test(calendarId)) return false;

      if (selectedClass === "9A") {
        return name === CLASS_9A_CALENDAR || name === GERMAN_CALENDAR;
      }

      return name !== CLASS_9A_CALENDAR;
    });

    const converted = classroomEvents
      .map(convertEvent)
      .filter(Boolean)
      .sort((a, b) => {
        const dateCompare = a.datum.localeCompare(b.datum);
        if (dateCompare !== 0) return dateCompare;
        return a.text.localeCompare(b.text, "sv");
      });

    const json = JSON.stringify(converted);
    lastJson = json;
    // Byt alltid den aktiva listan och rita om vid klassbyte.
    KALENDER = converted;
    refreshCalendar();

    console.info(`Skolkalendern uppdaterad för ${selectedClass}: ${KALENDER.length} händelser.`);
  }

  // Kan anropas från klassväljaren i index.html.
  window.refreshSchoolCalendarForClass = applyCalendarForSelectedClass;

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

      rawEventsCache = rawEvents;
      applyCalendarForSelectedClass();


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
