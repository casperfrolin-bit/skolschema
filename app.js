const TZ = "Europe/Stockholm";
const DAYS = ["måndag","tisdag","onsdag","torsdag","fredag"];
let offset = 0, schedule = [], menu = {days: []};

// ---------- Tid från internet (inte enhetens klocka) ----------
async function syncTime() {
  try {
    const t0 = Date.now();
    const r = await fetch("https://worldtimeapi.org/api/timezone/Europe/Stockholm", {cache:"no-store"});
    const j = await r.json(), t1 = Date.now();
    offset = j.unixtime * 1000 + (j.datetime.match(/\.(\d{3})/)?.[1] | 0) + (t1 - t0) / 2 - t1;
    return;
  } catch {}
  try { // reserv: serverns Date-header
    const t0 = Date.now();
    const r = await fetch(location.href, {method:"HEAD", cache:"no-store"});
    const t1 = Date.now(), d = r.headers.get("Date");
    if (d) offset = new Date(d).getTime() + 500 + (t1 - t0) / 2 - t1;
  } catch {}
}
const now = () => new Date(Date.now() + offset);

function parts(d) {
  const o = {};
  new Intl.DateTimeFormat("sv-SE", {timeZone:TZ, year:"numeric", month:"2-digit", day:"2-digit",
    hour:"2-digit", minute:"2-digit", second:"2-digit", hourCycle:"h23"})
    .formatToParts(d).forEach(p => o[p.type] = p.value);
  return o;
}
function isoWeek(y, m, d) {
  const t = new Date(Date.UTC(y, m - 1, d));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  return Math.ceil(((t - Date.UTC(t.getUTCFullYear(), 0, 1)) / 864e5 + 1) / 7);
}
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const hms = s => [Math.floor(s/3600), Math.floor(s%3600/60), s%60];
const toMin = s => { const [h,m] = s.split(":").map(Number); return h*60+m; };

// ---------- Tema ----------
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("theme", t); } catch {}
  const sun = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const moon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>';
  document.getElementById("themeBtn").innerHTML = t === "dark" ? sun : moon;
}
let saved = "light"; try { saved = localStorage.getItem("theme") || "light"; } catch {}
setTheme(saved);
document.getElementById("themeBtn").onclick = () =>
  setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

// ---------- Rendering ----------
function tick() {
  const d = now(), p = parts(d);
  const weekday = cap(new Intl.DateTimeFormat("sv-SE", {timeZone:TZ, weekday:"long"}).format(d));
  const month = new Intl.DateTimeFormat("sv-SE", {timeZone:TZ, month:"long"}).format(d);
  const week = isoWeek(+p.year, +p.month, +p.day);
  document.getElementById("datetime").textContent =
    `${p.hour}:${p.minute}:${p.second} · ${weekday} ${+p.day} ${month} ${p.year} (v. ${week})`;

  const sec = +p.hour*3600 + +p.minute*60 + +p.second;
  const lessons = schedule.filter(x => x.day === weekday.toLowerCase());
  const cur = lessons.find(x => sec >= toMin(x.start)*60 && sec < toMin(x.end)*60);
  const next = lessons.find(x => toMin(x.start)*60 > sec);
  const L = cur || next, el = id => document.getElementById(id);
  if (L) {
    el("lesson").textContent = (cur ? "" : "Nästa: ") + L.subject + (L.room ? ` (${L.room})` : "");
    el("lessonTime").textContent = `${L.start.replace(":",".")}–${L.end.replace(":",".")}`;
    const target = (cur ? toMin(L.end) : toMin(L.start)) * 60;
    const [h,m,s] = hms(target - sec);
    el("remaining").textContent = `${cur ? "Tid till slut" : "Tid till start"}: ${h} tim ${m} min ${s} sek`;
  } else {
    el("lesson").textContent = "Ingen lektion";
    el("lessonTime").textContent = "";
    el("remaining").textContent = "";
  }
  renderMenu(p, weekday.toLowerCase());
}

let menuKey = "";
function renderMenu(p, today) {
  // lördag/söndag: visa nästa vecka
  const base = new Date(Date.UTC(+p.year, +p.month-1, +p.day));
  const wd = base.getUTCDay() || 7;
  base.setUTCDate(base.getUTCDate() - (wd - 1) + (wd > 5 ? 7 : 0));
  const key = base.toISOString().slice(0,10) + today + menu.updated;
  if (key === menuKey) return;
  menuKey = key;
  document.getElementById("menu").innerHTML = DAYS.map((name, i) => {
    const dt = new Date(base); dt.setUTCDate(base.getUTCDate() + i);
    const iso = dt.toISOString().slice(0,10);
    const m = menu.days.find(x => x.date === iso);
    const nice = `${dt.getUTCDate()} ${new Intl.DateTimeFormat("sv-SE",{timeZone:"UTC",month:"short"}).format(dt)}`;
    return `<article class="day${name === today && wd <= 5 ? " active" : ""}">
      <div><div class="day-name">${cap(name)}</div><div class="day-date">${nice}</div></div>
      <div class="food"><div>${esc(m?.main || "Ingen uppgift")}</div><div>${esc(m?.alt || "")}</div></div></article>`;
  }).join("");
}
const esc = (s="") => s.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));

async function load() {
  try { schedule = await (await fetch("data/schedule.json", {cache:"no-store"})).json(); } catch {}
  try { menu = await (await fetch("data/menu.json", {cache:"no-store"})).json(); menu.days ||= []; } catch {}
  menuKey = ""; tick();
}
(async () => { await syncTime(); await load(); })();
setInterval(tick, 1000);
setInterval(syncTime, 10 * 60 * 1000);
setInterval(load, 30 * 60 * 1000);
