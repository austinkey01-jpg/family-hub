// FamilyHub touchscreen UI. No build step, no frameworks: easy to hack on the Pi.
const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const S = { weekStart: mondayOf(new Date()), view: "week", tab: "today", list: null, hidden: new Set(), data: null, who: null };

function mondayOf(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; }
function ymd(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function fmtTime(iso) {
  if (iso.length <= 10) return "All day";
  const d = new Date(iso.length === 16 ? iso + ":00" : iso);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).replace(":00", "").toLowerCase();
}
const NEUTRAL = "#8A8F98";

async function api(path, opts = {}) {
  const r = await fetch("/api/" + path, { headers: { "Content-Type": "application/json" }, ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined });
  if (opts.raw) return r;
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Something went wrong");
  return j;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add("hidden"), 3500); }

// ---------------------------------------------------------------- data
async function load() {
  try {
    S.data = await api(`state?start=${ymd(S.weekStart)}&days=7`);
    render();
  } catch (e) { toast("Can't reach FamilyHub server"); }
}

function render() { renderFamily(); renderWeather(); renderCalendar(); renderSide(); }

// ---------------------------------------------------------------- header
function tick() {
  const now = new Date();
  $("#time").textContent = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  $("#date").textContent = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
  const h = now.getHours();
  document.body.classList.toggle("night", h >= 21 || h < 6);
}

function renderFamily() {
  const f = $("#family"); f.innerHTML = "";
  for (const m of S.data.members) {
    const c = el("button", "chip" + (S.hidden.has(m.id) ? " off" : ""), `<span class="dot" style="background:${m.color}">${esc(m.emoji)}</span>${esc(m.name)}`);
    c.onclick = () => { S.hidden.has(m.id) ? S.hidden.delete(m.id) : S.hidden.add(m.id); render(); };
    f.append(c);
  }
}

const WMO = { 0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 48: "🌫️", 51: "🌦️", 53: "🌦️", 55: "🌧️", 61: "🌧️", 63: "🌧️", 65: "🌧️",
  71: "🌨️", 73: "🌨️", 75: "❄️", 80: "🌦️", 81: "🌧️", 82: "⛈️", 95: "⛈️", 96: "⛈️", 99: "⛈️" };
function renderWeather() {
  const w = S.data.weather, box = $("#weather");
  if (!w) { box.innerHTML = ""; return; }
  let html = `<div class="now">${WMO[w.current.weather_code] || "🌡️"} ${Math.round(w.current.temperature_2m)}°</div>`;
  for (let i = 1; i < Math.min(5, w.daily.time.length); i++) {
    const d = new Date(w.daily.time[i] + "T12:00");
    html += `<div class="day">${d.toLocaleDateString([], { weekday: "short" })}<b>${WMO[w.daily.weather_code[i]] || ""}</b>${Math.round(w.daily.temperature_2m_max[i])}° / ${Math.round(w.daily.temperature_2m_min[i])}°</div>`;
  }
  box.innerHTML = html;
}

// ---------------------------------------------------------------- calendar
function visibleEvents() {
  return S.data.events.filter((e) => !e.member_id || !S.hidden.has(e.member_id));
}
function eventsOn(day) {
  const d0 = ymd(day), d1 = ymd(addDays(day, 1));
  return visibleEvents().filter((e) => e.start.slice(0, 10) < d1 && (e.all_day ? e.end.slice(0, 10) > d0 : e.end.slice(0, 10) >= d0 && e.end > d0));
}
function evButton(e, withTime = true) {
  const b = el("button", "ev" + (e.all_day ? " allday" : ""));
  b.style.setProperty("--c", e.color || NEUTRAL);
  b.innerHTML = (e.all_day || !withTime ? "" : `<div class="t">${fmtTime(e.start)}</div>`) + `<div class="n">${esc(e.title)}</div>`;
  b.onclick = () => showDetail(e);
  return b;
}

function renderCalendar() {
  const end = addDays(S.weekStart, 6);
  const opt = { month: "short", day: "numeric" };
  $("#range").textContent = `${S.weekStart.toLocaleDateString([], opt)} – ${end.toLocaleDateString([], opt)}`;
  $("#week").classList.toggle("hidden", S.view !== "week");
  $("#agenda").classList.toggle("hidden", S.view !== "agenda");
  const todayStr = S.data.today;

  if (S.view === "week") {
    const wk = $("#week"); wk.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const day = addDays(S.weekStart, i);
      const col = el("div", "day" + (ymd(day) === todayStr ? " today" : ""));
      col.append(el("div", "day-head", `<span class="dow">${day.toLocaleDateString([], { weekday: "short" })}</span><span class="num">${day.getDate()}</span>`));
      const body = el("div", "day-body");
      const evs = eventsOn(day);
      evs.forEach((e) => body.append(evButton(e)));
      if (!evs.length) body.append(el("div", "empty", "—"));
      body.ondblclick = () => openAdd(ymd(day));
      col.append(body); wk.append(col);
    }
  } else {
    const ag = $("#agenda"); ag.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const day = addDays(S.weekStart, i), evs = eventsOn(day);
      if (!evs.length) continue;
      ag.append(el("h4", "", day.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })));
      evs.forEach((e) => { const b = evButton(e, false); b.prepend(el("div", "t", fmtTime(e.start))); ag.append(b); });
    }
    if (!ag.children.length) ag.append(el("div", "empty", "Nothing on the calendar this week."));
  }
}

