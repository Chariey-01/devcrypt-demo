# DevCrypt — MVP Readiness (Final Stability Audit)

Audit date: 2026-07-25 (T-2 days to Career Fair). Two audit passes:

- **Pass 1** (static + automated-test audit): code hygiene sweep, dead-code removal, migration
  check, route smoke test via the Flask test client. Everything looked green.
- **Pass 2** (this pass — live end-to-end verification): actually ran the app locally and drove
  every role through a real browser (Playwright) and real HTTP requests against a live server,
  per the instruction not to trust passing tests as proof the game flow works. **This pass found
  and fixed a showstopper bug that Pass 1's automated tests did not catch** (see below) — it
  would have blocked every team at every booth during the live event.

## Go / No-Go

**GO**, with one manual action item before doors open (see "Outstanding Issues" — confirming
Railway's `FINAL_FLAG_CIPHERTEXT`/`FINAL_FLAG_MISSION_IDS`, which cannot be checked from this
sandboxed environment).

## The critical bug this pass found

**`POST /missions/challenge/run-tests` and `POST /missions/challenge/submit` gated on the
wrong denominator.** Both compared `len(team_mission.knowledge_answers)` against
`len(mission.knowledge_questions)` — the booth's **full question pool** (15, per
`app/knowledge_bank.py`) — instead of the 5-question subset actually assigned to that team
(`assign_knowledge_subset`). Every real booth ships 15 questions with 5 assigned per team, so
`5 < 15` was always true: **a team that correctly answered all 5 of their assigned Knowledge
Check questions could never run tests or submit a solution, at any booth, ever.** The game
would have hard-stopped at booth 1 for every team on event day.

Why the existing 172-test suite didn't catch it: the tests exercising `run-tests`/`submit`
gating always used a 1-question pool (`_add_question`), and the tests using a realistic
15-question pool (`_add_n_questions(..., 15)`) only checked subset-assignment/reveal logic —
never both conditions together. Caught only by actually clicking "Run Visible Tests" in a real
browser against the real seeded data and getting rejected with
`"Complete the Knowledge Check before running tests."` after having answered every assigned
question correctly.

**Fix**: both routes now call `mission_service.assign_knowledge_subset(team_mission, mission)`
and compare against that, matching the pattern the `/missions/status` endpoint already used
correctly. **Regression test added**: `test_run_tests_and_submit_unlock_after_completing_the_assigned_subset_from_a_larger_pool`
in `tests/test_knowledge_check.py`, which specifically builds a 15-question pool, answers only
the assigned 5, and asserts both routes return 200. Verified live afterward: full team flow
(knowledge check → Monaco → Run Visible Tests → Submit → fragment → next-booth notification)
completed successfully in a real browser against the real seeded data.

## Architecture Summary

Flask app (`app/`) with blueprints per concern (`auth`, `missions`, `scoring`, `cipher`,
`leaderboard`, `mod`, `security`, `portals`, `agent`), SQLAlchemy models, Flask-Migrate/Alembic
for schema, Flask-SocketIO (gevent) for live pushes, Monaco editor (vendored on disk, no CDN)
for the coding challenge UI. Deployed on Railway; local dev uses SQLite, production uses
Postgres.

Two independent, non-overlapping cipher systems (confirmed in code AND live in the browser):

- **Booth Knowledge Check cipher** (`Mission.cipher_word`) — a per-booth thematic word (e.g.
  `LAUNCH`, `ACCESS`, `ROUTE`) revealed letter-by-letter as a team answers Knowledge Check
  questions correctly; sponsor branding/tagline rendered directly under the booth title on the
  same card. Cosmetic/flavor only — confirmed via DOM inspection that unrevealed letters are
  plain `class="tile"` decoy characters and revealed ones are `class="tile revealed"`, exactly
  matching the number of correct answers.
- **Final flag fragments** (`Fragment.cipher_value`, `app/services/final_flag_service.py`) —
  earned by passing a booth's coding challenge (≥80%), collected across all 6 booths, and
  reconstructed server-side via HMAC-keyed keystream (`EVENT_SALT` + sorted mission ids) only
  after a Game Master confirms at the Command Center.

## Verification Performed (Pass 2 — live, with evidence)

All of the following were exercised against a real running instance (`python3 run.py`), not
just read as code or asserted in a unit test.

