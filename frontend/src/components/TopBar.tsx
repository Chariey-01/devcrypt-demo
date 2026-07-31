import { Icon } from "../icons";
import type { TeamSummary } from "../types";

function csrfToken(): string {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ?? "";
}

export function TopBar({ team }: { team: TeamSummary | null }) {
  return (
    <header className="topbar">
      <span className="brand-mini">
        <Icon name="terminal" size={16} /> DevCrypt
      </span>
      <span className="pill">
        <Icon name="users" size={13} /> {team?.name ?? "—"}
      </span>
      <span className="pill">
        <Icon name="gauge" size={13} /> Score {team?.score ?? 0}
      </span>
      <span className="pill">
        <Icon name="signal" size={13} /> Integrity {team?.integrity ?? 100}%
      </span>
      <span className="pill">
        <Icon name="key" size={13} /> Hint penalty {team?.hint_points ?? 0}
      </span>
      <form method="post" action="/auth/logout" className="inline-form">
        <input type="hidden" name="csrf_token" value={csrfToken()} />
        <button className="ghost" type="submit">
          <Icon name="unlock" size={13} /> Terminate Session
        </button>
      </form>
    </header>
  );
}
