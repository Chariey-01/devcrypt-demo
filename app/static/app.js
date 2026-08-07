const ICON_PATHS = {"activity": "<path d=\"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2\" />", "alert-triangle": "<path d=\"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3\" /><path d=\"M12 9v4\" /><path d=\"M12 17h.01\" />", "binary": "<rect x=\"14\" y=\"14\" width=\"4\" height=\"6\" rx=\"2\" /><rect x=\"6\" y=\"4\" width=\"4\" height=\"6\" rx=\"2\" /><path d=\"M6 20h4\" /><path d=\"M14 10h4\" /><path d=\"M6 14h2v6\" /><path d=\"M14 4h2v6\" />", "bug": "<path d=\"M12 20v-9\" /><path d=\"M14 7a4 4 0 0 1 4 4v3a6 6 0 0 1-12 0v-3a4 4 0 0 1 4-4z\" /><path d=\"M14.12 3.88 16 2\" /><path d=\"M21 21a4 4 0 0 0-3.81-4\" /><path d=\"M21 5a4 4 0 0 1-3.55 3.97\" /><path d=\"M22 13h-4\" /><path d=\"M3 21a4 4 0 0 1 3.81-4\" /><path d=\"M3 5a4 4 0 0 0 3.55 3.97\" /><path d=\"M6 13H2\" /><path d=\"m8 2 1.88 1.88\" /><path d=\"M9 7.13V6a3 3 0 1 1 6 0v1.13\" />", "check": "<path d=\"M20 6 9 17l-5-5\" />", "chevron-left": "<path d=\"m15 18-6-6 6-6\" />", "chevron-right": "<path d=\"m9 18 6-6-6-6\" />", "cpu": "<path d=\"M12 20v2\" /><path d=\"M12 2v2\" /><path d=\"M17 20v2\" /><path d=\"M17 2v2\" /><path d=\"M2 12h2\" /><path d=\"M2 17h2\" /><path d=\"M2 7h2\" /><path d=\"M20 12h2\" /><path d=\"M20 17h2\" /><path d=\"M20 7h2\" /><path d=\"M7 20v2\" /><path d=\"M7 2v2\" /><rect x=\"4\" y=\"4\" width=\"16\" height=\"16\" rx=\"2\" /><rect x=\"8\" y=\"8\" width=\"8\" height=\"8\" rx=\"1\" />", "crosshair": "<circle cx=\"12\" cy=\"12\" r=\"10\" /><line x1=\"22\" x2=\"18\" y1=\"12\" y2=\"12\" /><line x1=\"6\" x2=\"2\" y1=\"12\" y2=\"12\" /><line x1=\"12\" x2=\"12\" y1=\"6\" y2=\"2\" /><line x1=\"12\" x2=\"12\" y1=\"22\" y2=\"18\" />", "database": "<ellipse cx=\"12\" cy=\"5\" rx=\"9\" ry=\"3\" /><path d=\"M3 5V19A9 3 0 0 0 21 19V5\" /><path d=\"M3 12A9 3 0 0 0 21 12\" />", "eye": "<path d=\"M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0\" /><circle cx=\"12\" cy=\"12\" r=\"3\" />", "file-lock-2": "<path d=\"M4 9.8V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2h-3\" /><path d=\"M14 2v5a1 1 0 0 0 1 1h5\" /><path d=\"M9 17v-2a2 2 0 0 0-4 0v2\" /><rect width=\"8\" height=\"5\" x=\"3\" y=\"17\" rx=\"1\" />", "fingerprint": "<path d=\"M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4\" /><path d=\"M14 13.12c0 2.38 0 6.38-1 8.88\" /><path d=\"M17.29 21.02c.12-.6.43-2.3.5-3.02\" /><path d=\"M2 12a10 10 0 0 1 18-6\" /><path d=\"M2 16h.01\" /><path d=\"M21.8 16c.2-2 .131-5.354 0-6\" /><path d=\"M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2\" /><path d=\"M8.65 22c.21-.66.45-1.32.57-2\" /><path d=\"M9 6.8a6 6 0 0 1 9 5.2v2\" />", "flame-kindling": "<path d=\"M12 2c1 3 2.5 3.5 3.5 4.5A5 5 0 0 1 17 10a5 5 0 1 1-10 0c0-.3 0-.6.1-.9a2 2 0 1 0 3.3-2C8 4.5 11 2 12 2Z\" /><path d=\"m5 22 14-4\" /><path d=\"m5 18 14 4\" />", "gauge": "<path d=\"m12 14 4-4\" /><path d=\"M3.34 19a10 10 0 1 1 17.32 0\" />", "globe": "<circle cx=\"12\" cy=\"12\" r=\"10\" /><path d=\"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20\" /><path d=\"M2 12h20\" />", "hash": "<line x1=\"4\" x2=\"20\" y1=\"9\" y2=\"9\" /><line x1=\"4\" x2=\"20\" y1=\"15\" y2=\"15\" /><line x1=\"10\" x2=\"8\" y1=\"3\" y2=\"21\" /><line x1=\"16\" x2=\"14\" y1=\"3\" y2=\"21\" />", "key": "<path d=\"m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4\" /><path d=\"m21 2-9.6 9.6\" /><circle cx=\"7.5\" cy=\"15.5\" r=\"5.5\" />", "lock-keyhole": "<circle cx=\"12\" cy=\"16\" r=\"1\" /><rect x=\"3\" y=\"10\" width=\"18\" height=\"12\" rx=\"2\" /><path d=\"M7 10V7a5 5 0 0 1 10 0v3\" />", "lock": "<rect width=\"18\" height=\"11\" x=\"3\" y=\"11\" rx=\"2\" ry=\"2\" /><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" />", "network": "<rect x=\"16\" y=\"16\" width=\"6\" height=\"6\" rx=\"1\" /><rect x=\"2\" y=\"16\" width=\"6\" height=\"6\" rx=\"1\" /><rect x=\"9\" y=\"2\" width=\"6\" height=\"6\" rx=\"1\" /><path d=\"M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3\" /><path d=\"M12 12V8\" />", "octagon-alert": "<path d=\"M12 16h.01\" /><path d=\"M12 8v4\" /><path d=\"M15.312 2a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586l-4.688-4.688A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2z\" />", "pencil": "<path d=\"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z\" /><path d=\"m15 5 4 4\" />", "radar": "<path d=\"M19.07 4.93A10 10 0 0 0 6.99 3.34\" /><path d=\"M4 6h.01\" /><path d=\"M2.29 9.62A10 10 0 1 0 21.31 8.35\" /><path d=\"M16.24 7.76A6 6 0 1 0 8.23 16.67\" /><path d=\"M12 18h.01\" /><path d=\"M17.99 11.66A6 6 0 0 1 15.77 16.67\" /><circle cx=\"12\" cy=\"12\" r=\"2\" /><path d=\"m13.41 10.59 5.66-5.66\" />", "radio-tower": "<path d=\"M4.9 16.1C1 12.2 1 5.8 4.9 1.9\" /><path d=\"M7.8 4.7a6.14 6.14 0 0 0-.8 7.5\" /><circle cx=\"12\" cy=\"9\" r=\"2\" /><path d=\"M16.2 4.8c2 2 2.26 5.11.8 7.47\" /><path d=\"M19.1 1.9a9.96 9.96 0 0 1 0 14.1\" /><path d=\"M9.5 18h5\" /><path d=\"m8 22 4-11 4 11\" />", "radio": "<path d=\"M16.247 7.761a6 6 0 0 1 0 8.478\" /><path d=\"M19.075 4.933a10 10 0 0 1 0 14.134\" /><path d=\"M4.925 19.067a10 10 0 0 1 0-14.134\" /><path d=\"M7.753 16.239a6 6 0 0 1 0-8.478\" /><circle cx=\"12\" cy=\"12\" r=\"2\" />", "satellite-dish": "<path d=\"M4 10a7.31 7.31 0 0 0 10 10Z\" /><path d=\"m9 15 3-3\" /><path d=\"M17 13a6 6 0 0 0-6-6\" /><path d=\"M21 13A10 10 0 0 0 11 3\" />", "scan-line": "<path d=\"M3 7V5a2 2 0 0 1 2-2h2\" /><path d=\"M17 3h2a2 2 0 0 1 2 2v2\" /><path d=\"M21 17v2a2 2 0 0 1-2 2h-2\" /><path d=\"M7 21H5a2 2 0 0 1-2-2v-2\" /><path d=\"M7 12h10\" />", "server": "<rect width=\"20\" height=\"8\" x=\"2\" y=\"2\" rx=\"2\" ry=\"2\" /><rect width=\"20\" height=\"8\" x=\"2\" y=\"14\" rx=\"2\" ry=\"2\" /><line x1=\"6\" x2=\"6.01\" y1=\"6\" y2=\"6\" /><line x1=\"6\" x2=\"6.01\" y1=\"18\" y2=\"18\" />", "shield-alert": "<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\" /><path d=\"M12 8v4\" /><path d=\"M12 16h.01\" />", "shield-check": "<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\" /><path d=\"m9 12 2 2 4-4\" />", "shield": "<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\" />", "signal": "<path d=\"M2 20h.01\" /><path d=\"M7 20v-4\" /><path d=\"M12 20v-8\" /><path d=\"M17 20V8\" /><path d=\"M22 4v16\" />", "siren": "<path d=\"M7 18v-6a5 5 0 1 1 10 0v6\" /><path d=\"M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z\" /><path d=\"M21 12h1\" /><path d=\"M18.5 4.5 18 5\" /><path d=\"M2 12h1\" /><path d=\"M12 2v1\" /><path d=\"m4.929 4.929.707.707\" /><path d=\"M12 12v6\" />", "target": "<circle cx=\"12\" cy=\"12\" r=\"10\" /><circle cx=\"12\" cy=\"12\" r=\"6\" /><circle cx=\"12\" cy=\"12\" r=\"2\" />", "terminal": "<path d=\"M12 19h8\" /><path d=\"m4 17 6-6-6-6\" />", "timer": "<line x1=\"10\" x2=\"14\" y1=\"2\" y2=\"2\" /><line x1=\"12\" x2=\"15\" y1=\"14\" y2=\"11\" /><circle cx=\"12\" cy=\"14\" r=\"8\" />", "trophy": "<path d=\"M10 14.66v1.626a2 2 0 0 1-.976 1.696A5 5 0 0 0 7 21.978\" /><path d=\"M14 14.66v1.626a2 2 0 0 0 .976 1.696A5 5 0 0 1 17 21.978\" /><path d=\"M18 9h1.5a1 1 0 0 0 0-5H18\" /><path d=\"M4 22h16\" /><path d=\"M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z\" /><path d=\"M6 9H4.5a1 1 0 0 1 0-5H6\" />", "trash-2": "<path d=\"M10 11v6\" /><path d=\"M14 11v6\" /><path d=\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6\" /><path d=\"M3 6h18\" /><path d=\"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\" />", "unlock": "<rect width=\"18\" height=\"11\" x=\"3\" y=\"11\" rx=\"2\" ry=\"2\" /><path d=\"M7 11V7a5 5 0 0 1 9.9-1\" />", "users": "<path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" /><path d=\"M16 3.128a4 4 0 0 1 0 7.744\" /><path d=\"M22 21v-2a4 4 0 0 0-3-3.87\" /><circle cx=\"9\" cy=\"7\" r=\"4\" />", "wifi": "<path d=\"M12 20h.01\" /><path d=\"M2 8.82a15 15 0 0 1 20 0\" /><path d=\"M5 12.859a10 10 0 0 1 14 0\" /><path d=\"M8.5 16.429a5 5 0 0 1 7 0\" />", "x": "<path d=\"M18 6 6 18\" /><path d=\"m6 6 12 12\" />", "zap": "<path d=\"M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z\" />"};

