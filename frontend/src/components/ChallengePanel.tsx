import { useRef, useState } from "react";
import { Icon } from "../icons";
import { api } from "../api";
import { draftStore, testResultsStore } from "../hooks/useLocalDraft";
import { MonacoCodeEditor, type MonacoCodeEditorHandle } from "./MonacoCodeEditor";
import type { Mission, RunTestsResponse, SubmitResponse } from "../types";

function TestResults({ results }: { results: RunTestsResponse }) {
  const allPassed = results.passed_tests === results.total_tests;
  return (
    <>
      <p className="hint-text" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span className={`badge ${allPassed ? "badge-test-pass" : "badge-test-fail"}`}>
          <Icon name="gauge" size={12} /> {results.passed_tests} / {results.total_tests} passed
        </span>
      </p>
      <div className="ops-grid">
        {results.results.map((r, i) => (
          <div className="ops-panel" key={i}>
            <p className="ops-value">
              <span className={`badge ${r.passed ? "badge-test-pass" : "badge-test-fail"}`}>
                <Icon name={r.passed ? "check" : "x"} size={12} /> {r.passed ? "PASS" : "FAIL"}
              </span>
            </p>
            <p className="ops-sub" style={{ fontSize: "0.78rem", color: "var(--text)", marginTop: "0.3rem" }}>
              {r.name}
            </p>
            {!r.passed && r.failure_message && <p className="hint-text">{r.failure_message}</p>}
            {r.visibility === "visible" && (
              <p className="hint-text mono">
                input: {r.input_data ?? ""} — expected: {r.expected_output ?? ""} — got: {r.actual_output ?? ""}
              </p>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

export function ChallengePanel({
  mission,
  teamName,
  softLockMinAttempts,
  showMessage,
  onSubmitted,
}: {
  mission: Mission;
  teamName: string | null;
  softLockMinAttempts: number;
  showMessage: (text: string) => void;
  onSubmitted: () => void;
}) {
  const challenge = mission.challenge!;
  const editorRef = useRef<MonacoCodeEditorHandle>(null);
  const [draftAnswer, setDraftAnswer] = useState("");
  const [testResults, setTestResults] = useState<RunTestsResponse | null>(() =>
    testResultsStore.load(teamName, mission.id, null) as RunTestsResponse | null
  );
  const [runningTests, setRunningTests] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const isAutoGraded = challenge.grading_mode === "auto" || challenge.grading_mode === "pytest";

  async function runTests() {
    if (!editorRef.current) {
      showMessage("Code editor is still loading — try again in a moment.");
      return;
    }
    setRunningTests(true);
    try {
      const code = editorRef.current.getValue();
      const res = await api<RunTestsResponse>("/missions/challenge/run-tests", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      if (res.ok) {
        setTestResults(res.data);
        testResultsStore.save(teamName, mission.id, res.data);
      } else {
        showMessage((res.data as unknown as { error?: string }).error ?? "Run failed.");
      }
    } finally {
      setRunningTests(false);
    }
  }

  async function submit() {
    if (isAutoGraded && !editorRef.current) {
      showMessage("Code editor is still loading — try again in a moment.");
      return;
    }
    setSubmitting(true);
    try {
      const value = isAutoGraded ? editorRef.current!.getValue() : draftAnswer;
      const res = await api<SubmitResponse>("/missions/challenge/submit", {
        method: "POST",
        body: JSON.stringify({ answer: value, code: value }),
      });
      if (!isAutoGraded) setDraftAnswer("");
      setTestResults(null);
      const detail =
        res.data.percent_score !== undefined
          ? ` (${res.data.passed_tests}/${res.data.total_tests} tests, ${res.data.percent_score}%)`
          : "";
      showMessage((res.data.message || res.data.error || "") + detail);
      onSubmitted();
    } finally {
      setSubmitting(false);
    }
  }

  async function requestHint() {
    const hintNumber = (challenge.hints_taken || 0) + 1;
    if (
      !window.confirm(
        `Request hint ${hintNumber} for this booth? Costs 15 points and 10% integrity. This can't be undone.`
      )
    )
      return;
    const res = await api<{ hint: string | null; error?: string }>("/missions/hint", { method: "POST" });
    showMessage(res.data.hint ? `HINT ${hintNumber}: ${res.data.hint}` : res.data.error || "");
    onSubmitted();
  }

  async function softLock() {
    if (
      !window.confirm(
        "Soft Lock this booth? You'll get a small participation score, no fragment, and move straight to the next booth. This can't be undone from your side."
      )
    )
      return;
    const res = await api<{ message?: string; error?: string }>("/missions/soft-lock", { method: "POST" });
    showMessage(res.data.message || res.data.error || "");
    onSubmitted();
  }

  if (mission.pending_review) {
    return (
      <p className="narrative-message">
        <Icon name="eye" size={13} /> SUBMISSION ROUTED TO FIELD AGENT FOR REVIEW.
      </p>
    );
  }

  const startValue = draftStore.load(
    teamName,
    mission.id,
    challenge.last_submitted_code || challenge.starter_code || ""
  );

  return (
    <>
      <p className="section-heading">
        <Icon name="terminal" size={14} /> Mission Action — Submission Panel
      </p>
      <p style={{ whiteSpace: "pre-line" }}>{challenge.prompt}</p>

      {isAutoGraded ? (
        <>
          {challenge.function_signature && (
            <p className="hint-text mono">
              <Icon name="terminal" size={12} /> {challenge.function_signature}
            </p>
          )}
          <div className="ide-panel">
            <div className="ide-toolbar">
              <span className="ide-toolbar-label">
                <Icon name="terminal" size={13} /> Code Editor{" "}
                <span className="mono ide-lang">{challenge.language || "python"}</span>
              </span>
              {challenge.max_attempts != null && (
                <span className="ide-toolbar-note">
                  <Icon name="activity" size={12} /> Attempts used: {challenge.attempts_used} / {challenge.max_attempts}
                </span>
              )}
            </div>
            <MonacoCodeEditor
              ref={editorRef}
              missionId={mission.id}
              teamName={teamName}
              language={challenge.language}
              startValue={startValue}
            />
            <div className="ide-actions">
              <button className="ghost" type="button" disabled={runningTests} onClick={runTests}>
                <Icon name="scan-line" size={13} /> {runningTests ? "Testing…" : "Run Visible Tests"}
              </button>
              <button disabled={submitting} onClick={submit}>
                <Icon name="unlock" size={13} /> {submitting ? "Grading…" : "Submit Solution"}
              </button>
            </div>
            <p className="hint-text ide-hidden-note">
              <Icon name="lock-keyhole" size={12} /> Submit also grades against hidden test cases
              you won't see the details of here — passing Run Visible Tests doesn't guarantee a
              pass.
            </p>
            <div id="test-results">{testResults && <TestResults results={testResults} />}</div>
          </div>
        </>
      ) : (
        <>
          <textarea
            rows={4}
            placeholder={challenge.type === "flag" ? "FLAG{...}" : "Type your fix here…"}
            value={draftAnswer}
            onChange={(e) => setDraftAnswer(e.target.value)}
          />
          <button disabled={submitting} onClick={submit}>
            <Icon name="unlock" size={13} /> {submitting ? "Grading…" : "Decrypt & Submit"}
          </button>
        </>
      )}

      {mission.penalty_remaining ? (
        <p className="narrative-message">
          <Icon name="timer" size={13} /> NODE ON COOLDOWN — {mission.penalty_remaining}s remaining.
        </p>
      ) : null}

      {(challenge.hints_revealed || []).map((text, i) => (
        <p className="narrative-message" key={i}>
          <Icon name="key" size={13} /> HINT {i + 1}: {text}
        </p>
      ))}

      {challenge.hints_available > 0 && (
        <button className="ghost" type="button" onClick={requestHint}>
          <Icon name="key" size={13} /> Request Hint ({challenge.hints_available} left this booth)
        </button>
      )}

      {mission.attempts >= softLockMinAttempts && (
        <div className="soft-lock-offer">
          <p className="hint-text">
            <Icon name="shield-alert" size={12} /> Stuck? You can Soft Lock this booth — a small
            participation score, no fragment, and you'll move straight to the next booth.
          </p>
          <button className="ghost" type="button" onClick={softLock}>
            <Icon name="chevron-right" size={13} /> Soft Lock This Booth
          </button>
        </div>
      )}
    </>
  );
}
