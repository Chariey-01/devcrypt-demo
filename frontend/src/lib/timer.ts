import type { Mission } from "../types";

export interface TimerDisplay {
  value: string;
  tier: "ok" | "warn" | "crit";
  pct: number;
  frozen: boolean;
  label: string;
}

export function fmtClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

// Ported 1:1 from app/static/app.js's computeTimerDisplay(). Once a mission has a frozen
// submission (grading_status set), the timer must show that frozen instant forever -- never
// fall back to live Date.now() math, or a slow review/grading pass would silently inflate the
// team's recorded time. Only compute a live countdown when nothing has been submitted yet.
export function computeTimerDisplay(mission: Mission | null | undefined): TimerDisplay {
  if (!mission) return { value: "—", tier: "ok", pct: 100, frozen: false, label: "Timer" };

  if (mission.submission_status) {
    const overtime = mission.submission_status === "overtime";
    const value = mission.time_limit
      ? overtime
        ? `+${fmtClock(-(mission.time_remaining_frozen ?? 0))} OVER`
        : fmtClock(mission.time_remaining_frozen ?? 0)
      : fmtClock(mission.elapsed_seconds ?? 0);
    const label = mission.grading_status === "pending_review" ? "Awaiting Review" : "Submitted";
    return {
      value: `Submitted — ${value}`,
      tier: overtime ? "crit" : "ok",
      pct: overtime ? 0 : 100,
      frozen: true,
      label,
    };
  }

  if (!mission.time_limit || !mission.started_at) {
    return { value: "—", tier: "ok", pct: 100, frozen: false, label: "Timer" };
  }
  const startedAt = new Date(mission.started_at + "Z").getTime();
  const remaining = mission.time_limit - (Date.now() - startedAt) / 1000;
  const pct = Math.max(0, Math.min(100, (remaining / mission.time_limit) * 100));
  const tier: TimerDisplay["tier"] = pct < 15 ? "crit" : pct < 50 ? "warn" : "ok";
  const value = remaining > 0 ? fmtClock(remaining) : "OVERDUE";
  return { value, tier, pct, frozen: false, label: "Timer" };
}