function icon(name, size = 16, cls = "") {
  const body = ICON_PATHS[name] || "";
  const classes = ("icon " + cls).trim();
  return '<svg class="' + classes + '" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + body + '</svg>';
}

const PAGE = document.body.dataset.page;

// Low-latency nudge layered on top of every page's own poll loop below, never a replacement for
// it: a socket event just triggers that page's existing refresh() immediately instead of waiting
// up to 2s for the next tick. If the socket never connects or drops mid-session, the poll loop
// keeps everything eventually-consistent regardless.
const socket = ["mod", "leaderboard"].includes(PAGE) ? io() : null;

// Tracks consecutive fetch()-level failures (server unreachable, dropped connection, a Railway
// restart) across every page's poll loop, independent of any one page's own state — api() below
// shows/hides a shared "reconnecting" banner on top of every existing poll loop, instead of
// leaving the player looking at a silently-frozen screen with no explanation.
let consecutiveNetworkFailures = 0;

// Shared by every fetch()-based api() helper on the site (this file's own api() below, plus
// mod_admin.js's and agent.js's) -- Flask-WTF's CSRFProtect (app/extensions.py) checks this
// header on every POST/PUT/PATCH/DELETE, since none of those requests are real <form> submits.
function csrfHeader() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? { "X-CSRFToken": meta.content } : {};
}

