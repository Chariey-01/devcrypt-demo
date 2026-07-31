import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { MissionStatus } from "../types";

const POLL_MS = 2000;

// Ported from app/static/app.js's refresh()/setInterval(refresh, 2000) poll loop. Note what's
// deliberately *not* ported here: the original manually skips rebuilding #mission-panel's
// innerHTML while the player has an input focused, because a raw innerHTML replacement always
// destroys (and loses focus on) the element being typed into. React doesn't have that problem
// for controlled inputs -- reconciliation updates existing DOM nodes in place as long as the
// component tree shape is stable, so focus is preserved for free. Monaco is the one exception
// (an imperative widget React doesn't own internally) and is handled separately in
// MonacoCodeEditor via an uncontrolled defaultValue + ref, keyed by mission id.
export function useMissionStatus() {
  const [data, setData] = useState<MissionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    const res = await api<MissionStatus>("/missions/status");
    if (res.networkError) {
      // Server unreachable -- the shared connection banner already covers this. Never navigate
      // away: the poll loop keeps retrying, and everything on screen (code drafts, test
      // results) is already safe in localStorage/the DB, not lost by staying put.
      return;
    }
    if (!res.data || !res.data.team) {
      // A genuine "you're not logged in" response. api()'s 401 handling already redirects in
      // the common case; this is the same defensive backstop app.js has for an edge case where
      // the body comes back empty without a 401 status.
      window.location.href = "/auth/team-login";
      return;
    }
    setData(res.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [refresh]);

  return { data, loading, refresh };
}
