import { Icon } from "../icons";
import type { MissionStatus } from "../types";

export function ScoreBreakdown({ data }: { data: MissionStatus }) {
  const team = data.team;
  const boothScore =
    data.mission && typeof data.mission.booth_score === "number" ? data.mission.booth_score : null;
  const tiles: Array<{ icon: string; label: string; value: number | string }> = [
    { icon: "gauge", label: "Total Score", value: team.score },
    { icon: "target", label: "Booth Score", value: boothScore === null ? "—" : boothScore },
    { icon: "scan-line", label: "MCQ Score", value: team.mcq_points },
    { icon: "cpu", label: "Coding Score", value: team.coding_points },
    { icon: "hash", label: "Cipher Score", value: team.cipher_points },
    { icon: "key", label: "Hint Deductions", value: team.hint_points },
    { icon: "timer", label: "Time Bonus", value: team.time_bonus_points },
    { icon: "trophy", label: "Leaderboard Score", value: team.score },
  ];
  return (
    <>
      <p className="section-heading">
        <Icon name="gauge" size={14} /> Score Breakdown
      </p>
      <section className="card score-breakdown" id="score-breakdown">
        {tiles.map((t) => (
          <div className="score-tile" key={t.label}>
            <span className="score-tile-label">
              <Icon name={t.icon} size={12} /> {t.label}
            </span>
            <span className="score-tile-value">{t.value}</span>
          </div>
        ))}
      </section>
    </>
  );
}
