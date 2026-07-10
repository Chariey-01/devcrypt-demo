const PAGE = document.body.dataset.page;

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

function fmtClock(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

/* ---------------------------------------------------------------- */
/* Player portal                                                     */
/* ---------------------------------------------------------------- */

(function playerPage() {
  if (PAGE !== "player") return;

  let activeTab = 0;
  let currentMissionId = null;
  let message = null;

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
    el.innerHTML = (fragments || [])
      .map((f) => `<span class="fragment-chip">${escapeHtml(f.value)}</span>`)
      .join("");
  }

  function renderBanners(data) {
    const eventBanner = document.getElementById("event-banner");
    if (data.event_status !== "running") {
      eventBanner.classList.remove("hidden");
      eventBanner.textContent =
        data.event_status === "not_started"
          ? "Standing by — waiting for the Game Master to start the event."
          : data.event_status === "paused"
          ? "Event paused by the Game Master."
          : "Event has ended. Final scores are locked.";
    } else {
      eventBanner.classList.add("hidden");
    }

    const broadcastEl = document.getElementById("broadcast-banner");
    if (data.broadcast) {
      broadcastEl.classList.remove("hidden");
      broadcastEl.textContent = `📡 ${data.broadcast.message}`;
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

    const submitBtn = panel.querySelector("#submit-challenge");
    if (submitBtn) {
      submitBtn.addEventListener("click", async () => {
        const answer = panel.querySelector("#challenge-answer").value;
        const res = await api("/missions/challenge/submit", {
          method: "POST",
          body: JSON.stringify({ answer }),
        });
        showMessage(res.data.message || res.data.error);
        await refresh();
      });
    }

    const hintBtn = panel.querySelector("#request-hint");
    if (hintBtn) {
      hintBtn.addEventListener("click", async () => {
        if (
          !confirm(
            "Request a hint? Costs 15 points and 10% integrity, and uses one of your team's 3 event-wide hints."
          )
        )
          return;
        const res = await api("/missions/hint", { method: "POST" });
        showMessage(res.data.hint ? `HINT: ${res.data.hint}` : res.data.error);
        await refresh();
      });
    }
  }

  function renderMissionPanel(data) {
    const panel = document.getElementById("mission-panel");
    const finishedPanel = document.getElementById("finished-panel");

    if (data.finished) {
      panel.classList.add("hidden");
      finishedPanel.classList.remove("hidden");
      finishedPanel.innerHTML = `
        <div class="card">
          <h2>METAVERSE CORE RESTORED</h2>
          <p>All six nodes secured. Final score: <strong>${data.team.score}</strong> ·
             Integrity: <strong>${data.team.integrity}%</strong></p>
        </div>`;
      return;
    }
    finishedPanel.classList.add("hidden");
    panel.classList.remove("hidden");

    const mission = data.mission;
    if (mission.id !== currentMissionId) {
      currentMissionId = mission.id;
      activeTab = 0;
    }

    let timerHtml = "";
    if (mission.time_limit && mission.started_at) {
      const startedAt = new Date(mission.started_at + "Z").getTime();
      const remaining = mission.time_limit - (Date.now() - startedAt) / 1000;
      const pct = Math.max(0, Math.min(100, (remaining / mission.time_limit) * 100));
      const cls = pct < 15 ? "red" : pct < 50 ? "amber" : "";
      timerHtml = `
        <div class="timer-bar"><div class="timer-fill ${cls}" style="width:${pct}%"></div></div>
        <p class="hint-text">Time remaining: ${remaining > 0 ? fmtClock(remaining) : "OVERDUE"}</p>`;
    }

    const tabsHtml = mission.evidence_files
      .map(
        (e, i) =>
          `<button class="tab ${i === activeTab ? "active" : ""}" data-tab="${i}">${escapeHtml(
            e.label
          )}</button>`
      )
      .join("");
    const evidenceContent = mission.evidence_files[activeTab]
      ? escapeHtml(mission.evidence_files[activeTab].content)
      : "";

    let mcqHtml = "<h3>Threat Assessment</h3>";
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
      mcqHtml += `<p class="hint-text">Complete — ${
        mission.mcqs.filter((m) => m.was_correct).length
      } / ${mission.mcqs.length} correct.</p>`;
    }

    let challengeHtml = "";
    if (mission.mcqs_complete && mission.challenge) {
      const c = mission.challenge;
      challengeHtml = "<h3>Mission Action</h3>";
      if (mission.pending_review) {
        challengeHtml += `<p class="narrative-message">SUBMISSION ROUTED TO FIELD AGENT FOR REVIEW.</p>`;
      } else if (mission.locked) {
        challengeHtml += `<p class="narrative-message">COMMAND CENTER LOCKED — TWO SECURITY CLEARANCE STAMPS REQUIRED.</p>`;
      } else {
        challengeHtml += `<p>${escapeHtml(c.prompt)}</p>`;
        if (c.type === "mcq" && c.options) {
          challengeHtml += c.options
            .map((opt) => `<button class="challenge-option" data-answer="${escapeHtml(opt)}">${escapeHtml(opt)}</button>`)
            .join("");
        } else {
          challengeHtml += `
            <textarea id="challenge-answer" rows="4" placeholder="${
              c.type === "flag" ? "FLAG{...}" : "Type your fix here…"
            }"></textarea>
            <button id="submit-challenge">Submit</button>`;
        }
        if (mission.penalty_remaining) {
          challengeHtml += `<p class="narrative-message">NODE ON COOLDOWN — ${mission.penalty_remaining}s remaining.</p>`;
        }
        if (c.hint_text) {
          challengeHtml += `<p class="narrative-message">HINT: ${escapeHtml(c.hint_text)}</p>`;
        } else {
          challengeHtml += `<button id="request-hint" class="ghost">Request hint (${data.team.hints_remaining} left)</button>`;
        }
      }
    }

    const objective = !mission.mcqs_complete
      ? "Answer the threat assessment questions."
      : mission.pending_review
      ? "Await field agent review."
      : mission.locked
      ? "Obtain two security clearance stamps."
      : "Complete the mission action to secure this node.";

    panel.innerHTML = `
      <h2>${escapeHtml(mission.title)}</h2>
      <p>${escapeHtml(mission.narrative)}</p>
      ${timerHtml}
      <div class="tabs">${tabsHtml}</div>
      <div class="evidence-content">${evidenceContent}</div>
      <div id="mcq-stage">${mcqHtml}</div>
      <div id="challenge-stage">${challengeHtml}</div>
      ${message ? `<p class="narrative-message">${escapeHtml(message)}</p>` : ""}
      <p class="objective">Current objective: ${objective}</p>
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
    document.getElementById("team-name").textContent = data.team.name;
    document.getElementById("team-score").textContent = `Score ${data.team.score}`;
    document.getElementById("team-integrity").textContent = `Integrity ${data.team.integrity}%`;
    document.getElementById("team-hints").textContent = `Hints ${data.team.hints_remaining}/3`;
    renderBanners(data);
    renderCryptogram(data.cryptogram);
    renderFragments(data.fragments);
    renderMissionPanel(data);
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
      el.innerHTML = `<p class="hint-text">No submissions waiting. Teams appear here once they submit a code challenge.</p>`;
      return;
    }

    el.innerHTML = queue
      .map(
        (item) => `
      <div class="queue-card">
        <h3>${escapeHtml(item.team)}</h3>
        <p class="hint-text">Attempt ${item.attempts + 1} · Hints remaining ${item.hints_remaining}</p>
        <pre>${escapeHtml(item.submission)}</pre>
        <div class="queue-actions">
          <button data-action="pass" data-id="${item.team_mission_id}">PASS</button>
          <button data-action="retry" data-id="${item.team_mission_id}" class="ghost">RETRY</button>
          <button data-action="hint" data-id="${item.team_mission_id}" class="ghost">HINT</button>
          <button data-action="override" data-id="${item.team_mission_id}" class="danger">OVERRIDE</button>
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
    if (statusPill) statusPill.textContent = data.event_status;

    const el = document.getElementById("team-table");
    el.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th>Team</th><th>Score</th><th>Integrity</th><th>Current mission</th>
              <th>Fragments</th><th>Clearance</th><th>Status</th><th></th></tr>
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
              <td>${t.fragments}/6</td>
              <td>${t.clearance}/2</td>
              <td><span class="badge badge-${t.status}">${t.status}</span></td>
              <td><a class="ghost-link" href="/mod/team/${t.id}">Detail</a></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
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
    const rows = res.data.leaderboard || [];
    const el = document.getElementById("leaderboard-table");
    el.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th>#</th><th>Team</th><th>Score</th><th>Integrity</th><th>Current mission</th>
              <th>Fragments</th><th>Clearance</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (r) => `
            <tr>
              <td>${r.rank}</td>
              <td>${escapeHtml(r.team)}</td>
              <td>${r.score}</td>
              <td>${r.integrity}%</td>
              <td>${escapeHtml(r.current_mission)}</td>
              <td>${r.fragments}/6</td>
              <td>${r.clearance}/2</td>
              <td><span class="badge badge-${r.status}">${r.status}</span></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  refresh();
  setInterval(refresh, 2000);
})();
