// Hämtar den automatiskt uppdaterade matsedeln från menu.json.
// Formatet på sidan är veckobaserat; menu.json innehåller en rad per datum.
var MATSEDEL = {};

(function () {
  "use strict";
  const DAY_KEYS = ["mån", "tis", "ons", "tors", "fre", "lör", "sön"];

  function isoWeek(date) {
    const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
    const year = d.getUTCFullYear();
    const yearStart = new Date(Date.UTC(year, 0, 1));
    const week = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    return { year, week };
  }

  const loadedWeeks = new Set();
  const pendingWeeks = new Set();

  function addWeekPayload(payload, requestedYear, requestedWeek) {
    const days = Array.isArray(payload.days) ? payload.days : null;
    const legacyDays = payload.WeekState && Array.isArray(payload.WeekState.Days) ? payload.WeekState.Days : null;
    const list = days || legacyDays || [];
    const next = { ...MATSEDEL };
    const dayNames = ["mån", "tis", "ons", "tors", "fre", "lör", "sön"];
    for (const day of list) {
      if (day.cancelled) continue;
      const dateText = String(day.date || "").slice(0, 10);
      if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(dateText)) continue;
      const date = new Date(dateText + "T12:00:00Z");
      const { year, week } = isoWeek(date);
      const key = year + "-v" + String(week).padStart(2, "0");
      const dayKey = dayNames[(date.getUTCDay() + 6) % 7];
      const meals = [];
      if (typeof day.main === "string" && day.main.trim()) meals.push(day.main.trim());
      if (typeof day.alt === "string" && day.alt.trim()) meals.push(...day.alt.split(/\\s+\\/\\s+/).map(x => x.trim()).filter(Boolean));
      if (!days && Array.isArray(day.Meals)) {
        for (const meal of day.Meals) if (meal && typeof meal.name === "string" && meal.name.trim()) meals.push(meal.name.trim());
      }
      if (meals.length) { if (!next[key]) next[key] = {}; next[key][dayKey] = meals; }
    }
    MATSEDEL = next;
    loadedWeeks.add(requestedYear + "-v" + String(requestedWeek).padStart(2, "0"));
    window.dispatchEvent(new Event("matsedelupdated"));
  }

  window.loadMenuWeek = async function (year, week) {
    const key = year + "-v" + String(week).padStart(2, "0");
    if (loadedWeeks.has(key) || pendingWeeks.has(key)) return;
    pendingWeeks.add(key);
    try {
      const url = "https://skolmaten.se/api/4/menu/school/svensgardsskolan?year=" + encodeURIComponent(year) + "&week=" + encodeURIComponent(week);
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error("Skolmaten svarade " + response.status);
      addWeekPayload(await response.json(), year, week);
      console.info("Hämtade vald matsedelsvecka:", key);
    } catch (error) {
      console.warn("Kunde inte hämta vald matsedelsvecka direkt från Skolmaten:", key, error);
    } finally { pendingWeeks.delete(key); }
  };

  async function loadMenu() {
    try {
      const response = await fetch("./menu.json?t=" + Date.now(), { cache: "no-store" });
      if (!response.ok) throw new Error("menu.json svarade " + response.status);
      const data = await response.json();
      const next = {};
      for (const day of (Array.isArray(data.days) ? data.days : [])) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(day.date || "")) continue;
        const date = new Date(day.date + "T12:00:00Z");
        const { year, week } = isoWeek(date);
        const key = year + "-v" + String(week).padStart(2, "0");
        const dayKey = DAY_KEYS[(date.getUTCDay() + 6) % 7];
        const meals = [];
        if (typeof day.main === "string" && day.main.trim()) meals.push(day.main.trim());
        if (typeof day.alt === "string" && day.alt.trim()) {
          meals.push(...day.alt.split(/\s+\/\s+/).map(x => x.trim()).filter(Boolean));
        }
        if (!next[key]) next[key] = {};
        next[key][dayKey] = meals;
      }
      MATSEDEL = next;
      // Uppdatera sidan även om data hämtades innan sidans eventlyssnare hann registreras.
      window.dispatchEvent(new Event("matsedelupdated"));
      if (typeof window.renderMenu === "function") window.renderMenu();
      console.info("Matsedel laddad:", data.updated || "utan tidsstämpel", "veckor:", Object.keys(next).length);
    } catch (error) {
      console.warn("Kunde inte ladda menu.json:", error);
    }
  }

  loadMenu();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadMenu();
  });
})();
