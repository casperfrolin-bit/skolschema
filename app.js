const DEFAULT_SETTINGS = {
  school: "Svensgårdsskolan",
  refreshMinutes: 30
};

function setCookie(name, value, days = 365) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}
function getCookie(name) {
  const key = encodeURIComponent(name) + "=";
  return document.cookie.split("; ").find(row => row.startsWith(key))?.slice(key.length) ?? null;
}
function loadSettings() {
  try {
    const saved = getCookie("schema_settings");
    return saved ? {...DEFAULT_SETTINGS, ...JSON.parse(decodeURIComponent(saved))} : {...DEFAULT_SETTINGS};
  } catch { return {...DEFAULT_SETTINGS}; }
}
function saveSettings(settings) {
  setCookie("schema_settings", JSON.stringify(settings));
}

let settings = loadSettings();
let schedule = [];

document.querySelector(".school-name").textContent = settings.school;
document.getElementById("schoolInput").value = settings.school;
document.getElementById("refreshInput").value = settings.refreshMinutes;

function parseTime(s) {
  const [h,m] = s.split(":").map(Number);
  return h*60+m;
}
function minutesNow() {
  const d = new Date();
  return d.getHours()*60+d.getMinutes()+d.getSeconds()/60;
}
function todayKey() {
  return new Intl.DateTimeFormat("sv-SE", {weekday:"long"}).format(new Date()).toLowerCase();
}
function formatDate() {
  return new Intl.DateTimeFormat("sv-SE",{weekday:"long",day:"numeric",month:"long"}).format(new Date());
}

async function loadSchedule() {
  try {
    const r = await fetch("data/schedule.json", {cache:"no-store"});
    schedule = await r.json();
  } catch {
    schedule = [];
  }
  renderSchedule();
}

async function loadMenu() {
  const status = document.getElementById("status");
  try {
    const r = await fetch("data/menu.json", {cache:"no-store"});
    if (!r.ok) throw new Error("menu.json saknas");
    const data = await r.json();
    const day = data.days?.find(x => x.date === new Date().toISOString().slice(0,10)) ||
                data.days?.[0];
    if (!day) throw new Error("Ingen meny");
    document.getElementById("foodMain").textContent = day.main || "Ingen uppgift";
    document.getElementById("foodAlt").textContent = day.alt || "";
    document.getElementById("foodDate").textContent = day.date ? day.date : formatDate();
    status.textContent = "Senast uppdaterad: " + (data.updated || "okänt");
  } catch {
    document.getElementById("foodMain").textContent = "Skolmaten kunde inte hämtas";
    document.getElementById("foodAlt").textContent = "Kontrollera data/menu.json";
    document.getElementById("foodDate").textContent = formatDate();
    status.textContent = "Menydata saknas";
  }
}

function renderSchedule() {
  const day = todayKey();
  const lessons = schedule.filter(x => x.day === day);
  const now = minutesNow();

  let current = lessons.find(x => now >= parseTime(x.start) && now < parseTime(x.end));
  if (!current) {
    current = lessons.find(x => parseTime(x.start) > now);
  }

  const currentSubject = document.getElementById("currentSubject");
  const currentTime = document.getElementById("currentTime");
  const timeLeft = document.getElementById("timeLeft");
  const progress = document.getElementById("progressBar");

  if (current) {
    currentSubject.textContent = current.subject;
    currentTime.textContent = `${current.start.replace(":",".")}–${current.end.replace(":",".")}`;
    const start = parseTime(current.start), end = parseTime(current.end);
    const remaining = Math.max(0, Math.ceil(end - now));
    const pct = Math.min(100, Math.max(0, ((now-start)/(end-start))*100));
    timeLeft.textContent = now >= start && now < end ? `${remaining} min kvar` : "Nästa lektion";
    progress.style.width = `${pct}%`;
  } else {
    currentSubject.textContent = "Ingen lektion";
    currentTime.textContent = "";
    timeLeft.textContent = "Skoldagen är slut";
    progress.style.width = "0%";
  }

  const upcoming = lessons.filter(x => parseTime(x.end) > now).slice(0, 5);
  document.getElementById("nextLessons").innerHTML = upcoming.map(x => `
    <article class="lesson">
      <div>
        <div class="lesson-name">${escapeHtml(x.subject)}</div>
        <div class="lesson-room">${escapeHtml(x.room || "")}</div>
      </div>
      <div class="lesson-time">${x.start.replace(":",".")}–${x.end.replace(":",".")}</div>
    </article>
  `).join("");
}

function escapeHtml(s="") {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function updateClock() {
  document.getElementById("clock").textContent = new Intl.DateTimeFormat("sv-SE", {
    hour:"2-digit", minute:"2-digit"
  }).format(new Date());
  renderSchedule();
}
document.getElementById("settingsBtn").onclick = () => document.getElementById("settingsDialog").showModal();
document.getElementById("saveSettings").onclick = () => {
  settings.school = document.getElementById("schoolInput").value.trim() || DEFAULT_SETTINGS.school;
  settings.refreshMinutes = Math.max(5, Number(document.getElementById("refreshInput").value) || 30);
  saveSettings(settings);
  document.querySelector(".school-name").textContent = settings.school;
  setTimeout(loadMenu, 100);
};

loadSchedule();
loadMenu();
updateClock();
setInterval(updateClock, 1000);
setInterval(loadMenu, settings.refreshMinutes * 60 * 1000);
