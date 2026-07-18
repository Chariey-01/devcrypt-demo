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
const socket = ["player", "mod", "leaderboard"].includes(PAGE) ? io() : null;

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = {};
  try {
    data = await res.json();
  } catch (err) {
    data = {};
  }
  return { ok: res.ok, status: res.status, data };
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
/* Player portal                                                     */
/* ---------------------------------------------------------------- */

(function playerPage() {
  if (PAGE !== "player") return;

  let activeTab = 0;
  let currentMissionId = null;
  let message = null;
  let draftAnswer = "";
  let testResults = null; // last "Run Visible Tests" result, cleared when the mission changes
  // Tracks the challenge prompt actually on screen, so refresh() can tell a genuine Agent
  // edit apart from "nothing changed" while the player is mid-type in the answer field
  // (renderMissionPanel is skipped in that case to avoid stealing focus/cursor position —
  // see refresh() below — but the player still needs to know an update is waiting).
  let lastShownPrompt = null;

  function showMessage(text) {
    message = text || null;
    clearTimeout(showMessage._t);
    showMessage._t = setTimeout(() => {
      message = null;
    }, 4000);
  }

  function renderCryptogram(board) {
    const el = document.getElementById("cryptogram-board");
    el.innerHTML = "";
    board.forEach((word) => {
      const wrap = document.createElement("div");
      wrap.className = "cipher-word" + (word.complete ? " complete" : "");

      const letters = document.createElement("div");
      letters.className = "cipher-letters";
      [...word.display].forEach((ch, i) => {
        const tile = document.createElement("span");
        tile.className = "tile" + (word.revealed[i] ? " revealed" : "");
        tile.textContent = ch;
        letters.appendChild(tile);
      });

      const title = document.createElement("div");
      title.className = "cipher-word-title";
      title.textContent = word.title;

      wrap.appendChild(letters);
      wrap.appendChild(title);
      el.appendChild(wrap);
    });
  }

  function renderFragments(fragments) {
    const el = document.getElementById("fragment-rail");
    if (!fragments || !fragments.length) {
      el.innerHTML = `<span class="hint-text">${icon("file-lock-2", 13)} No fragments recovered yet.</span>`;
      return;
    }
    el.innerHTML = fragments
      .map((f) => `<span class="fragment-chip">${icon("hash", 12)} ${escapeHtml(f.value)}</span>`)
      .join("");
  }

  function renderBanners(data) {
    const eventBanner = document.getElementById("event-banner");
    if (data.event_status !== "running") {
      eventBanner.classList.remove("hidden");
      eventBanner.innerHTML =
        data.event_status === "not_started" || data.event_status === "draft"
          ? `${icon("radar", 14)} STANDING BY — waiting for the Game Master to start the event.`
          : data.event_status === "paused"
          ? `${icon("octagon-alert", 14)} EVENT PAUSED by the Game Master.`
          : `${icon("shield-check", 14)} EVENT ENDED — final scores are locked.`;
    } else {
      eventBanner.classList.add("hidden");
    }

    const broadcastEl = document.getElementById("broadcast-banner");
    if (data.broadcast) {
      broadcastEl.classList.remove("hidden");
      broadcastEl.innerHTML = `${icon("radio-tower", 14)} ${escapeHtml(data.broadcast.message)}`;
    } else {
      broadcastEl.classList.add("hidden");
    }
  }

  function attachMcqHandlers(panel) {
    panel.querySelectorAll(".mcq-option").forEach((btn) => {
      btn.addEventListener("click", async () => {
        panel.querySelectorAll(".mcq-option").forEach((b) => (b.disabled = true));
        const res = await api(`/missions/mcq/${btn.dataset.mcq}/answer`, {
          method: "POST",
          body: JSON.stringify({ option_id: parseInt(btn.dataset.option, 10) }),
        });
        showMessage(res.data.message || res.data.error);
        await refresh();
      });
    });
  }

  function attachChallengeHandlers(panel) {
    panel.querySelectorAll(".challenge-option").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const res = await api("/missions/challenge/submit", {
          method: "POST",
          body: JSON.stringify({ answer: btn.dataset.answer }),
        });
        showMessage(res.data.message || res.data.error);
        await refresh();
      });
    });

    const answerEl = panel.querySelector("#challenge-answer, #code-editor");
    if (answerEl) {
      answerEl.addEventListener("input", () => {
        draftAnswer = answerEl.value;
      });
    }

    const runTestsBtn = panel.querySelector("#run-tests");
    if (runTestsBtn) {
      runTestsBtn.addEventListener("click", () =>
        withLoadingButton(runTestsBtn, "Testing&hellip;", async () => {
          const code = panel.querySelector("#code-editor").value;
          const res = await api("/missions/challenge/run-tests", {
            method: "POST",
            body: JSON.stringify({ code }),
          });
          if (res.ok) {
            testResults = res.data;
            const resultsEl = panel.querySelector("#test-results");
            if (resultsEl) resultsEl.innerHTML = renderTestResults(testResults);
          } else {
            showMessage(res.data.error);
          }
        })
      );
    }

    const submitBtn = panel.querySelector("#submit-challenge");
    if (submitBtn) {
      submitBtn.addEventListener("click", () =>
        // Grading runs server-side and can legitimately take several seconds under peak event
        // load (many teams submitting at once all contend for the same sandboxed-subprocess
        // CPU budget) — disable + relabel so a slow grading run reads as "working," not "did
        // my click register?", and so a player can't fire a second submission (and burn an
        // extra attempt against max_attempts) while the first is still in flight.
        withLoadingButton(submitBtn, "Grading&hellip;", async () => {
          const value = panel.querySelector("#challenge-answer, #code-editor").value;
          const res = await api("/missions/challenge/submit", {
            method: "POST",
            body: JSON.stringify({ answer: value, code: value }),
          });
          draftAnswer = "";
          testResults = null;
          const detail =
            res.data.percent_score !== undefined
              ? ` (${res.data.passed_tests}/${res.data.total_tests} tests, ${res.data.percent_score}%)`
              : "";
          showMessage((res.data.message || res.data.error) + detail);
          await refresh();
        })
      );
    }

    const hintBtn = panel.querySelector("#request-hint");
    if (hintBtn) {
      hintBtn.addEventListener("click", async () => {
        const hintLimit = data.team.hints_used + data.team.hints_remaining;
        if (
          !confirm(
            `Request a hint? Costs 15 points and 10% integrity, and uses one of your team's ${hintLimit} event-wide hints.`
          )
        )
          return;
        const res = await api("/missions/hint", { method: "POST" });
        showMessage(res.data.hint ? `HINT: ${res.data.hint}` : res.data.error);
        await refresh();
      });
    }
  }

  function renderTestResults(results) {
    if (!results) return "";
    const rows = results.results
      .map((r) => {
        const passIcon = icon(r.passed ? "check" : "x", 13);
        let detail = "";
        if (r.visibility === "visible") {
          detail = `<p class="hint-text mono">input: ${escapeHtml(r.input_data ?? "")} — expected: ${escapeHtml(
            r.expected_output ?? ""
          )} — got: ${escapeHtml(r.actual_output ?? "")}</p>`;
        }
        return `<div class="ops-panel">
          <p class="ops-value ${r.passed ? "ok" : "crit"}">${passIcon} ${escapeHtml(r.name)}</p>
          ${!r.passed && r.failure_message ? `<p class="hint-text">${escapeHtml(r.failure_message)}</p>` : ""}
          ${detail}
        </div>`;
      })
      .join("");
    return `
      <p class="hint-text">${icon("gauge", 12)} ${results.passed_tests} / ${results.total_tests} passed</p>
      <div class="ops-grid">${rows}</div>`;
  }

  function missionThreat(mission) {
    if (mission.penalty_remaining) return { label: "ELEVATED", tier: "warn" };
    if (mission.attempts > 1) return { label: "ELEVATED", tier: "warn" };
    if (mission.mcqs_complete) return { label: "CONTAINED", tier: "ok" };
    return { label: "ACTIVE", tier: "info" };
  }

  function missionStage(mission) {
    if (mission.pending_review) return { label: "AWAITING REVIEW", tier: "warn" };
    if (mission.penalty_remaining) return { label: "ON COOLDOWN", tier: "warn" };
    if (!mission.mcqs_complete) return { label: "THREAT ASSESSMENT", tier: "info" };
    return { label: "MISSION ACTION", tier: "info" };
  }

  function renderMissionPanel(data) {
    const panel = document.getElementById("mission-panel");
    const finishedPanel = document.getElementById("finished-panel");

    if (data.finished) {
      panel.classList.add("hidden");
      finishedPanel.classList.remove("hidden");
      finishedPanel.innerHTML = `
        <div class="card">
          <p class="meta-tag ok">${icon("shield-check", 12)} Core Restored</p>
          <h2>${icon("unlock", 22)} METAVERSE CORE RESTORED</h2>
          <div class="ops-grid" style="margin-top:0.75rem;">
            <div class="ops-panel">
              <p class="ops-label">${icon("gauge", 14)} Final Score</p>
              <p class="ops-value ok">${data.team.score}</p>
            </div>
            <div class="ops-panel">
              <p class="ops-label">${icon("signal", 14)} Integrity</p>
              <p class="ops-value info">${data.team.integrity}%</p>
            </div>
          </div>
        </div>`;
      return;
    }
    finishedPanel.classList.add("hidden");
    panel.classList.remove("hidden");

    const mission = data.mission;
    if (mission.id !== currentMissionId) {
      currentMissionId = mission.id;
      activeTab = 0;
      draftAnswer = "";
      testResults = null;
    }

    const nodesSecured = (data.cryptogram || []).filter((w) => w.complete).length;
    const nodesTotal = (data.cryptogram || []).length;
    const threat = missionThreat(mission);
    const stage = missionStage(mission);
    const missionCode = `NODE-${String(mission.id).padStart(2, "0")}`;

    let timerValue = "—";
    let timerPct = 100;
    let timerTier = "ok";
    if (mission.time_limit && mission.started_at) {
      const startedAt = new Date(mission.started_at + "Z").getTime();
      const remaining = mission.time_limit - (Date.now() - startedAt) / 1000;
      timerPct = Math.max(0, Math.min(100, (remaining / mission.time_limit) * 100));
      timerTier = timerPct < 15 ? "red" : timerPct < 50 ? "amber" : "";
      timerValue = remaining > 0 ? fmtClock(remaining) : "OVERDUE";
    }
    const timerValueTier = timerTier === "red" ? "crit" : timerTier === "amber" ? "warn" : "ok";

    const opsGridHtml = `
      <div class="ops-grid">
        <div class="ops-panel">
          <p class="ops-label">${icon("crosshair", 14)} Threat Level</p>
          <p class="ops-value ${threat.tier}">${threat.label}</p>
        </div>
        <div class="ops-panel">
          <p class="ops-label">${icon("activity", 14)} Stage</p>
          <p class="ops-value ${stage.tier}">${stage.label}</p>
        </div>
        <div class="ops-panel">
          <p class="ops-label">${icon("network", 14)} Progress</p>
          <p class="ops-value info">${nodesSecured} / ${nodesTotal}</p>
        </div>
        <div class="ops-panel">
          <p class="ops-label">${icon("timer", 14)} Timer</p>
          <p class="ops-value ${timerValueTier}">${timerValue}</p>
          ${
            mission.time_limit && mission.started_at
              ? `<div class="timer-bar"><div class="timer-fill ${timerTier}" style="width:${timerPct}%"></div></div>`
              : ""
          }
        </div>
      </div>`;

    const tabsHtml = mission.evidence_files
      .map(
        (e, i) =>
          `<button class="tab ${i === activeTab ? "active" : ""}" role="tab" aria-selected="${i === activeTab}" data-tab="${i}">${icon(
            "file-lock-2",
            12
          )} ${escapeHtml(e.label)}</button>`
      )
      .join("");
    const evidenceContent = mission.evidence_files[activeTab]
      ? escapeHtml(mission.evidence_files[activeTab].content)
      : "";

    let mcqHtml = `<p class="section-heading">${icon("shield-alert", 14)} Threat Assessment</p>`;
    if (!mission.mcqs_complete) {
      const nextMcq = mission.mcqs.find((m) => !m.answered);
      if (nextMcq) {
        mcqHtml += `
          <p>${escapeHtml(nextMcq.question_text)}</p>
          ${nextMcq.options
            .map(
              (o) =>
                `<button class="mcq-option" data-mcq="${nextMcq.id}" data-option="${o.id}">${escapeHtml(
                  o.option_text
                )}</button>`
            )
            .join("")}`;
      }
    } else {
      const correctCount = mission.mcqs.filter((m) => m.was_correct).length;
      mcqHtml += `<p class="hint-text">${icon("check", 13)} Complete — ${correctCount} / ${
        mission.mcqs.length
      } correct.</p>`;
    }

    let challengeHtml = "";
    lastShownPrompt = mission.challenge ? mission.challenge.prompt : null;
    if (mission.mcqs_complete && mission.challenge) {
      const c = mission.challenge;
      challengeHtml = `<p class="section-heading">${icon("terminal", 14)} Mission Action — Submission Panel</p>`;
      if (mission.pending_review) {
        challengeHtml += `<p class="narrative-message">${icon("eye", 13)} SUBMISSION ROUTED TO FIELD AGENT FOR REVIEW.</p>`;
      } else {
        challengeHtml += `<p>${escapeHtml(c.prompt)}</p>`;
        if (c.grading_mode === "auto") {
          if (c.function_signature) {
            challengeHtml += `<p class="hint-text mono">${icon("terminal", 12)} ${escapeHtml(c.function_signature)}</p>`;
          }
          const codeValue = draftAnswer || c.starter_code || "";
          const attemptsNote =
            c.max_attempts != null
              ? `<p class="hint-text">${icon("activity", 12)} Attempts used: ${c.attempts_used} / ${c.max_attempts}</p>`
              : "";
          challengeHtml += `
            <textarea id="code-editor" class="mono" rows="10" spellcheck="false">${escapeHtml(codeValue)}</textarea>
            ${attemptsNote}
            <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
              <button id="run-tests" class="ghost" type="button">${icon("scan-line", 13)} Run Visible Tests</button>
              <button id="submit-challenge">${icon("unlock", 13)} Submit Solution</button>
            </div>
            <div id="test-results">${renderTestResults(testResults)}</div>`;
        } else if (c.type === "mcq" && c.options) {
          challengeHtml += c.options
            .map((opt) => `<button class="challenge-option" data-answer="${escapeHtml(opt)}">${escapeHtml(opt)}</button>`)
            .join("");
        } else {
          challengeHtml += `
            <textarea id="challenge-answer" rows="4" placeholder="${
              c.type === "flag" ? "FLAG{...}" : "Type your fix here…"
            }">${escapeHtml(draftAnswer)}</textarea>
            <button id="submit-challenge">${icon("unlock", 13)} Decrypt &amp; Submit</button>`;
        }
        if (mission.penalty_remaining) {
          challengeHtml += `<p class="narrative-message">${icon("timer", 13)} NODE ON COOLDOWN — ${
            mission.penalty_remaining
          }s remaining.</p>`;
        }
        if (c.hint_text) {
          challengeHtml += `<p class="narrative-message">${icon("key", 13)} HINT: ${escapeHtml(c.hint_text)}</p>`;
        } else {
          challengeHtml += `<button id="request-hint" class="ghost">${icon("key", 13)} Request Hint (${
            data.team.hints_remaining
          } left)</button>`;
        }
      }
    }

    const objective = !mission.mcqs_complete
      ? "Answer the threat assessment questions."
      : mission.pending_review
      ? "Await field agent review."
      : "Complete the mission action to secure this node.";

    const timelineHtml = (data.timeline || [])
      .map(
        (t, i, arr) => `
      <div class="mission-timeline-node ${t.status}">
        <span class="status-dot ${t.status === "current" ? "" : "off"}"></span>
        <span class="mission-timeline-label">${escapeHtml(t.title)}</span>
      </div>
      ${i < arr.length - 1 ? '<div class="mission-timeline-connector"></div>' : ""}`
      )
      .join("");

    panel.innerHTML = `
      <div class="mission-header">
        <div>
          <p class="mission-id">${icon("hash", 12)} MISSION ${missionCode}</p>
          <h2>${escapeHtml(mission.title)}</h2>
        </div>
        <span class="meta-tag">${icon("unlock", 12)} ACTIVE</span>
      </div>
      <div class="mission-timeline">${timelineHtml}</div>
      <p>${escapeHtml(mission.narrative)}</p>
      ${opsGridHtml}
      <div class="tabs" role="tablist">${tabsHtml}</div>
      <div class="evidence-content">${evidenceContent}</div>
      <div id="mcq-stage">${mcqHtml}</div>
      <div id="challenge-stage">${challengeHtml}</div>
      ${
        message && !mission.pending_review && !mission.penalty_remaining
          ? `<p class="narrative-message">${escapeHtml(message)}</p>`
          : ""
      }
      <p class="objective">${icon("target", 12)} Current objective: ${objective}</p>
    `;

    panel.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = parseInt(btn.dataset.tab, 10);
        renderMissionPanel(data);
      });
    });

    attachMcqHandlers(panel);
    attachChallengeHandlers(panel);
  }

  async function refresh() {
    const res = await api("/missions/status");
    if (!res.data || !res.data.team) {
      window.location.href = "/auth/team-login";
      return;
    }
    const data = res.data;
    document.getElementById("team-name").innerHTML = `${icon("users", 13)} ${escapeHtml(data.team.name)}`;
    document.getElementById("team-score").innerHTML = `${icon("gauge", 13)} Score ${data.team.score}`;
    document.getElementById("team-integrity").innerHTML = `${icon("signal", 13)} Integrity ${data.team.integrity}%`;
    document.getElementById("team-hints").innerHTML = `${icon("key", 13)} Hints ${data.team.hints_remaining}/3`;
    renderBanners(data);
    renderCryptogram(data.cryptogram);
    renderFragments(data.fragments);
    // Skip the mission panel rebuild while the player is actively typing a submission —
    // rebuilding replaces #challenge-answer/#code-editor's DOM node every poll, which would
    // steal focus/cursor position out from under them (the typed *value* itself already
    // survives via draftAnswer above, this is purely about not yanking focus mid-keystroke).
    const promptBanner = document.getElementById("prompt-updated-banner");
    const activeId = document.activeElement && document.activeElement.id;
    if (activeId === "challenge-answer" || activeId === "code-editor") {
      const newPrompt = data.mission && data.mission.challenge ? data.mission.challenge.prompt : null;
      if (newPrompt !== null && newPrompt !== lastShownPrompt) {
        promptBanner.classList.remove("hidden");
        promptBanner.innerHTML = `${icon("radio-tower", 13)} This challenge was just updated by an Agent. <a href="#" id="prompt-updated-refresh">Click to load the new version</a> (your current draft is kept either way).`;
        document.getElementById("prompt-updated-refresh").addEventListener("click", (e) => {
          e.preventDefault();
          renderMissionPanel(data);
        });
      }
      return;
    }
    promptBanner.classList.add("hidden");
    renderMissionPanel(data);
  }

  if (socket) {
    socket.on("team_update", refresh);
    socket.on("event_update", refresh);
  }

  refresh();
  setInterval(refresh, 2000);
})();

