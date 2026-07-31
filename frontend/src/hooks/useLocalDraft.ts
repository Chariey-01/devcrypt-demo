// Ported from app/static/app.js's makeLocalStore()/draftStore/testResultsStore. A dropped
// connection or a page reload must never lose the player's work -- autosave is a convenience,
// not a correctness requirement: private browsing or a full quota should never break the
// actual submit flow, just silently skip persisting.
function makeLocalStore<T>(prefix: string, parse: (raw: string) => T, serialize: (value: T) => string) {
  const key = (teamName: string | null, missionId: number) => `${prefix}_${teamName || "unknown"}_${missionId}`;
  return {
    load(teamName: string | null, missionId: number, fallback: T): T {
      try {
        const saved = localStorage.getItem(key(teamName, missionId));
        return saved === null ? fallback : parse(saved);
      } catch {
        return fallback;
      }
    },
    save(teamName: string | null, missionId: number, value: T) {
      try {
        localStorage.setItem(key(teamName, missionId), serialize(value));
      } catch {
        // quota exceeded / private browsing -- ignored, matches app.js
      }
    },
    clear(teamName: string | null, missionId: number) {
      try {
        localStorage.removeItem(key(teamName, missionId));
      } catch {
        // ignored
      }
    },
  };
}

export const draftStore = makeLocalStore<string>(
  "devcrypt_code_draft",
  (raw) => raw,
  (value) => value
);

export const testResultsStore = makeLocalStore<unknown>(
  "devcrypt_test_results",
  (raw) => JSON.parse(raw),
  (value) => JSON.stringify(value)
);