async function api(url, options = {}) {
  let res;
  try {
    res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      ...options,
    });
  } catch (err) {
    // The request never reached the server at all — network down, server mid-restart, etc.
    // Reported the same shape as a real HTTP response so every existing caller's `!res.ok`
    // handling already does the right thing, with status 0 as the "never got a response" tell.
    // Only (re)renders the banner on the transition into "down" (count going 0 -> 1), not on
    // every single failed poll — it's already showing, no need to touch the DOM again each tick.
    consecutiveNetworkFailures += 1;
    if (consecutiveNetworkFailures === 1) renderConnectionBanner();
    return { ok: false, status: 0, data: {}, networkError: true };
  }
  const wasDown = consecutiveNetworkFailures > 0;
  consecutiveNetworkFailures = 0;
  if (wasDown) renderConnectionBanner();
  let data = {};
  try {
    data = await res.json();
  } catch (err) {
    data = {};
  }
  // A dead/expired team session (deleted team, or the cookie simply outlived the event) — mod
  // and agent pages already get an HTML redirect for free from Flask-Login's own handling. The
  // player dashboard is a standalone React app on Vercel now (frontend/src/api.ts has its own
  // copy of this same redirect); only the leaderboard's poll loop still needs it here.
  if (res.status === 401 && PAGE === "leaderboard") {
    window.location.href = "/auth/team-login";
  }
  return { ok: res.ok, status: res.status, data };
}

