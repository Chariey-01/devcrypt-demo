import { useEffect, useRef, useState } from "react";
import { Icon } from "../icons";
import { api } from "../api";
import type {
  FinalFlagRequirementsResponse,
  FinalFlagStatusResponse,
  FinalFlagSubmitResponse,
  FinalFlagVault,
  MissionStatus,
} from "../types";

// Ported from app/static/app.js's renderFinishedPanel(). The flag is never computed
// client-side and never sent until the server confirms every vault is actually passed and the
// player has correctly re-entered every fragment -- this component only orchestrates that
// existing server-side gate, exactly like the vanilla version did.
export function FinishedPanel({ data }: { data: MissionStatus }) {
  const [vaults, setVaults] = useState<FinalFlagVault[] | null>(null);
  const [flag, setFlag] = useState<string | null>(null);
  const [status, setStatus] = useState<"pending" | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Set<number>>(new Set());
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const statusCheckingRef = useRef(false);

  useEffect(() => {
    api<FinalFlagRequirementsResponse>("/missions/final-flag/requirements").then((res) => {
      if (res.ok && res.data.vaults) {
        setVaults(res.data.vaults);
      } else {
        setVaults([]);
        setFormError(res.data.error || "Unavailable.");
      }
    });
  }, []);

  useEffect(() => {
    if (status !== "pending" || statusCheckingRef.current) return;
    statusCheckingRef.current = true;
    const poll = () => {
      api<FinalFlagStatusResponse>("/missions/final-flag/status").then((res) => {
        statusCheckingRef.current = false;
        if (res.ok && res.data.status === "confirmed" && res.data.flag) {
          setFlag(res.data.flag);
        }
      });
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, [status]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!vaults) return;
    setSubmitting(true);
    try {
      const fragments: Record<number, string> = {};
      vaults.forEach((v) => {
        fragments[v.mission_id] = drafts[v.mission_id] || "";
      });
      const res = await api<FinalFlagSubmitResponse>("/missions/final-flag", {
        method: "POST",
        body: JSON.stringify({ fragments }),
      });
      if (res.ok) {
        setFormError(null);
        setFieldErrors(new Set());
        if (res.data.status === "confirmed" && res.data.flag) {
          setFlag(res.data.flag);
        } else {
          setStatus("pending");
        }
        setDrafts({});
      } else {
        setFormError(res.data.error || "Unlock failed.");
        setFieldErrors(new Set(res.data.incorrect_mission_ids || []));
      }
    } finally {
      setSubmitting(false);
    }
  }

  let unlockSection: React.ReactNode;
  if (flag) {
    unlockSection = (
      <p className="mono" style={{ fontSize: "1.1rem", color: "var(--green)", marginTop: "0.75rem" }}>
        <Icon name="unlock" size={16} /> {flag}
      </p>
    );
  } else if (status === "pending") {
    unlockSection = (
      <p className="hint-text">
        <Icon name="timer" size={13} /> Fragments verified — awaiting Game Master confirmation at
        the Command Centre…
      </p>
    );
  } else if (vaults === null) {
    unlockSection = (
      <p className="hint-text">
        <Icon name="timer" size={13} /> Checking vault status…
      </p>
    );
  } else if (vaults.length === 0) {
    unlockSection = (
      <p className="hint-text">
        <Icon name="lock-keyhole" size={13} /> {formError || "Final flag is not available."}
      </p>
    );
  } else {
    unlockSection = (
      <div style={{ marginTop: "0.75rem" }}>
        <p className="section-heading">
          <Icon name="key" size={14} /> Enter every recovered fragment to unlock the final flag
        </p>
        <p className="hint-text">
          <Icon name="eye" size={12} /> Check the Recovered Fragments rail above — type each one
          in exactly as shown.
        </p>
        <form onSubmit={submit}>
          {vaults.map((v) => (
            <div key={v.mission_id}>
              <label htmlFor={`fragment-${v.mission_id}`}>{v.title}</label>
              <input
                type="text"
                id={`fragment-${v.mission_id}`}
                className={`mono${fieldErrors.has(v.mission_id) ? " fragment-invalid" : ""}`}
                placeholder="e.g. AB:CD"
                autoComplete="off"
                value={drafts[v.mission_id] || ""}
                onChange={(e) => setDrafts((prev) => ({ ...prev, [v.mission_id]: e.target.value }))}
              />
            </div>
          ))}
          <button type="submit" disabled={submitting}>
            <Icon name="unlock" size={13} /> {submitting ? "Unlocking…" : "Unlock Final Flag"}
          </button>
        </form>
        {formError && (
          <p className="narrative-message" style={{ borderColor: "var(--red)", color: "var(--red)" }}>
            <Icon name="alert-triangle" size={13} /> {formError}
          </p>
        )}
      </div>
    );
  }

  return (
    <div id="finished-panel">
      <div className="card">
        <p className="meta-tag ok">
          <Icon name="shield-check" size={12} /> Core Restored
        </p>
        <h2>
          <Icon name="unlock" size={22} /> GRID CORE RESTORED
        </h2>
        <div className="ops-grid" style={{ marginTop: "0.75rem" }}>
          <div className="ops-panel">
            <p className="ops-label">
              <Icon name="gauge" size={14} /> Final Score
            </p>
            <p className="ops-value ok">{data.team.score}</p>
          </div>
          <div className="ops-panel">
            <p className="ops-label">
              <Icon name="signal" size={14} /> Integrity
            </p>
            <p className="ops-value info">{data.team.integrity}%</p>
          </div>
        </div>
        {unlockSection}
      </div>
    </div>
  );
}