/* ---------------------------------------------------------------- */
/* Submission alerts — live notification bar for booth + security     */
/* Fires only for submissions that appear *after* the first poll, so  */
/* the bar doesn't flood with everything already pending on load.     */
/* ---------------------------------------------------------------- */

(function submissionAlerts() {
  if (PAGE !== "booth" && PAGE !== "security") return;

  const bar = document.getElementById("alert-bar");
  if (!bar) return;

  let seen = null;

  function pushAlert(item) {
    const toast = document.createElement("div");
    toast.className = "alert-toast";
    toast.innerHTML = `${icon("radio", 14)} <strong>${escapeHtml(
      item.team
    )}</strong> submitted a solution — ${escapeHtml(item.mission)}`;
    bar.prepend(toast);
    while (bar.children.length > 4) bar.removeChild(bar.lastChild);
    setTimeout(() => toast.remove(), 10000);
  }

  async function refresh() {
    const res = await api("/booth/alerts/data");
    if (!res.ok) return;
    const alerts = res.data.alerts || [];
    const ids = new Set(alerts.map((a) => a.id));

    if (seen) {
      alerts
        .filter((a) => !seen.has(a.id))
        .reverse()
        .forEach(pushAlert);
    }
    seen = ids;
  }

  refresh();
  setInterval(refresh, 2000);
})();