// One shared banner, injected once per page if the page has a spot for it — every page's poll
// loop calls this after each api() call so a dropped connection is always visibly explained,
// never just a UI that silently stops updating.
function renderConnectionBanner() {
  let el = document.getElementById("connection-banner");
  if (!el) {
    el = document.createElement("div");
    el.id = "connection-banner";
    el.className = "connection-banner hidden";
    document.body.insertBefore(el, document.body.firstChild);
  }
  if (consecutiveNetworkFailures > 0) {
    el.classList.remove("hidden");
    el.innerHTML = `${icon("wifi", 14)} Connection lost — attempting to reconnect&hellip;`;
  } else {
    el.classList.add("hidden");
  }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

// Disables `btn` and (optionally) swaps its label for the duration of `fn`, always restoring
// both in a finally block — the one loading-button pattern already established in this codebase
// (originally just the challenge-submit button), generalized so other fetch-triggered buttons
// can reuse it instead of each hand-rolling the same disable/restore dance.
async function withLoadingButton(btn, loadingLabel, fn) {
  const original = btn.innerHTML;
  btn.disabled = true;
  if (loadingLabel) btn.innerHTML = loadingLabel;
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

function fmtClock(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

// Once a mission has a frozen submission (grading_status set, either "pending_review" while a
// Booth Agent hasn't looked at it yet or "graded" once a synchronous auto/cipher result already
// landed), the timer must show that frozen instant forever — never fall back to live
// Date.now() math, or a slow review/grading pass would silently inflate the team's recorded
// time exactly like the bug this replaced. Only compute a live countdown when nothing has been
// submitted yet.
function computeTimerDisplay(mission) {
  if (!mission) return { value: "—", tier: "ok", pct: 100, frozen: false, label: "Timer" };

  // submission_status/time_remaining_frozen/elapsed_seconds are frozen together, regardless of
  // grading_status — a manual-review submission awaiting a Booth Agent is just as much "on time"
  // or "overtime" as an already-graded one, so that computation must not depend on which state
  // grading is in. grading_status only ever picks the *label* on top of it.
  if (mission.submission_status) {
    const overtime = mission.submission_status === "overtime";
    const value = mission.time_limit
      ? overtime
        ? `+${fmtClock(-mission.time_remaining_frozen)} OVER`
        : fmtClock(mission.time_remaining_frozen)
      : fmtClock(mission.elapsed_seconds);
    const label = mission.grading_status === "pending_review" ? "Awaiting Review" : "Submitted";
    return { value: `Submitted — ${value}`, tier: overtime ? "crit" : "ok", pct: overtime ? 0 : 100, frozen: true, label };
  }

  if (!mission.time_limit || !mission.started_at) {
    return { value: "—", tier: "ok", pct: 100, frozen: false, label: "Timer" };
  }
  const startedAt = new Date(mission.started_at + "Z").getTime();
  const remaining = mission.time_limit - (Date.now() - startedAt) / 1000;
  const pct = Math.max(0, Math.min(100, (remaining / mission.time_limit) * 100));
  const tier = pct < 15 ? "crit" : pct < 50 ? "warn" : "ok";
  const value = remaining > 0 ? fmtClock(remaining) : "OVERDUE";
  return { value, tier, pct, frozen: false, label: "Timer" };
}

/* ---------------------------------------------------------------- */
/* Data-grid utility — click-to-sort headers + optional live search  */
/* Applied to every .data-table on the site, JS-rendered or static.  */
/* ---------------------------------------------------------------- */

function enhanceDataTable(table) {
  if (!table || table.dataset.gridEnhanced) return;
  table.dataset.gridEnhanced = "1";

  if (!table.parentElement.classList.contains("data-grid-wrap")) {
    const wrap = document.createElement("div");
    wrap.className = "data-grid-wrap";
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
  }

  const ths = Array.from(table.querySelectorAll("thead th"));
  ths.forEach((th, idx) => {
    th.addEventListener("click", () => {
      const tbody = table.querySelector("tbody");
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const wasAsc = th.classList.contains("sorted-asc");
      ths.forEach((h) => h.classList.remove("sorted-asc", "sorted-desc"));
      const asc = !wasAsc;
      th.classList.add(asc ? "sorted-asc" : "sorted-desc");
      rows.sort((a, b) => {
        const av = a.children[idx] ? a.children[idx].textContent.trim() : "";
        const bv = b.children[idx] ? b.children[idx].textContent.trim() : "";
        const an = parseFloat(av.replace(/[^0-9.\-]/g, ""));
        const bn = parseFloat(bv.replace(/[^0-9.\-]/g, ""));
        const bothNumeric = av !== "" && bv !== "" && !isNaN(an) && !isNaN(bn);
        const cmp = bothNumeric ? an - bn : av.localeCompare(bv);
        return asc ? cmp : -cmp;
      });
      rows.forEach((r) => tbody.appendChild(r));
    });
  });
}

function enhanceAllDataTables(root = document) {
  root.querySelectorAll("table.data-table").forEach(enhanceDataTable);
}

// containerEl must be a stable element that outlives table re-renders (the
// <table> itself gets replaced on every poll, so we re-query it live instead
// of closing over a specific node — and guard so refresh() can call this
// every cycle without stacking duplicate "input" listeners on the search box).
function attachGridSearch(input, containerEl) {
  if (!input || !containerEl || input.dataset.gridSearchAttached) return;
  input.dataset.gridSearchAttached = "1";
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    const table = containerEl.querySelector("table.data-table") || containerEl;
    table.querySelectorAll("tbody tr").forEach((row) => {
      row.style.display = !q || row.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  enhanceAllDataTables();
  document.querySelectorAll("[data-grid-search-for]").forEach((input) => {
    const container = document.getElementById(input.dataset.gridSearchFor);
    attachGridSearch(input, container);
  });
});

/* ---------------------------------------------------------------- */
/* Game Master dashboard                                              */
/* ---------------------------------------------------------------- */

(function modPage() {
  if (PAGE !== "mod") return;

  async function refresh() {
    const res = await api("/mod/data");
    const data = res.data;
    if (!data.teams) return;

    const statusPill = document.getElementById("event-status-pill");
    if (statusPill) {
      const dotTier = data.event_status === "running" ? "" : data.event_status === "paused" ? "warn" : "off";
      statusPill.innerHTML = `<span class="status-dot ${dotTier}"></span> ${escapeHtml(data.event_status)}`;
    }

    const el = document.getElementById("team-table");
    el.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th>${icon("users", 12)} Team</th><th>${icon("gauge", 12)} Score</th><th>${icon(
      "signal",
      12
    )} Integrity</th><th>${icon("target", 12)} Current mission</th>
              <th>${icon("file-lock-2", 12)} Fragments</th><th>${icon("shield-check", 12)} Clearance</th><th>${icon(
      "activity",
      12
    )} Status</th><th></th></tr>
        </thead>
        <tbody>
          ${data.teams
            .map(
              (t) => `
            <tr>
              <td>${escapeHtml(t.name)}</td>
              <td>${t.score}</td>
              <td>${t.integrity}%</td>
              <td>${escapeHtml(t.current_mission)}</td>
              <td>${t.fragments}/${data.total_missions || 0}</td>
              <td>${t.clearance}</td>
              <td><span class="badge badge-${t.status}">${t.status}</span>${
                t.soft_locked_missions && t.soft_locked_missions.length
                  ? ` <span class="badge badge-soft_locked" title="Soft-locked: ${escapeHtml(
                      t.soft_locked_missions.join(", ")
                    )}">${icon("shield-alert", 11)} ${t.soft_locked_missions.length} Soft Lock${
                      t.soft_locked_missions.length > 1 ? "s" : ""
                    }</span>`
                  : ""
              }</td>
              <td><a class="ghost-link" href="/mod/team/${t.id}">${icon("eye", 12)} Detail</a></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;

    const table = el.querySelector("table.data-table");
    enhanceDataTable(table);
    attachGridSearch(document.getElementById("team-search"), el);
  }

  if (socket) {
    socket.on("mod_update", refresh);
    socket.on("event_update", refresh);
  }

  refresh();
  setInterval(refresh, 2000);
})();

/* ---------------------------------------------------------------- */
/* Public leaderboard                                                 */
/* ---------------------------------------------------------------- */

(function leaderboardPage() {
  if (PAGE !== "leaderboard") return;

  async function refresh() {
    const res = await api("/leaderboard/data");
    const el = document.getElementById("leaderboard-table");
    if (res.data.hidden) {
      el.innerHTML = `<p class="hint-text">${icon("lock-keyhole", 13)} The leaderboard is hidden for this event.</p>`;
      return;
    }
    const rows = res.data.leaderboard || [];
    const totalMissions = res.data.total_missions || 0;
    el.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th>${icon("crosshair", 12)} #</th><th>${icon("users", 12)} Team</th><th>${icon(
      "gauge",
      12
    )} Score</th><th>${icon("signal", 12)} Integrity</th><th>${icon("target", 12)} Current mission</th>
              <th>${icon("file-lock-2", 12)} Fragments</th><th>${icon("shield-check", 12)} Clearance</th><th>${icon(
      "activity",
      12
    )} Status</th></tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (r) => `
            <tr>
              <td>${r.rank <= 3 ? icon("trophy", 13, "rank-trophy") : ""} ${r.rank}</td>
              <td>${escapeHtml(r.team)}</td>
              <td>${r.score}</td>
              <td>${r.integrity}%</td>
              <td>${escapeHtml(r.current_mission)}</td>
              <td>${r.fragments}/${totalMissions}</td>
              <td>${r.clearance}</td>
              <td><span class="badge badge-${r.status}">${r.status}</span>${
                r.soft_locked_count
                  ? ` <span class="badge badge-soft_locked" title="${r.soft_locked_count} booth(s) soft-locked">${icon(
                      "shield-alert",
                      11
                    )} ${r.soft_locked_count} Soft Lock${r.soft_locked_count > 1 ? "s" : ""}</span>`
                  : ""
              }</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;

    const table = el.querySelector("table.data-table");
    enhanceDataTable(table);
    attachGridSearch(document.getElementById("leaderboard-search"), el);
  }

  if (socket) {
    socket.on("event_update", refresh);
  }

  refresh();
  setInterval(refresh, 2000);
})();