1. **Team flow, full loop, real browser (Playwright/Chromium):** team login → booth assignment
   → 5-question Knowledge Check (answers looked up from `app/knowledge_bank.py` and clicked for
   real) → cipher letters revealed exactly on correct answers → coding challenge auto-unlocked,
   no refresh → Monaco editor confirmed present (`.monaco-editor` DOM element, real line
   numbers, syntax highlighting visible in screenshots) with **zero** plain `<textarea>`
   standing in for it → typed a real solution → **draft survived a full page reload**
   byte-for-byte (verified via `monaco.editor.getModels()[0].getValue()`) → **Run Visible
   Tests** executed only the visible case and showed per-case diagnostics
   (`1/1 passed — input: on off on on — expected: 3 — got: 3`) → **Submit Solution** ran the
   full hidden suite, scored it, awarded a fragment (`NODE SECURED. FRAGMENT ACQUIRED. (5/5
   tests, 100%)`), froze the booth, and **an automatic "Next booth" notification banner
   appeared and the UI advanced to booth 2 with a fresh Knowledge Check — all with zero manual
   refresh.**
2. **Wrong-answer / no-retry, direct HTTP:** a wrong Knowledge Check answer returns
   `{"correct": false, "message": "INCORRECT — NO CLUE REVEALED."}`, no score change, and no
   cipher letters flip to `revealed`. Re-submitting the *correct* answer to the same question
   afterward returns `{"already_answered": true, "correct": false, ...}` — the original wrong
   answer is locked in; there is no retry path.
3. **Scoring thresholds, direct HTTP:** a solution passing 4/7 tests (57%) is rejected
   (`correct: false`), awards proportional score (not zero, not full) toward the team total, and
   awards **no fragment**. A cooldown penalty (`429 NODE ON COOLDOWN`) engages after a failed
   submission before another attempt is allowed — an explicit anti-farming/anti-duplicate-points
   mechanism, on top of the concurrency-safety already covered by
   `tests/test_scoring_concurrency.py` and `tests/test_grading_concurrency.py` (both pass).
4. **Agent Dashboard authoring + live sync, direct HTTP:** a **newly GM-created** Booth Agent
   (`agent3@devcrypt.local` — not one of the two static seeded agents) logged in and could see
   **only** their assigned booth (permission scoping confirmed — 1 mission visible, not 6).
   That agent updated the mission narrative, challenge prompt, starter code, added a visible
   test case, a hidden test case, a hint, a text-based evidence file, and a binary (PDF)
   evidence file, then published. A **different team**, given a plain `GET
   /missions/status` immediately afterward with no agent-side action to "sync" anything, saw
   every one of those changes — title, narrative, prompt, starter code, evidence files — with
   zero refresh and zero manual sync step. The Agent Dashboard is confirmed the single source
   of truth.
5. **Game Master flows, direct HTTP:** publish event (`draft → not_started`), start/"Initialize
   Mission" (`→ running`), pause (`→ paused`), resume (`→ running`), end (`→ ended`) all work.
   Creating a brand-new dynamic Booth Agent via `/mod/credentials/generate` works (proving
   "Static Agent 1 and Agent 2 are not acceptable" is satisfied — the GM can mint new agents).
   Reassigning a booth to a different agent works. Disabling an agent immediately blocks their
   *next* login (401, correct error) — confirmed the disabled agent cannot authenticate; a
   follow-up check on an already-open session (not exercised live this pass, but covered by
   `tests/test_booth_agent_management.py`) is documented in `docs/SYSTEM.md` as re-checked on
   every request via `roles_required`. Re-enabling restores access. Leaderboard, Analytics, and
   all 4 CSV export endpoints (`export.csv`, `export/submissions.csv`, `export/challenges.csv`,
   `export/event-stats.csv`) return 200 with sane content.
