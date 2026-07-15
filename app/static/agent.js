/* ---------------------------------------------------------------- */
/* Agent Dashboard — challenge authoring for stakeholder booths      */
/* ---------------------------------------------------------------- */

(function agentPage() {
  if (typeof PAGE === "undefined" || PAGE !== "agent") return;

  let missions = [];
  let selected = null; // full mission detail, once chosen
  let activeTab = "challenge";
  let flashText = null;

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
    renderAll();
    clearTimeout(flash._t);
    flash._t = setTimeout(() => {
      flashText = null;
      renderAll();
    }, 3500);
  }

  async function loadMissions() {
    const data = await api("GET", "/agent/missions");
    missions = data.missions;
    if (selected && !missions.find((m) => m.id === selected.id)) {
      selected = null;
    }
    renderAll();
  }

  async function selectMission(id) {
    selected = await api("GET", `/agent/missions/${id}`);
    activeTab = "challenge";
    renderAll();
  }

  // Re-fetches the current mission's data (after a test case / hint / asset CRUD
  // action) without resetting activeTab — selectMission() always jumps back to the
  // Challenge tab, which is correct when switching missions but wrong mid-edit.
  async function refreshSelected() {
    selected = await api("GET", `/agent/missions/${selected.id}`);
    renderAll();
  }

  function renderAll() {
    renderMissionList();
    renderEditor();
  }

  function renderMissionList() {
    const el = document.getElementById("agent-mission-list");
    const cards = missions
      .map(
        (m) => `
      <div class="card" style="margin-bottom:0.75rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;flex-wrap:wrap;">
          <div>
            <strong>${icon("server", 14)} ${escapeHtml(m.title)}</strong>
            <span class="badge ${m.grading_mode === "auto" ? "badge-passed" : "badge-not_started"}">
              ${m.grading_mode === "auto" ? "Auto-graded" : "No challenge yet"}
            </span>
          </div>
          <div style="display:flex;gap:0.4rem;">
            <button type="button" data-select="${m.id}">${icon("terminal", 13)} Manage</button>
            <button type="button" class="danger" data-delete="${m.id}">${icon("x", 13)} Delete</button>
          </div>
        </div>
      </div>`
      )
      .join("");

    el.innerHTML = `
      ${flashText ? `<div class="flash flash-info" style="margin-bottom:0.75rem;">${escapeHtml(flashText)}</div>` : ""}
      ${cards || `<p class="hint-text">${icon("radar", 13)} You don't own any booths yet — create one below.</p>`}
      <form id="create-mission-form" class="auth-form" style="margin-top:0.75rem;">
        <input type="text" name="title" placeholder="Problem title, e.g. Discovery Node — DEPLOY" required>
        <input type="text" name="cipher_word" placeholder="Cipher word, e.g. DEPLOY" required>
        <textarea name="narrative" placeholder="Narrative / booth intro shown to teams" required rows="2"></textarea>
        <input type="number" name="time_limit" placeholder="Time limit (seconds, optional)">
        <button type="submit">${icon("zap", 13)} Create Booth</button>
      </form>
    `;

    el.querySelectorAll("[data-select]").forEach((btn) => {
      btn.addEventListener("click", () => selectMission(Number(btn.dataset.select)));
    });
    el.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this booth and all of its challenge content? This cannot be undone.")) return;
        await api("DELETE", `/agent/missions/${btn.dataset.delete}`);
        await loadMissions();
      });
    });
    const createForm = document.getElementById("create-mission-form");
    if (createForm) {
      createForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(createForm);
        try {
          const created = await api("POST", "/agent/missions", {
            title: fd.get("title"),
            cipher_word: fd.get("cipher_word"),
            narrative: fd.get("narrative"),
            time_limit: fd.get("time_limit") ? Number(fd.get("time_limit")) : null,
          });
          await loadMissions();
          await selectMission(created.id);
          flash("Booth created.");
        } catch (err) {
          flash(err.message);
        }
      });
    }
  }

  function renderEditor() {
    const el = document.getElementById("agent-editor");
    if (!selected) {
      el.innerHTML = "";
      return;
    }
    const tabs = [
      ["challenge", "Challenge"],
      ["tests", "Test Suite"],
      ["hints", "Hints"],
      ["assets", "Files"],
    ];
    el.innerHTML = `
      <p class="section-heading">${icon("crosshair", 14)} Editing: ${escapeHtml(selected.title)}</p>
      <div class="tabs">
        ${tabs
          .map(
            ([key, label]) =>
              `<button type="button" class="tab ${activeTab === key ? "active" : ""}" data-tab="${key}">${escapeHtml(label)}</button>`
          )
          .join("")}
      </div>
      <div id="agent-tab-content" class="card"></div>
    `;
    el.querySelectorAll("[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = btn.dataset.tab;
        renderEditor();
      });
    });
    const content = document.getElementById("agent-tab-content");
    if (activeTab === "challenge") renderChallengeTab(content);
    else if (activeTab === "tests") renderTestsTab(content);
    else if (activeTab === "hints") renderHintsTab(content);
    else if (activeTab === "assets") renderAssetsTab(content);
  }

  function renderChallengeTab(el) {
    const c = selected.challenge || {};
    el.innerHTML = `
      <form id="challenge-form" class="auth-form">
        <label>Problem title
          <input type="text" name="title" value="${escapeHtml(c.title || "")}">
        </label>
        <label>Problem statement
          <textarea name="prompt" rows="4" required>${escapeHtml(c.prompt || "")}</textarea>
        </label>
        <label>Language
          <select name="language">
            <option value="python" ${(c.language || "python") === "python" ? "selected" : ""}>Python</option>
          </select>
        </label>
        <label>Expected function signature
          <input type="text" name="function_signature" placeholder="def solve(n: int) -> int:" value="${escapeHtml(c.function_signature || "")}">
        </label>
        <label>Starter code (shown to players)
          <textarea name="starter_code" rows="4" class="mono">${escapeHtml(c.starter_code || "")}</textarea>
        </label>
        <label>${icon("lock", 12)} Solution code (private — never shown to players)
          <textarea name="solution_code" rows="4" class="mono">${escapeHtml(c.solution_code || "")}</textarea>
        </label>
        <div class="ops-grid">
          <label>Pass threshold (%)<input type="number" name="pass_threshold" min="1" max="100" value="${c.pass_threshold ?? 100}"></label>
          <label>Bonus points<input type="number" name="bonus_points" min="0" value="${c.bonus_points ?? 0}"></label>
          <label>Max attempts<input type="number" name="max_attempts" min="1" value="${c.max_attempts ?? ""}" placeholder="Unlimited"></label>
          <label>Per-test timeout (s)<input type="number" name="time_limit_seconds" min="1" max="30" value="${c.time_limit_seconds ?? 5}"></label>
        </div>
        <button type="submit">${icon("check", 13)} Save Challenge</button>
      </form>
    `;
    document.getElementById("challenge-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        selected = await api("PUT", `/agent/missions/${selected.id}/challenge`, {
          title: fd.get("title"),
          prompt: fd.get("prompt"),
          language: fd.get("language"),
          function_signature: fd.get("function_signature"),
          starter_code: fd.get("starter_code"),
          solution_code: fd.get("solution_code"),
          pass_threshold: Number(fd.get("pass_threshold") || 100),
          bonus_points: Number(fd.get("bonus_points") || 0),
          max_attempts: fd.get("max_attempts") ? Number(fd.get("max_attempts")) : null,
          time_limit_seconds: Number(fd.get("time_limit_seconds") || 5),
        });
        await loadMissions();
        flash("Challenge saved.");
      } catch (err) {
        flash(err.message);
      }
    });
  }

  function renderTestsTab(el) {
    if (!selected.challenge) {
      el.innerHTML = `<p class="hint-text">${icon("alert-triangle", 13)} Save the challenge before adding test cases.</p>`;
      return;
    }
    const rows = selected.test_cases
      .map(
        (tc, i) => `
      <tr data-tc="${tc.id}">
        <td>${escapeHtml(tc.name)}</td>
        <td><span class="badge ${tc.visibility === "hidden" ? "badge-overridden" : "badge-active"}">${tc.visibility}</span></td>
        <td>${tc.weight}</td>
        <td>
          <button type="button" data-move-up="${tc.id}" ${i === 0 ? "disabled" : ""}>${icon("chevron-left", 12)}</button>
          <button type="button" data-move-down="${tc.id}" ${i === selected.test_cases.length - 1 ? "disabled" : ""}>${icon("chevron-right", 12)}</button>
          <button type="button" data-edit="${tc.id}">${icon("terminal", 12)}</button>
          <button type="button" class="danger" data-remove="${tc.id}">${icon("x", 12)}</button>
        </td>
      </tr>`
      )
      .join("");

    el.innerHTML = `
      <div class="grid-toolbar">
        <button type="button" id="tc-add">${icon("zap", 13)} Add Test Case</button>
        <button type="button" id="tc-export" class="ghost">${icon("database", 13)} Export</button>
        <button type="button" id="tc-import" class="ghost">${icon("radio", 13)} Import</button>
      </div>
      <div class="data-grid-wrap">
        <table class="data-table">
          <thead><tr><th>Name</th><th>Visibility</th><th>Weight</th><th>Actions</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="4" class="hint-text">No test cases yet.</td></tr>`}</tbody>
        </table>
      </div>
      <div id="tc-form-slot"></div>
    `;

    document.getElementById("tc-add").addEventListener("click", () => showTestCaseForm(null));
    document.getElementById("tc-export").addEventListener("click", async () => {
      const data = await api("GET", `/agent/missions/${selected.id}/testcases/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${selected.cipher_word || "testcases"}.json`;
      a.click();
    });
    document.getElementById("tc-import").addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "application/json";
      input.addEventListener("change", async () => {
        const file = input.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const parsed = JSON.parse(text);
          const result = await api("POST", `/agent/missions/${selected.id}/testcases/import`, parsed);
          await refreshSelected();
          flash(`Imported ${result.imported} test case(s).`);
        } catch (err) {
          flash(err.message || "Import failed — check the file is valid JSON.");
        }
      });
      input.click();
    });
    el.querySelectorAll("[data-edit]").forEach((btn) =>
      btn.addEventListener("click", () => showTestCaseForm(selected.test_cases.find((t) => t.id === Number(btn.dataset.edit))))
    );
    el.querySelectorAll("[data-remove]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        await api("DELETE", `/agent/testcases/${btn.dataset.remove}`);
        await refreshSelected();
      })
    );
    el.querySelectorAll("[data-move-up]").forEach((btn) =>
      btn.addEventListener("click", () => reorder(Number(btn.dataset.moveUp), -1))
    );
    el.querySelectorAll("[data-move-down]").forEach((btn) =>
      btn.addEventListener("click", () => reorder(Number(btn.dataset.moveDown), 1))
    );
  }

  async function reorder(tcId, direction) {
    const ids = selected.test_cases.map((t) => t.id);
    const idx = ids.indexOf(tcId);
    const swapWith = idx + direction;
    if (swapWith < 0 || swapWith >= ids.length) return;
    [ids[idx], ids[swapWith]] = [ids[swapWith], ids[idx]];
    await api("POST", `/agent/missions/${selected.id}/testcases/reorder`, { order: ids });
    await refreshSelected();
  }

  function showTestCaseForm(tc) {
    const slot = document.getElementById("tc-form-slot");
    slot.innerHTML = `
      <form id="tc-form" class="auth-form" style="margin-top:0.75rem;">
        <label>Test name<input type="text" name="name" value="${escapeHtml(tc?.name || "")}" required></label>
        <label>Input (fed to the script on stdin)<textarea name="input_data" rows="2">${escapeHtml(tc?.input_data || "")}</textarea></label>
        <label>Expected output (stdout, exact match)<textarea name="expected_output" rows="2" required>${escapeHtml(tc?.expected_output || "")}</textarea></label>
        <div class="ops-grid">
          <label>Weight<input type="number" name="weight" min="1" value="${tc?.weight ?? 1}"></label>
          <label>Visibility
            <select name="visibility">
              <option value="visible" ${!tc || tc.visibility === "visible" ? "selected" : ""}>Visible</option>
              <option value="hidden" ${tc?.visibility === "hidden" ? "selected" : ""}>Hidden</option>
            </select>
          </label>
        </div>
        <label>Failure message (shown to players on this test failing)
          <input type="text" name="failure_message" value="${escapeHtml(tc?.failure_message || "")}">
        </label>
        <div style="display:flex;gap:0.5rem;">
          <button type="submit">${icon("check", 13)} ${tc ? "Save" : "Add"} Test Case</button>
          <button type="button" class="ghost" id="tc-form-cancel">Cancel</button>
        </div>
      </form>
    `;
    document.getElementById("tc-form-cancel").addEventListener("click", () => (slot.innerHTML = ""));
    document.getElementById("tc-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = {
        name: fd.get("name"),
        input_data: fd.get("input_data"),
        expected_output: fd.get("expected_output"),
        weight: Number(fd.get("weight") || 1),
        visibility: fd.get("visibility"),
        failure_message: fd.get("failure_message"),
      };
      try {
        if (tc) await api("PUT", `/agent/testcases/${tc.id}`, body);
        else await api("POST", `/agent/missions/${selected.id}/testcases`, body);
        await refreshSelected();
        flash("Test case saved.");
      } catch (err) {
        flash(err.message);
      }
    });
  }

  function renderHintsTab(el) {
    if (!selected.challenge) {
      el.innerHTML = `<p class="hint-text">${icon("alert-triangle", 13)} Save the challenge before adding hints.</p>`;
      return;
    }
    const rows = selected.hints
      .map(
        (h) => `
      <div class="card" style="margin-bottom:0.5rem;">
        <p>${escapeHtml(h.text)} ${h.point_cost ? `<span class="badge">-${h.point_cost} pts</span>` : ""}</p>
        <button type="button" class="danger" data-remove-hint="${h.id}">${icon("x", 12)} Remove</button>
      </div>`
      )
      .join("");
    el.innerHTML = `
      ${rows || `<p class="hint-text">No hints configured yet.</p>`}
      <form id="hint-form" class="auth-form">
        <textarea name="text" rows="2" placeholder="Hint text" required></textarea>
        <input type="number" name="point_cost" placeholder="Point cost (optional)">
        <button type="submit">${icon("zap", 13)} Add Hint</button>
      </form>
    `;
    el.querySelectorAll("[data-remove-hint]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        await api("DELETE", `/agent/hints/${btn.dataset.removeHint}`);
        await refreshSelected();
      })
    );
    document.getElementById("hint-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      await api("POST", `/agent/missions/${selected.id}/hints`, {
        text: fd.get("text"),
        point_cost: fd.get("point_cost") ? Number(fd.get("point_cost")) : null,
      });
      await refreshSelected();
    });
  }

  function renderAssetsTab(el) {
    const rows = selected.assets
      .map(
        (a) => `
      <div class="card" style="margin-bottom:0.5rem;">
        <strong>${icon("file-lock-2", 13)} ${escapeHtml(a.label)}</strong> <span class="badge">${escapeHtml(a.file_type)}</span>
        <pre>${escapeHtml(a.content)}</pre>
        <button type="button" class="danger" data-remove-asset="${a.id}">${icon("x", 12)} Remove</button>
      </div>`
      )
      .join("");
    el.innerHTML = `
      ${rows || `<p class="hint-text">No supporting files uploaded yet.</p>`}
      <form id="asset-form" class="auth-form">
        <input type="text" name="label" placeholder="Filename, e.g. login.py" required>
        <input type="text" name="file_type" placeholder="Type, e.g. python, log, sql" value="text">
        <textarea name="content" rows="4" class="mono" placeholder="Paste the vulnerable/incomplete source or supporting file content" required></textarea>
        <button type="submit">${icon("zap", 13)} Upload File</button>
      </form>
    `;
    el.querySelectorAll("[data-remove-asset]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        await api("DELETE", `/agent/assets/${btn.dataset.removeAsset}`);
        await refreshSelected();
      })
    );
    document.getElementById("asset-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      await api("POST", `/agent/missions/${selected.id}/assets`, {
        label: fd.get("label"),
        file_type: fd.get("file_type"),
        content: fd.get("content"),
      });
      await refreshSelected();
    });
  }

  loadMissions().catch((err) => flash(err.message));
})();
