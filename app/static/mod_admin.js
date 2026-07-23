/* ---------------------------------------------------------------- */
/* Game Master Dashboard admin panels — teams/credentials, agents,   */
/* live submissions. Separate from app.js's existing modPage() IIFE  */
/* (which owns the live #team-table poll) to keep concerns isolated. */
/* ---------------------------------------------------------------- */

(function modAdminPage() {
  if (typeof PAGE === "undefined" || PAGE !== "mod") return;

  let teams = [];
  let missions = [];
  let agents = [];
  let flashText = null;
  let lastCredential = null;

  async function api(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    if (!res.ok) {
      throw new Error((data && data.error) || `Request failed (${res.status})`);
    }
    return data;
  }

  function flash(text) {
    flashText = text;
    renderTeamAdmin();
    clearTimeout(flash._t);
    flash._t = setTimeout(() => {
      flashText = null;
      renderTeamAdmin();
    }, 4000);
  }

  function renderTeamAdmin() {
    const el = document.getElementById("team-admin");
    if (!el) return;

    const missionOptions = missions
      .map((m) => `<option value="${m.id}">${escapeHtml(m.title)}</option>`)
      .join("");

    const teamRows = teams
      .map((t) => {
        const memberRows = t.members
          .map(
            (m) => `<li>${escapeHtml(m.name)}${m.email ? ` (${escapeHtml(m.email)})` : ""}
            <button type="button" class="danger" data-remove-member="${t.id}:${m.id}">${icon("x", 11)}</button></li>`
          )
          .join("");
        return `
        <div class="card" style="margin-bottom:0.75rem;">
          <div class="queue-card-header">
            <strong>${icon("users", 13)} ${escapeHtml(t.name)}</strong>
            <div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
              <button type="button" class="ghost" data-reset-team="${t.id}">${icon("rotate-ccw", 12)} Reset Progress</button>
              <button type="button" class="danger" data-delete-team="${t.id}">${icon("trash-2", 12)} Delete</button>
            </div>
          </div>
          <form class="inline-form" data-rename-team="${t.id}" style="margin-top:0.4rem;">
            <input type="text" name="name" value="${escapeHtml(t.name)}" required style="width:auto;">
            <button type="submit" class="ghost">${icon("pencil", 12)} Rename</button>
          </form>
          <ul style="margin:0.4rem 0;">${memberRows || `<li class="hint-text">No members added.</li>`}</ul>
          <form class="inline-form" data-add-member="${t.id}">
            <input type="text" name="name" placeholder="Member name" required style="width:auto;">
            <input type="email" name="email" placeholder="Email (optional)" style="width:auto;">
            <button type="submit">${icon("zap", 12)} Add Member</button>
          </form>
          <form class="inline-form" data-set-booth="${t.id}" style="margin-top:0.4rem;">
            <select name="mission_id" style="width:auto;">
              <option value="">Default (first booth)</option>
              ${missions
                .map(
                  (m) =>
                    `<option value="${m.id}" ${t.starting_mission_id === m.id ? "selected" : ""}>${escapeHtml(m.title)}</option>`
                )
                .join("")}
            </select>
            <button type="submit" class="ghost">${icon("crosshair", 12)} Set Starting Booth</button>
          </form>
        </div>`;
      })
      .join("");

    el.innerHTML = `
      ${flashText ? `<div class="flash flash-info" style="margin-bottom:0.75rem;">${escapeHtml(flashText)}</div>` : ""}
      ${
        lastCredential
          ? `<div class="card" style="margin-bottom:0.75rem;">
              <p>${icon("key", 13)} <strong>${escapeHtml(lastCredential.login)}</strong> — secret shown once: <code>${escapeHtml(lastCredential.secret)}</code></p>
              ${lastCredential.qr_data_uri ? `<img src="${lastCredential.qr_data_uri}" alt="QR code" width="140" height="140">` : ""}
            </div>`
          : ""
      }
      <form id="create-team-form" class="auth-form" style="margin-bottom:0.75rem;">
        <input type="text" name="name" placeholder="New team name" required>
        <button type="submit">${icon("zap", 13)} Create Team</button>
      </form>
      <form id="gen-credential-form" class="inline-form" style="margin-bottom:1rem;">
        <select name="kind">
          <option value="team">Team key</option>
          <option value="booth_agent">Booth Agent password</option>
          <option value="security_officer">Security Officer password</option>
          <option value="game_master">Game Master password</option>
        </select>
        <input type="text" name="name" placeholder="Team name or staff email" required style="width:auto;">
        <input type="text" name="full_name" placeholder="Full name (staff only, optional)" style="width:auto;">
        <button type="submit">${icon("key", 13)} Generate + QR</button>
      </form>
      <button type="button" class="danger" id="reset-all-teams-btn" style="margin-bottom:1rem;">${icon("rotate-ccw", 13)} Reset ALL Teams (clears every team's progress + activity log)</button>
      ${teamRows}
    `;

    document.getElementById("create-team-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const submitBtn = e.target.querySelector('button[type="submit"]');
      try {
        await withLoadingButton(submitBtn, "Creating&hellip;", () => api("POST", "/mod/team", { name: fd.get("name") }));
        await loadAll();
        flash("Team created.");
      } catch (err) {
        flash(err.message);
      }
    });

    document.getElementById("gen-credential-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        lastCredential = await api("POST", "/mod/credentials/generate", {
          kind: fd.get("kind"),
          name: fd.get("name"),
          full_name: fd.get("full_name"),
        });
        e.target.reset();
        await loadAll();
      } catch (err) {
        flash(err.message);
      }
    });

    el.querySelectorAll("[data-add-member]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const teamId = form.dataset.addMember;
        const fd = new FormData(form);
        try {
          await api("POST", `/mod/team/${teamId}/member`, { name: fd.get("name"), email: fd.get("email") });
          await loadAll();
          flash("Member added.");
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-remove-member]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const [teamId, memberId] = btn.dataset.removeMember.split(":");
        await api("DELETE", `/mod/team/${teamId}/member/${memberId}`);
        await loadAll();
      });
    });

    document.getElementById("reset-all-teams-btn").addEventListener("click", async () => {
      if (
        !confirm(
          "Reset EVERY team's progress and clear the entire activity log? This is meant for the moment testing ends and the real event begins — it cannot be undone."
        )
      )
        return;
      try {
        const result = await api("POST", "/mod/teams/reset-all");
        await loadAll();
        await refreshActivity().catch(() => {});
        flash(`Reset ${result.teams_reset} team(s).`);
      } catch (err) {
        flash(err.message);
      }
    });

    el.querySelectorAll("[data-rename-team]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const teamId = form.dataset.renameTeam;
        const fd = new FormData(form);
        try {
          await api("PATCH", `/mod/team/${teamId}`, { name: fd.get("name") });
          await loadAll();
          flash("Team renamed.");
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-reset-team]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Reset this team's progress? Missions, fragments, clearance stamps, and submissions will be cleared. The team and its members stay.")) return;
        try {
          await api("POST", `/mod/team/${btn.dataset.resetTeam}/reset`);
          await loadAll();
          flash("Team progress reset.");
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-delete-team]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this team permanently? This cannot be undone.")) return;
        try {
          await api("DELETE", `/mod/team/${btn.dataset.deleteTeam}`);
          await loadAll();
          flash("Team deleted.");
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-set-booth]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const teamId = form.dataset.setBooth;
        const fd = new FormData(form);
        try {
          await api("POST", `/mod/team/${teamId}/starting-booth`, {
            mission_id: fd.get("mission_id") ? Number(fd.get("mission_id")) : null,
          });
          await loadAll();
          flash("Starting booth updated.");
        } catch (err) {
          flash(err.message);
        }
      });
    });
  }

  let agentSearchQuery = "";

  function fmtLastLogin(iso) {
    if (!iso) return "Never logged in";
    return new Date(iso + "Z").toLocaleString();
  }

  function renderAgentOverview() {
    const el = document.getElementById("agent-overview");
    if (!el) return;

    const q = agentSearchQuery.trim().toLowerCase();
    const visibleAgents = q
      ? agents.filter(
          (a) =>
            (a.email || "").toLowerCase().includes(q) ||
            (a.full_name || "").toLowerCase().includes(q)
        )
      : agents;

    const rows = visibleAgents
      .map((a) => {
        const missionList = a.missions.length
          ? a.missions.map((m) => `<li>${escapeHtml(m.title)} — <span class="badge">${m.grading_mode || "not configured"}</span></li>`).join("")
          : `<li class="hint-text">No booth assigned yet.</li>`;
        return `
        <div class="card" style="margin-bottom:0.75rem;">
          <div class="queue-card-header">
            <strong>${icon("flame-kindling", 13)} ${escapeHtml(a.full_name || a.email)}</strong>
            <div style="display:flex;gap:0.4rem;align-items:center;flex-wrap:wrap;">
              <span class="badge ${a.is_active ? "badge-active" : "badge-not_started"}">${a.is_active ? "Active" : "Inactive"}</span>
              <button type="button" class="ghost" data-reset-agent-password="${a.id}" data-agent-email="${escapeHtml(a.email)}">${icon("key", 12)} Reset Password</button>
              <button type="button" class="ghost" data-toggle-agent="${a.id}" data-active="${a.is_active}">${a.is_active ? icon("lock", 12) + " Deactivate" : icon("unlock", 12) + " Activate"}</button>
              <button type="button" class="danger" data-delete-agent="${a.id}">${icon("trash-2", 12)} Delete</button>
            </div>
          </div>
          <p class="hint-text">${escapeHtml(a.email)} — last login: ${escapeHtml(fmtLastLogin(a.last_login_at))}</p>
          <form class="inline-form" data-edit-agent="${a.id}" style="margin-top:0.4rem;">
            <input type="text" name="full_name" placeholder="Full name" value="${escapeHtml(a.full_name || "")}" style="width:auto;">
            <input type="email" name="email" value="${escapeHtml(a.email)}" required style="width:auto;">
            <button type="submit" class="ghost">${icon("pencil", 12)} Save</button>
          </form>
          <ul style="margin:0.4rem 0;">${missionList}</ul>
          <form class="inline-form" data-assign-agent="${a.id}">
            <select name="mission_id" style="width:auto;">
              <option value="">— assign a booth —</option>
              ${missions.map((m) => `<option value="${m.id}">${escapeHtml(m.title)}</option>`).join("")}
            </select>
            <button type="submit" class="ghost">${icon("server", 12)} Assign</button>
          </form>
        </div>`;
      })
      .join("");
    el.innerHTML =
      rows ||
      `<p class="hint-text">${agents.length ? "No booth agents match that search." : "No booth agents on file yet."}</p>`;

    el.querySelectorAll("[data-assign-agent]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const agentId = form.dataset.assignAgent;
        const fd = new FormData(form);
        const missionId = fd.get("mission_id");
        if (!missionId) return;
        try {
          await api("POST", `/mod/mission/${missionId}/assign-agent`, { agent_id: Number(agentId) });
          await loadAll();
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-edit-agent]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const agentId = form.dataset.editAgent;
        const fd = new FormData(form);
        try {
          await api("PUT", `/mod/agents/${agentId}`, {
            full_name: fd.get("full_name"),
            email: fd.get("email"),
          });
          await loadAll();
          flash("Agent updated.");
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-toggle-agent]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const agentId = btn.dataset.toggleAgent;
        const isActive = btn.dataset.active === "true";
        if (isActive && !confirm("Deactivate this agent? They'll be logged out of any open session immediately and can't log back in until reactivated.")) return;
        try {
          await api("POST", `/mod/agents/${agentId}/active`, { is_active: !isActive });
          await loadAll();
          flash(isActive ? "Agent deactivated." : "Agent activated.");
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-reset-agent-password]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const email = btn.dataset.agentEmail;
        if (!confirm(`Generate a new password for ${email}? Their current password stops working immediately.`)) return;
        try {
          lastCredential = await api("POST", "/mod/credentials/generate", { kind: "booth_agent", name: email });
          renderTeamAdmin();
        } catch (err) {
          flash(err.message);
        }
      });
    });

    el.querySelectorAll("[data-delete-agent]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this agent permanently? This only works if they own no booths. This cannot be undone.")) return;
        try {
          await api("DELETE", `/mod/agents/${btn.dataset.deleteAgent}`);
          await loadAll();
          flash("Agent deleted.");
        } catch (err) {
          flash(err.message);
        }
      });
    });
  }

  async function refreshSubmissions() {
    const el = document.getElementById("submissions-feed");
    if (!el) return;
    const data = await api("GET", "/mod/submissions");
    const rows = data.submissions
      .map(
        (s) => `
      <tr>
        <td>${escapeHtml(s.team)}</td>
        <td>${escapeHtml(s.mission)}</td>
        <td><span class="badge ${s.mode === "submit" ? "badge-active" : "badge-not_started"}">${s.mode}</span></td>
        <td>${s.passed_tests}/${s.total_tests} (${s.percent_score}%)</td>
        <td>${s.passed ? icon("check", 13) : icon("x", 13)}</td>
      </tr>`
      )
      .join("");
    el.innerHTML = `
      <div class="data-grid-wrap">
        <table class="data-table">
          <thead><tr><th>Team</th><th>Mission</th><th>Mode</th><th>Result</th><th>Passed</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="5" class="hint-text">No auto-graded submissions yet.</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  async function refreshActivity() {
    const el = document.getElementById("activity-feed");
    if (!el) return;
    const data = await api("GET", "/mod/activity");
    const rows = data.logs
      .map(
        (l) => `
      <tr>
        <td>${escapeHtml(l.when)}</td>
        <td>${escapeHtml(l.actor_role)}</td>
        <td>${escapeHtml(l.action)}</td>
        <td>${escapeHtml(l.metadata || "—")}</td>
      </tr>`
      )
      .join("");
    el.innerHTML = `
      <div class="data-grid-wrap">
        <table class="data-table">
          <thead><tr><th>When</th><th>Actor role</th><th>Action</th><th>Details</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="4" class="hint-text">No activity logged yet.</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  async function loadAll() {
    const [dataRes, missionsRes, agentsRes] = await Promise.all([
      api("GET", "/mod/data"),
      api("GET", "/mod/missions"),
      api("GET", "/mod/agents"),
    ]);
    teams = dataRes.teams;
    missions = missionsRes.missions;
    agents = agentsRes.agents;
    renderTeamAdmin();
    renderAgentOverview();
  }

  if (typeof socket !== "undefined" && socket) {
    socket.on("mod_update", () => {
      refreshSubmissions().catch(() => {});
      refreshActivity().catch(() => {});
    });
  }

  const agentSearchInput = document.getElementById("agent-search");
  if (agentSearchInput) {
    agentSearchInput.addEventListener("input", () => {
      agentSearchQuery = agentSearchInput.value;
      renderAgentOverview();
    });
  }

  loadAll().catch((err) => flash(err.message));
  refreshSubmissions().catch(() => {});
  refreshActivity().catch(() => {});
  setInterval(() => {
    refreshSubmissions().catch(() => {});
    refreshActivity().catch(() => {});
  }, 3000);
})();