function showDetail(e) {
  $("#dTitle").textContent = e.title;
  const s = new Date(e.start.length === 10 ? e.start + "T00:00" : e.start);
  $("#dWhen").textContent = s.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" }) +
    (e.all_day ? " · All day" : ` · ${fmtTime(e.start)} – ${fmtTime(e.end)}`) + (e.member ? ` · ${e.member}` : "");
  $("#dWhere").textContent = e.location || "";
  const del = $("#dDelete");
  del.classList.toggle("hidden", e.source !== "local");
  del.onclick = async () => { await api(`events/${e.id}`, { method: "DELETE" }); close("#detail"); load(); };
  $("#detail").classList.remove("hidden");
}

// ---------------------------------------------------------------- side panel
function renderSide() {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === S.tab));
  for (const t of ["today", "chores", "lists"]) $("#tab-" + t).classList.toggle("hidden", S.tab !== t);
  renderToday(); renderChores(); renderLists();
}

function renderToday() {
  const box = $("#tab-today"); box.innerHTML = "";
  const sug = S.data.suggestions;
  if (!sug.length) box.append(el("div", "empty", "All clear. Nothing needs your attention. 🎉"));
  for (const s of sug) {
    const c = el("div", "sugg " + s.kind, `<div class="i">${s.icon}</div><div class="b"><div class="h">${esc(s.title)}</div><div class="d">${esc(s.detail)}</div><div class="acts"></div></div>`);
    const acts = c.querySelector(".acts");
    if (s.action?.type === "add_items") {
      const go = el("button", "go", esc(s.action.label));
      go.onclick = async () => {
        for (const text of s.action.items) await api(`lists/${s.action.list_id}/items`, { method: "POST", body: { text } });
        toast(`Added: ${s.action.items.join(", ")}`); load();
      };
      acts.append(go);
    }
    const no = el("button", "", "Dismiss");
    no.onclick = async () => { await api("suggestions", { method: "POST", body: { key: s.key } }); load(); };
    acts.append(no);
    box.append(c);
  }
}

function renderChores() {
  const box = $("#tab-chores"); box.innerHTML = "";
  const pts = Object.fromEntries(S.data.points.map((p) => [p.id, p.points]));
  const groups = new Map();
  for (const c of S.data.chores) {
    if (c.member_id && S.hidden.has(c.member_id)) continue;
    const k = c.member_id || 0;
    if (!groups.has(k)) groups.set(k, { name: c.member || "Anyone", color: c.color || NEUTRAL, items: [] });
    groups.get(k).items.push(c);
  }
  if (!groups.size) box.append(el("div", "empty", "No chores today. Add them in config or via the API."));
  for (const [mid, g] of groups) {
    const done = g.items.filter((c) => c.done).length;
    const p = el("div", "person"); p.style.setProperty("--c", g.color);
    p.append(el("div", "person-head", `${esc(g.name)} · ${done}/${g.items.length}<span class="pts">⭐ ${pts[mid] || 0} this week</span>`));
    for (const c of g.items) {
      const t = el("button", "task" + (c.done ? " done" : ""), `<span class="box">${c.done ? "✓" : ""}</span><span class="label">${esc(c.title)}</span><span class="pt">+${c.points}</span>`);
      t.onclick = async () => {
        const r = await api(`chores/${c.id}/toggle`, { method: "POST", body: { day: S.data.today } });
        if (r.done) { p.classList.add("celebrate"); if (g.items.every((x) => x.done || x.id === c.id)) toast(`🎉 ${g.name} finished everything!`); }
        load();
      };
      p.append(t);
    }
    box.append(p);
  }
}