/* ---------------------------------------------------------------- */
/* Booth agent portal                                                 */
/* ---------------------------------------------------------------- */

(function boothPage() {
  if (PAGE !== "booth") return;

  async function refresh() {
    const res = await api("/booth/queue/data");
    const el = document.getElementById("queue");
    const queue = res.data.queue || [];

    if (queue.length === 0) {
      el.innerHTML = `<p class="hint-text">${icon(
        "radar",
        14
      )} No submissions waiting. Teams appear here once they submit a code challenge.</p>`;
      return;
    }

    el.innerHTML = queue
      .map(
        (item) => `
      <div class="queue-card">
        <div class="queue-card-header">
          <h3>${icon("users", 15)} ${escapeHtml(item.team)}</h3>
          <span class="meta-tag">${icon("crosshair", 12)} Attempt ${item.attempts + 1}</span>
        </div>
        <p class="hint-text">${icon("key", 13)} Hints remaining ${item.hints_remaining}</p>
        <pre>${escapeHtml(item.submission)}</pre>
        <div class="queue-actions">
          <button data-action="pass" data-id="${item.team_mission_id}">${icon("check", 13)} Pass</button>
          <button data-action="retry" data-id="${item.team_mission_id}" class="ghost">${icon("timer", 13)} Retry</button>
          <button data-action="hint" data-id="${item.team_mission_id}" class="ghost">${icon("key", 13)} Hint</button>
          <button data-action="override" data-id="${item.team_mission_id}" class="danger">${icon(
          "siren",
          13
        )} Mission Override</button>
        </div>
      </div>`
      )
      .join("");

    el.querySelectorAll("button[data-action]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const action = btn.dataset.action;
        if (action === "override" && !confirm("Mission Override applies a heavy score/integrity penalty. Continue?")) {
          return;
        }
        const res = await api(`/booth/submission/${btn.dataset.id}/${action}`, { method: "POST" });
        if (res.data.hint) {
          alert(`Read this hint aloud — don't freestyle:\n\n${res.data.hint}`);
        }
        refresh();
      });
    });
  }

  refresh();
  setInterval(refresh, 2000);
})();

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
              <td><span class="badge badge-${t.status}">${t.status}</span></td>
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
              <td><span class="badge badge-${r.status}">${r.status}</span></td>
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
