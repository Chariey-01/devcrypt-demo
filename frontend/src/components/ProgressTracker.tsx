import { Icon } from "../icons";
import { computeTimerDisplay } from "../lib/timer";
import type { MissionStatus } from "../types";

export function ProgressTracker({ data }: { data: MissionStatus }) {
  if (data.finished) {
    return (
      <>
        <p className="section-heading">
          <Icon name="crosshair" size={14} /> Booth Progress
        </p>
        <section className="ops-grid" id="progress-tracker" />
      </>
    );
  }

  const mission = data.mission;
  const remaining = Math.max(0, (data.booths_total || 0) - (data.booths_completed || 0));
  const timer = computeTimerDisplay(mission);
  const boothsTotal = data.booths_total || 1;
  const boothsPct = Math.round(((data.booths_completed || 0) / boothsTotal) * 100);
  const fragmentsCount = (data.fragments || []).length;
  const fragmentsPct = Math.round((fragmentsCount / boothsTotal) * 100);

  return (
    <>
      <p className="section-heading">
        <Icon name="crosshair" size={14} /> Booth Progress
      </p>
      <section className="ops-grid" id="progress-tracker">
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="crosshair" size={14} /> Current Booth
        </p>
        <p className="ops-value info">{mission ? mission.title : "—"}</p>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="chevron-right" size={14} /> Next Booth
        </p>
        <p className="ops-value">{data.next_mission ? data.next_mission.title : "Final booth"}</p>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="check" size={14} /> Booths Completed
        </p>
        <p className="ops-value ok">
          {data.booths_completed} / {data.booths_total}
        </p>
        <div className="mini-progress">
          <div className="mini-progress-fill" style={{ width: `${boothsPct}%` }} />
        </div>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="radar" size={14} /> Booths Remaining
        </p>
        <p className="ops-value">{remaining}</p>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="file-lock-2" size={14} /> Fragments Collected
        </p>
        <p className="ops-value info">
          {fragmentsCount} / {data.booths_total}
        </p>
        <div className="mini-progress">
          <div className="mini-progress-fill accent-2" style={{ width: `${fragmentsPct}%` }} />
        </div>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="gauge" size={14} /> Total Score
        </p>
        <p className="ops-value ok">{data.team.score}</p>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="key" size={14} /> Hints Remaining — This Booth
        </p>
        <p className="ops-value">{mission && mission.challenge ? mission.challenge.hints_available : "—"}</p>
      </div>
      <div className="ops-panel">
        <p className="ops-label">
          <Icon name="timer" size={14} /> This Booth — Time Left
        </p>
        <p className={`ops-value ${timer.tier}`}>{timer.value}</p>
      </div>
      </section>
    </>
  );
}
