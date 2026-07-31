// Mirrors app/static/app.js's api()/csrfHeader() exactly -- same CSRF header source (the
// server-rendered <meta name="csrf-token"> in base.html, unchanged), same credentials handling
// (a plain session cookie, no token/JWT scheme exists anywhere in this app), same 401 ->
// team-login redirect. Kept as a small standalone module rather than importing app.js's
// version so this bundle has no runtime dependency on the vanilla-JS file at all.

export interface ApiResult<T> {
  ok: boolean;
  status: number;
  data: T;
  networkError?: boolean;
}

function csrfHeader(): Record<string, string> {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const content = meta?.getAttribute("content");
  return content ? { "X-CSRFToken": content } : {};
}

let consecutiveNetworkFailures = 0;
let onConnectionChange: ((down: boolean) => void) | null = null;

export function setConnectionListener(listener: (down: boolean) => void) {
  onConnectionChange = listener;
}

export async function api<T = unknown>(url: string, options: RequestInit = {}): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(url, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
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
  // Same asymmetry as app.js: a dead/expired team session redirects straight to team-login --
  // this bundle only ever runs on the player page, so no PAGE check is needed here.
  if (res.status === 401) {
    window.location.href = "/auth/team-login";
  }
  return { ok: res.ok, status: res.status, data };
}
