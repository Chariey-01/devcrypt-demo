import { useState } from "react";
import { Icon } from "../icons";
import { computeTimerDisplay } from "../lib/timer";
import { KnowledgeCheck } from "./KnowledgeCheck";
import { ChallengePanel } from "./ChallengePanel";
import type { Mission, MissionStatus } from "../types";

function missionThreat(mission: Mission) {
  if (mission.penalty_remaining) return { label: "ELEVATED", tier: "warn" };
  if (mission.attempts > 1) return { label: "ELEVATED", tier: "warn" };
  return { label: "ACTIVE", tier: "info" };
}

function missionStage(mission: Mission) {
  if (mission.pending_review) return { label: "AWAITING REVIEW", tier: "warn" };
  if (mission.penalty_remaining) return { label: "ON COOLDOWN", tier: "warn" };
  if (!mission.knowledge_check_complete) return { label: "KNOWLEDGE CHECK", tier: "info" };
  return { label: "MISSION ACTION", tier: "info" };
}

// Ported from app/static/app.js's renderMissionPanel(). Rendered with key={mission.id} by
// App.tsx, so the evidence-tab selection (and ChallengePanel's own per-mission local state)
// resets naturally on a booth change -- React's remount does what the vanilla version had to
// do by hand (disposing Monaco, clearing draftAnswer, resetting activeTab) on a mission-id
// change.
//
// Not ported: the "prompt was just updated by an Agent mid-edit" banner. It existed to paper
// over a real problem in the vanilla version -- a raw innerHTML rebuild while a player was
// mid-keystroke would silently blow away their draft and cursor position, so refresh() froze
// the whole panel until they defocused. React doesn't have that problem: props (including a
// live-edited prompt) always reflect the latest poll, and neither the Monaco draft nor the
// plain-textarea draftAnswer state are touched by a prompt string changing above them. Cutting
// this is a real scope reduction, not an oversight -- there's no rebuild left to warn about.
export function MissionPanel({
  data,
  teamName,
  message,
  showMessage,
  onSubmitted,
}: {
  data: MissionStatus;
  teamName: string | null;
  message: string | null;
  showMessage: (text: string) => void;
  onSubmitted: () => void;
}) {
  const [activeTab, setActiveTab] = useState(0);
  const mission = data.mission!;

  const nodesSecured = (data.cryptogram || []).filter((w) => w.complete).length;
  const nodesTotal = (data.cryptogram || []).length;
  const threat = missionThreat(mission);
  const stage = missionStage(mission);
  const missionCode = `NODE-${String(mission.id).padStart(2, "0")}`;
  const timer = computeTimerDisplay(mission);

  const activeEvidence = mission.evidence_files[activeTab];
  let evidenceContent: React.ReactNode = null;
  if (activeEvidence?.has_binary) {
    const downloadUrl = `/missions/assets/${activeEvidence.id}/download`;
    evidenceContent = (activeEvidence.mime_type || "").startsWith("image/") ? (
      <a href={downloadUrl} target="_blank" rel="noopener noreferrer">
        <img
          src={downloadUrl}
          alt={activeEvidence.filename || activeEvidence.label}
          style={{ maxWidth: "100%", borderRadius: 4 }}
        />
      </a>
    ) : (
      <a href={downloadUrl} target="_blank" rel="noopener noreferrer">
        <Icon name="file-lock-2" size={13} /> {activeEvidence.filename || activeEvidence.label}
      </a>
    );
  } else if (activeEvidence) {
    evidenceContent = activeEvidence.content;
  }

  const objective = !mission.knowledge_check_complete
    ? "Answer the Knowledge Check questions to unlock this booth's challenge."
    : mission.pending_review
    ? "Await field agent review."
    : "Complete the mission action to secure this node.";

  return (
    <section id="mission-panel" className="card">
      <div className="mission-header">
        <div>
          <p className="mission-id">
            <Icon name="hash" size={12} /> MISSION {missionCode}
          </p>
          <h2>{mission.title}</h2>
          {mission.tagline && <p className="mission-tagline">{mission.tagline}</p>}
        </div>
        <span className="meta-tag">
          <Icon name="unlock" size={12} /> ACTIVE
        </span>
      </div>

      <div className="mission-timeline">
        {data.timeline.map((t, i, arr) => (
          <span key={t.mission_id}>
            <div className={`mission-timeline-node ${t.status}`}>
              <span className={`status-dot ${t.status === "current" ? "" : "off"}`} />
              <span className="mission-timeline-label">{t.title}</span>
            </div>
            {i < arr.length - 1 && <div className="mission-timeline-connector" />}
          </span>
        ))}
      </div>

      <p>{mission.narrative}</p>

      <div className="ops-grid">
        <div className="ops-panel">
          <p className="ops-label">
            <Icon name="crosshair" size={14} /> Threat Level
          </p>
          <p className={`ops-value ${threat.tier}`}>{threat.label}</p>
        </div>
        <div className="ops-panel">
          <p className="ops-label">
            <Icon name="activity" size={14} /> Stage
          </p>
          <p className={`ops-value ${stage.tier}`}>{stage.label}</p>
        </div>
        <div className="ops-panel">
          <p className="ops-label">
            <Icon name="network" size={14} /> Progress
          </p>
          <p className="ops-value info">
            {nodesSecured} / {nodesTotal}
          </p>
        </div>
        <div className="ops-panel">
          <p className="ops-label">
            <Icon name="timer" size={14} /> {timer.label}
          </p>
          <p className={`ops-value ${timer.tier}`}>{timer.value}</p>
          {!timer.frozen && mission.time_limit && mission.started_at && (
            <div className="timer-bar">
              <div
                className={`timer-fill ${timer.tier === "crit" ? "red" : timer.tier === "warn" ? "amber" : ""}`}
                style={{ width: `${timer.pct}%` }}
              />
            </div>
          )}
        </div>
      </div>

      {mission.evidence_files.length > 0 && (
        <>
          <div className="tabs" role="tablist">
            {mission.evidence_files.map((e, i) => (
              <button
                key={e.id}
                type="button"
                className={`tab ${i === activeTab ? "active" : ""}`}
                role="tab"
                aria-selected={i === activeTab}
                onClick={() => setActiveTab(i)}
              >
                <Icon name="file-lock-2" size={12} /> {e.label}
              </button>
            ))}
          </div>
          <div className="evidence-content">{evidenceContent}</div>
        </>
      )}

      <div id="knowledge-check-stage">
        {mission.knowledge_questions.length > 0 && !mission.knowledge_check_complete && (
          <KnowledgeCheck questions={mission.knowledge_questions} onAnswered={onSubmitted} showMessage={showMessage} />
        )}
      </div>

      <div id="challenge-stage">
        {mission.challenge && mission.knowledge_check_complete && (
          <ChallengePanel
            key={mission.id}
            mission={mission}
            teamName={teamName}
            softLockMinAttempts={data.soft_lock_min_attempts}
            showMessage={showMessage}
            onSubmitted={onSubmitted}
          />
        )}
      </div>

      {message && !mission.pending_review && !mission.penalty_remaining && (
        <p className="narrative-message">{message}</p>
      )}

      <p className="objective">
        <Icon name="target" size={12} /> Current objective: {objective}
      </p>
    </section>
  );
}