function renderLists() {
  const box = $("#tab-lists"); box.innerHTML = "";
  const lists = S.data.lists;
  if (!lists.length) return;
  if (!S.list || !lists.find((l) => l.id === S.list)) S.list = lists[0].id;
  const tabs = el("div", "list-tabs");
  for (const l of lists) {
    const open = l.items.filter((i) => !i.done).length;
    const b = el("button", l.id === S.list ? "on" : "", `${esc(l.name)}${open ? ` (${open})` : ""}`);
    b.onclick = () => { S.list = l.id; renderLists(); };
    tabs.append(b);
  }
  box.append(tabs);
  const list = lists.find((l) => l.id === S.list);
  const row = el("form", "add-row", `<input placeholder="Add to ${esc(list.name)}…"><button>Add</button>`);
  row.onsubmit = async (ev) => {
    ev.preventDefault();
    const inp = row.querySelector("input"); if (!inp.value.trim()) return;
    await api(`lists/${list.id}/items`, { method: "POST", body: { text: inp.value } });
    inp.value = ""; await load(); $("#tab-lists input")?.focus();
  };
  box.append(row);
  const wrap = el("div", "person");
  for (const i of list.items) {
    const t = el("button", "task" + (i.done ? " done" : ""), `<span class="box">${i.done ? "✓" : ""}</span><span class="label">${esc(i.text)}</span>`);
    t.onclick = async () => { await api(`items/${i.id}/toggle`, { method: "POST" }); load(); };
    wrap.append(t);
  }
  if (list.items.length) box.append(wrap);
  if (list.items.some((i) => i.done)) {
    const clr = el("button", "link", "Clear checked items");
    clr.onclick = async () => { await api(`lists/${list.id}/clear`, { method: "POST" }); load(); };
    box.append(clr);
  }
}