6. **Final flag — 100+ reconstructions, per the instruction to prove it, not assume it:**
   - **100/100** pure-crypto reconstructions (fresh random `EVENT_SALT` each run, matching a
     fresh event's real conditions) produced exactly `M3T4V3R$3`, zero mismatches.
   - **25/25** *full real HTTP pipeline* runs — actual `/missions/final-flag` fragment
     submission → `pending` → a separate Game Master session hitting
     `/mod/final-flag/<team_id>/confirm` → `/missions/final-flag` again — produced exactly
     `M3T4V3R$3`, zero mismatches, zero variation.
   - Combined with the 19 targeted `tests/test_final_flag.py` tests (adversarial cases: wrong/
     missing/swapped/reused/tampered fragments, rotated-salt fails closed), the final flag path
     has now been exercised well over 140 times across this audit with 100% consistency.
7. **Local WebSocket handshake bug found and fixed:** local `.env` had `ALLOWED_ORIGIN` set to
   the production Railway URL **with a leading space** (`" https://web-production..."`),
   which fails Socket.IO's origin check and breaks the WebSocket handshake for local testing
   (400 on every socket connect). This file is gitignored and Railway doesn't read it, so
   **production was not directly affected by this specific file** — but the same class of typo
   (a stray leading/trailing space when pasting the URL into Railway's dashboard) would break
   real-time push in production the same way, and is now an explicit item on the Railway
   checklist below. Fixed locally by leaving `ALLOWED_ORIGIN` unset (matches the documented
   "leave unset for local demos" guidance already in the file).
8. **Documentation accuracy:** found and fixed a stale claim in `docs/SYSTEM.md` (the doc
   `README.md` explicitly names as the current, verified source of truth) — it still described
   "2–3 questions" per booth, predating the hardcoded 15-question-pool/5-assigned-per-team
   system. Corrected, and the corrected text documents the exact bug found in item 6.

## Verification Performed (Pass 1 — static + automated)

1. Full regression suite: 172 tests passing across 28 files before this pass; after this pass's
   fix and one new regression test, 173 passing (see below).
2. Route smoke test: every parameter-free route across all 9 blueprints returns 200/302/401 as
   expected, zero 500s.
3. Code hygiene: no TODO/FIXME/HACK/debug prints/stub code.
4. Dead code: removed `app/repositories/mission_repo.py` (`MissionRepository`, zero callers).
5. Migrations: single linear Alembic history, one head, no drift.
6. Knowledge bank: all 6 booths have exactly 15 well-formed questions, no duplicate keys.
7. Local dev hygiene: fixed a `python-dotenv` parse warning from a stray `/* */` comment block
   in `.env` (gitignored, zero production impact).

## Known Limitations (by design — not defects)

- Knowledge Check content is hardcoded in `app/knowledge_bank.py` rather than authored through
  the Agent Dashboard CRUD UI, per an explicit product decision to reduce admin-surface risk
  this close to the event. The Agent Dashboard's Knowledge Check CRUD still exists and works
  (confirmed by `tests/test_knowledge_check.py`'s agent-authoring tests) — it's just not the
  path used for this event's real content.
- Final flag reconstruction requires explicit Game Master confirmation at the Command Center
  before it's ever handed to a team — intentional, not a bug.

## Outstanding Issues (action required before the event)

1. **Railway environment variables — cannot be verified from this sandbox** (no Railway CLI
   session available here). See the full checklist below; the two most consequential are
   `FINAL_FLAG_CIPHERTEXT`/`FINAL_FLAG_MISSION_IDS` (unset = the final-flag feature 404s rather
   than fabricating a flag, so failure mode is safe but the event can't be completed) and
   `ALLOWED_ORIGIN` (a copy-paste whitespace typo — the exact bug found locally this pass —
   would silently degrade real-time push to polling; the app still works, just less snappy).
2. **Live click-through against the actual deployed Railway URL** — this pass verified the full
   flow exhaustively against a local instance with production-equivalent code and config shape
   (gevent, same Procfile command). A final one-time click-through against the real
   `https://web-production-188c4.up.railway.app` URL, after confirming the env vars above, is
   still worth doing once as final confirmation before doors open.

## Railway Checklist

Environment variables actually read by the app (`app/config.py` — this is the complete list;
nothing else affects runtime behavior):

| Variable | Required? | What happens if missing/wrong |
|---|---|---|
| `SECRET_KEY` | Yes | Falls back to a hardcoded demo value (`devcrypt-demo-secret`) — session signing would use a publicly-known key. Must be a real random value in production. |
| `DATABASE_URL` | Yes | Falls back to a local SQLite file. On Railway's ephemeral filesystem this means **all data is lost on every redeploy/restart** — this is the single most important variable to confirm. Must point at the provisioned Postgres instance. Accepts either `postgres://` or `postgresql://` (the app normalizes it). |
| `EVENT_SALT` | Yes | Falls back to a hardcoded demo value. Must be a real random secret, and — critically — **must be the exact same value used when `scripts/derive_final_flag.py` was run** to produce `FINAL_FLAG_CIPHERTEXT`, or the final flag decrypts to garbage and fails closed (by design, per `test_final_flag_wrong_salt_fails_closed_instead_of_returning_garbage`). |
| `FINAL_FLAG_CIPHERTEXT` | Yes, for the final flag to work at all | Unset = `/missions/final-flag/*` routes 404 (safe failure, but the event can't be completed). |
| `FINAL_FLAG_MISSION_IDS` | Yes, paired with above | Must be the exact comma-separated Mission ids passed to `derive_final_flag.py`. A mismatch here or a later mission re-creation would change the derived key — this is why `scripts/verify_missions.py` should be re-run against production data right before generating these, not assumed from local ids. |
| `ALLOWED_ORIGIN` | Recommended | Unset falls back to `"*"` (Socket.IO accepts any origin — works, but is the permissive default, not defense-in-depth). If set, **must exactly match the deployed URL with no leading/trailing whitespace** — this exact typo class broke the local WebSocket handshake during this audit. Copy it fresh from the Railway-assigned domain, don't retype it. |

Also confirm on Railway:

- [ ] Health check path configured and passing (`/auth/health`, `/cipher/health`,
      `/scoring/health`, `/mod/health` all return `{"status": "ok"}` with no auth required).
- [ ] Procfile's worker command is actually what's deployed: `gunicorn -k gevent -w 1 -b
      0.0.0.0:$PORT --timeout 60 --graceful-timeout 60 "app:create_app()"` — the single-worker,
      gevent-based command is required for WebSocket support; a default/auto-detected Railway
      start command would silently break real-time push.
- [ ] Migrations applied: `flask db upgrade` (or Railway's release-phase equivalent) has run
      against the production database and `flask db current` matches head `d7e1a4c9f3b2`.
- [ ] `git status` on the deploy source is clean and `main` is what's actually deployed — confirm
      the Railway deployment's commit SHA matches `origin/main`'s latest.
- [ ] Socket.IO actually connects against the live URL (open the browser console on the deployed
      site, confirm no `400`/handshake errors — the same failure mode found locally this pass).

## Render Migration Checklist (informational only — do not migrate yet)

Per instruction: Railway must be fully stable first; this is a reference checklist for *when*
that migration happens, not a plan being executed now.

- [ ] Provision a managed Postgres instance on Render (or continue using the existing Railway
      Postgres and just point `DATABASE_URL` at it during a transition window).
- [ ] Set the same 6 environment variables listed above on the Render service.
- [ ] Render's start command needs the same gevent/single-worker shape as the Procfile —
      confirm Render's service settings use the `gunicorn -k gevent -w 1 ...` command, not a
      default Python buildpack command (which would break WebSockets identically to a
      misconfigured Railway deploy).
- [ ] Run `flask db upgrade` against the Render-side database before any traffic is routed to
      it.
- [ ] `EVENT_SALT` and `FINAL_FLAG_CIPHERTEXT`/`FINAL_FLAG_MISSION_IDS` must be copied byte-for-
      byte from Railway's values (or re-derived together) — a mismatch here breaks the final
      flag exactly as described above.
- [ ] Health checks (`/auth/health` etc.) configured on Render's dashboard before cutover.
- [ ] DNS/URL cutover plan and rollback path (keep the Railway deployment running in parallel
      until Render is confirmed stable under real traffic).
- [ ] Update `ALLOWED_ORIGIN` to the new Render URL once cutover happens.

## Rollback Plan

- Railway deploys from `main` — reverting any commit is `git revert <sha>` followed by a push,
  or redeploying a prior commit from the Railway dashboard.
- Database: no destructive schema changes were made in this audit; general migration rollback
  is `flask db downgrade`.

## Deployment Checklist

- [x] All tests passing (173/173 after this pass's fix + new regression test)
- [x] Critical showstopper bug found via live verification and fixed (Knowledge Check gating)
- [x] No debug code / unfinished stubs in the codebase
- [x] Dead code removed
- [x] Git tree clean, `main` pushed to `origin/main`
- [x] Migrations at a single, unbranched head
- [x] Full team/agent/GM role flows verified live (browser + real HTTP), not just unit-tested
- [x] Final flag proven deterministic across 125+ combined reconstructions this audit
- [ ] Confirm Railway environment variables per the checklist above (manual — no CLI access
      from this environment)
- [ ] One final live click-through against the actual deployed Railway URL

## Test Summary

- 173/173 automated tests passing, 0 failures, 0 skips (includes 1 new regression test added
  this pass for the Knowledge Check gating bug)
- Full team/Monaco/scoring/booth-routing loop verified in a real headless-Chromium browser
  session against a live local server, with screenshots as evidence
- Agent authoring → team-side live sync verified via direct HTTP against a live local server
- Game Master event-lifecycle, agent management, leaderboard, analytics, and exports verified
  via direct HTTP against a live local server
- Final flag: 100/100 pure-crypto + 25/25 full-HTTP-pipeline reconstructions, 0 mismatches
