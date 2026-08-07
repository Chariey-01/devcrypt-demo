// This bundle is hosted standalone on Vercel (see vercel.json) and calls the Flask API on
// Railway cross-origin -- credentials: "include" plus a CORS-allowed origin (app/__init__.py's
// CORS(app, resources={...})) carries the session cookie set at Flask login, but there's no
// Flask-rendered <meta name="csrf-token"> tag here the way a same-origin page would have (that
// only exists because base.html renders it server-side). The token is instead fetched once from
// GET /auth/csrf-token (app/blueprints/auth.py) -- Flask-WTF's own documented pattern for this
// exact case -- and cached for the life of the page load.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface ApiResult<T> {
  ok: boolean;
  status: number;
  data: T;
  networkError?: boolean;
}

let cachedCsrfToken: string | null = null;
let csrfTokenPromise: Promise<string | null> | null = null;

async function csrfHeader(): Promise<Record<string, string>> {
  if (cachedCsrfToken) return { "X-CSRFToken": cachedCsrfToken };
  // Coalesce concurrent first-load requests onto one in-flight fetch instead of each racing
  // its own call to /auth/csrf-token.
  csrfTokenPromise ??= fetch(`${API_BASE}/auth/csrf-token`, { credentials: "include" })
    .then((res) => (res.ok ? (res.json() as Promise<{ csrfToken?: string }>) : null))
    .then((data) => data?.csrfToken ?? null)
    .catch(() => null);
  cachedCsrfToken = await csrfTokenPromise;
  return cachedCsrfToken ? { "X-CSRFToken": cachedCsrfToken } : {};
}

let consecutiveNetworkFailures = 0;
let onConnectionChange: ((down: boolean) => void) | null = null;

export function setConnectionListener(listener: (down: boolean) => void) {
  onConnectionChange = listener;
}

export async function api<T = unknown>(url: string, options: RequestInit = {}): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${url}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(await csrfHeader()) },
      ...options,
    });
  } catch {
    consecutiveNetworkFailures += 1;
    if (consecutiveNetworkFailures === 1) onConnectionChange?.(true);
    return { ok: false, status: 0, data: {} as T, networkError: true };
  }
  const wasDown = consecutiveNetworkFailures > 0;
  consecutiveNetworkFailures = 0;
  if (wasDown) onConnectionChange?.(false);

  let data: T = {} as T;
  try {
    data = (await res.json()) as T;
  } catch {
    data = {} as T;
  }
  // Same asymmetry as before: a dead/expired team session sends the team back to the
  // Flask-hosted login page (this bundle only ever runs on the player page, so no PAGE check
  // is needed here). Absolute because that page no longer lives on this origin.
  if (res.status === 401) {
    window.location.href = `${API_BASE}/auth/team-login`;
  }
  return { ok: res.ok, status: res.status, data };
}