// ---------------------------------------------------------------- add event
function openAdd(day) {
  const f = $("#eventForm"); f.reset();
  f.day.value = day || S.data.today;
  S.who = null;
  const who = $("#whoPick"); who.innerHTML = "";
  for (const m of [{ id: null, name: "Everyone", color: NEUTRAL }, ...S.data.members]) {
    const b = el("button", m.id === null ? "on" : "", esc(m.name)); b.type = "button";
    b.style.setProperty("--c", m.color);
    b.onclick = () => { S.who = m.id; who.querySelectorAll("button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); };
    who.append(b);
  }
  $("#quickWrap").classList.toggle("hidden", !S.data.features.ai);
  $("#quick").value = "";
  $("#sheet").classList.remove("hidden");
}
function close(sel) { $(sel).classList.add("hidden"); }

$("#eventForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const f = ev.target, allDay = f.all_day.checked || !f.start.value;
  const body = { title: f.title.value, all_day: allDay, member_id: S.who };
  if (allDay) { body.start = f.day.value; body.end = ymd(addDays(new Date(f.day.value + "T12:00"), 1)); }
  else {
    body.start = `${f.day.value}T${f.start.value}`;
    let endT = f.end.value;
    if (!endT) { const [h, m] = f.start.value.split(":").map(Number); endT = `${String(Math.min(h + 1, 23)).padStart(2, "0")}:${String(m).padStart(2, "0")}`; }
    body.end = `${f.day.value}T${endT}`;
  }
  await api("events", { method: "POST", body });
  close("#sheet"); toast("Added to the calendar"); load();
};

$("#quickGo").onclick = async () => {
  const text = $("#quick").value.trim(); if (!text) return;
  $("#quickGo").textContent = "…";
  try { const ev = await api("quick-add", { method: "POST", body: { text } }); close("#sheet"); toast(`Added “${ev.title}”`); load(); }
  catch (e) { toast(e.message); }
  finally { $("#quickGo").textContent = "Add"; }
};

// ---------------------------------------------------------------- brief + Dad's voice
async function loadBrief() {
  try {
    const { text } = await api("brief");
    if (!text) return;
    $("#briefText").textContent = text;
    $("#brief").classList.remove("hidden");
    $("#briefPlay").classList.toggle("hidden", !S.data?.features.voice);
  } catch (_) { /* brief is optional */ }
}
$("#briefPlay").onclick = async () => {
  const btn = $("#briefPlay"); btn.classList.add("playing");
  try {
    const r = await api("speak", { method: "POST", body: { text: $("#briefText").textContent }, raw: true });
    if (!r.ok) throw new Error("Voice isn't set up yet");
    const audio = new Audio(URL.createObjectURL(await r.blob()));
    audio.onended = () => btn.classList.remove("playing");
    await audio.play();
  } catch (e) { toast(e.message); btn.classList.remove("playing"); }
};

// ---------------------------------------------------------------- wiring
$("#prev").onclick = () => { S.weekStart = addDays(S.weekStart, -7); load(); };
$("#next").onclick = () => { S.weekStart = addDays(S.weekStart, 7); load(); };
$("#todayBtn").onclick = () => { S.weekStart = mondayOf(new Date()); load(); };
document.querySelectorAll(".seg button").forEach((b) => b.onclick = () => {
  S.view = b.dataset.view; document.querySelectorAll(".seg button").forEach((x) => x.classList.toggle("on", x === b)); renderCalendar();
});
document.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => { S.tab = b.dataset.tab; renderSide(); });
document.querySelectorAll("[data-close]").forEach((b) => b.onclick = () => b.closest(".sheet").classList.add("hidden"));
document.querySelectorAll(".sheet").forEach((s) => s.onclick = (e) => { if (e.target === s) s.classList.add("hidden"); });
$("#fab").onclick = () => openAdd();

tick(); setInterval(tick, 1000 * 15);
load().then(loadBrief);
setInterval(() => { if (document.querySelector(".sheet:not(.hidden)")) return; load(); }, 60 * 1000);
// Morning brief refreshes once an hour (cached server-side per day).
setInterval(loadBrief, 60 * 60 * 1000);

// ---------------------------------------------------------------- family settings
const PALETTE = ["#3B6EA8", "#C2557A", "#2E8B6A", "#D08A2E", "#7A5BB5", "#3E9AAE", "#B5523B", "#6B7F3A", "#8A8F98"];
const EMOJIS = ["🧔", "👨", "👩", "👱", "👵", "👴", "🧑", "👦", "👧", "👶", "🐶", "🐱", "⭐", "🌻", "⚽", "🎨", "🎸", "🦖", "🦄", "🚀"];
const F = { editing: null, color: PALETTE[0], emoji: "" };

function openFamily() { showFamList(); $("#familySheet").classList.remove("hidden"); }

function showFamList() {
  $("#famTitle").textContent = "Family";
  $("#famBack").classList.add("hidden");
  $("#famForm").classList.add("hidden");
  $("#famList").classList.remove("hidden");
  const box = $("#famPeople"); box.innerHTML = "";
  if (!S.data.members.length) box.append(el("div", "empty", "No one here yet. Add your first family member."));
  for (const m of S.data.members) {
    const row = el("button", "fam-row", `<span class="fam-dot" style="--c:${m.color}">${esc(m.emoji)}</span>${esc(m.name)}<span class="chev">›</span>`);
    row.onclick = () => showFamForm(m);
    box.append(row);
  }
}

function showFamForm(member) {
  F.editing = member || null;
  const used = new Set(S.data.members.map((m) => m.color));
  F.color = member?.color || PALETTE.find((c) => !used.has(c)) || PALETTE[0];
  F.emoji = member?.emoji || "";
  $("#famTitle").textContent = member ? `Edit ${member.name}` : "Add someone";
  $("#famBack").classList.remove("hidden");
  $("#famList").classList.add("hidden");
  const form = $("#famForm"); form.classList.remove("hidden");
  form.name.value = member?.name || "";
  const del = $("#famDelete");
  del.classList.toggle("hidden", !member); del.classList.remove("armed"); del.textContent = "Remove from family";
  renderFamPickers();
  if (!member) form.name.focus();
}

function renderFamPickers() {
  const dot = $("#famDot"); dot.style.setProperty("--c", F.color); dot.textContent = F.emoji;
  const sw = $("#famColors"); sw.innerHTML = "";
  for (const c of PALETTE) {
    const b = el("button", c === F.color ? "on" : ""); b.type = "button"; b.style.setProperty("--c", c);
    b.setAttribute("aria-label", "Color " + c);
    b.onclick = () => { F.color = c; renderFamPickers(); };
    sw.append(b);
  }
  const em = $("#famEmojis"); em.innerHTML = "";
  for (const e of ["", ...EMOJIS]) {
    const b = el("button", e === F.emoji ? "on" : "", e || "—"); b.type = "button";
    b.onclick = () => { F.emoji = e; renderFamPickers(); };
    em.append(b);
  }
}

$("#famForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const name = ev.target.name.value.trim();
  if (!name) { toast("Add a name first"); return; }
  const path = F.editing ? `members/${F.editing.id}` : "members";
  try {
    await api(path, { method: "POST", body: { name, color: F.color, emoji: F.emoji } });
    toast(F.editing ? `Saved ${name}` : `Welcome, ${name}!`);
    await load(); showFamList();
  } catch (e) { toast(e.message); }
};

$("#famDelete").onclick = async () => {
  const del = $("#famDelete");
  if (!del.classList.contains("armed")) {   // first tap asks, second tap removes
    del.classList.add("armed"); del.textContent = `Tap again to remove ${F.editing.name}`; return;
  }
  await api(`members/${F.editing.id}`, { method: "DELETE" });
  toast(`${F.editing.name} removed. Their events are still on the calendar.`);
  S.hidden.delete(F.editing.id);
  await load(); showFamList();
};

$("#gear").onclick = openFamily;
$("#famAdd").onclick = () => showFamForm(null);
$("#famBack").onclick = showFamList;
