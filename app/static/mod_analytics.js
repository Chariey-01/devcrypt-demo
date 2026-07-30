(async function () {
  const el = document.getElementById("analytics-content");
  async function load() {
    el.innerHTML = `<p class="hint-text">${icon("radar", 13)} Loading analytics…</p>`;
    let data;
    try {
      const res = await fetch("/mod/analytics/data");
      data = await res.json();
    } catch (e) {
      el.innerHTML = `<p class="hint-text">${icon("alert-triangle", 13)} Failed to load analytics.</p>`;
      return;
    }

    const pf = data.pass_fail;
    const passRate = pf.total ? Math.round((pf.passed / pf.total) * 100) : 0;
    const avgTime =
      data.average_completion_seconds == null
        ? "—"
        : `${Math.floor(data.average_completion_seconds / 60)}m ${Math.round(data.average_completion_seconds % 60)}s`;

    const challengeRows = data.challenge_stats
      .map(
        (c) => `
      <tr>
        <td>${escapeHtml(c.title)}</td>
        <td>${c.attempts}</td>
        <td>${c.passed}</td>
        <td>${c.pass_rate == null ? "—" : c.pass_rate + "%"}</td>
      </tr>`
      )
      .join("");

    el.innerHTML = `
      <p class="section-heading">${icon("gauge", 14)} Submissions</p>
      <div class="ops-grid">
        <div class="ops-panel">
          <p class="ops-label">${icon("scan-line", 14)} Total Submissions</p>
          <p class="ops-value info">${data.total_submissions}</p>
        </div>
        <div class="ops-panel">
          <p class="ops-label">${icon("check", 14)} Pass Rate</p>
          <p class="ops-value ${passRate >= 50 ? "ok" : "warn"}">${passRate}%</p>
          <div class="timer-bar"><div class="timer-fill" style="width:${passRate}%"></div></div>
          <p class="ops-sub">${pf.passed} passed / ${pf.failed} failed</p>
        </div>
        <div class="ops-panel">
          <p class="ops-label">${icon("timer", 14)} Avg. Completion Time</p>
          <p class="ops-value info">${avgTime}</p>
        </div>
        <div class="ops-panel">
          <p class="ops-label">${icon("key", 14)} Hints Used</p>
          <p class="ops-value info">${data.hint_usage.total_hints_used}</p>
          <p class="ops-sub">${data.hint_usage.missions_with_hint_used} missions used a hint</p>
        </div>
      </div>

      ${
        data.most_failed_challenge
          ? `<p class="narrative-message">${icon("alert-triangle", 13)} Most-failed challenge: <strong>${escapeHtml(
              data.most_failed_challenge.title
            )}</strong> (${data.most_failed_challenge.pass_rate}% pass rate, ${
              data.most_failed_challenge.attempts
            } attempts)</p>`
          : ""
      }

      <p class="section-heading" style="margin-top:1rem;">${icon("network", 14)} Per-Challenge Stats</p>
      <div class="data-grid-wrap">
        <table class="data-table">
          <thead><tr><th>Challenge</th><th>Attempts</th><th>Passed</th><th>Pass Rate</th></tr></thead>
          <tbody>${challengeRows || `<tr><td colspan="4" class="hint-text">No auto-graded submissions yet.</td></tr>`}</tbody>
        </table>
      </div>
      <button type="button" class="ghost" id="analytics-refresh" style="margin-top:1rem;">${icon("rotate-ccw", 13)} Refresh</button>
    `;
    document.getElementById("analytics-refresh").addEventListener("click", load);
  }
  load();
})();
