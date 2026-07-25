# DevCrypt — MVP Readiness (Final Stability Audit)

Audit date: 2026-07-25 (T-2 days to Career Fair). Scope: verify the release candidate cannot
fail during the live event. No new features were added; the only change made was removing one
piece of dead code (see below).

## Go / No-Go

**GO**, with one manual action item before doors open (see "Outstanding Issues").

## Architecture Summary

Flask app (`app/`) with blueprints per concern (`auth`, `missions`, `scoring`, `cipher`,
`leaderboard`, `mod`, `security`, `portals`, `agent`), SQLAlchemy models, Flask-Migrate/Alembic
for schema, Flask-SocketIO for live leaderboard/notification pushes, Monaco editor for the
coding challenge UI. Deployed on Railway; local dev uses SQLite, production uses Postgres.

Two independent, non-overlapping cipher systems (confirmed in code, not just intent):

- **Booth Knowledge Check cipher** (`Mission.cipher_word`, `app/services/cipher_service.py`) —
  a per-booth thematic word (e.g. `LAUNCH`, `ACCESS`, `ROUTE`) revealed letter-by-letter as a
  team answers Knowledge Check questions correctly. Cosmetic/flavor only.
- **Final flag fragments** (`Fragment.cipher_value`, `app/services/final_flag_service.py`) —
  earned by passing a booth's coding challenge (≥80%), collected across all 6 booths, and
  reconstructed server-side via HMAC-keyed keystream (`EVENT_SALT` + sorted mission ids) only
  after a Game Master confirms at the Command Center. This is the only path that produces the
  real event flag.

## Verification Performed

1. **Final flag correctness (highest priority item)** — `tests/test_final_flag.py`, 19/19
   passing, including an end-to-end test that runs the full fragment→validate→confirm→decrypt
   pipeline **10 independent times** and asserts the output is exactly `M3T4V3R$3` every time,
   plus adversarial cases: one wrong/missing/swapped/reused/single-character-tampered fragment,
   and a rotated-salt scenario that must fail closed (500, no flag leaked) rather than return
   mojibake. All pass.
2. **Full regression suite** — 172/172 tests passing across 28 test files covering auth, team
   management, agent challenge authoring, submission review, auto-grading, grading/scoring
   concurrency, attempt caps, soft lock, mission timers, knowledge check, booth distribution,
   event settings, exports, analytics, sockets, security officer flow, and emergency mod
   actions. Zero failures, zero skips.
3. **Route smoke test** — every parameter-free registered route (30+ across all 9 blueprints)
   hit via the Flask test client: 200/302/401 as expected for public/auth-gated/protected
   endpoints respectively, zero 500s or unhandled exceptions.
4. **Code hygiene sweep** — no `TODO`/`FIXME`/`HACK`/`XXX`/`NotImplemented`, no stray
   `print()`, no `debug=True`, no bare `raise Exception`, no unfinished stub functions. The only
   `except: pass` blocks are legitimate optional-dependency fallbacks (gevent's `psycogreen`,
   `qrcode`) — not swallowed real errors.
5. **Dead code sweep** — no unused HTML templates, no unused custom JS/CSS, no duplicate route
   definitions. Found and removed one dead module: `app/repositories/mission_repo.py`
   (`MissionRepository`, zero callers anywhere — mission creation goes through the Agent
   Dashboard flow, not this class). Full suite re-run and confirmed green after removal.
6. **Migrations** — single linear Alembic history, one head (`d7e1a4c9f3b2`), no branching, no
   drift.
7. **Knowledge bank** — all 6 booths have exactly 15 well-formed questions (4 options, valid
   correct-index), no duplicate keys within a booth.
8. **Git** — working tree clean, `main` in sync with `origin/main`, dead-code removal committed
   and pushed (`73c3f0b`).
9. **Local dev hygiene** — fixed a `python-dotenv` parse warning on every app boot caused by a
   stray `/* */`-style comment block in `.env` (dotenv only understands `#` comments). `.env`
   is gitignored and Railway doesn't read it, so this had zero production impact — fixed for a
   clean local console during event-day troubleshooting.

## Known Limitations (unchanged, by design — not defects)

- Knowledge Check content is hardcoded in `app/knowledge_bank.py` rather than authored through
  the Agent Dashboard CRUD UI, per an explicit product decision to reduce admin-surface risk
  this close to the event. Documented in the module docstring, including how to switch back
  later.
- Final flag reconstruction requires explicit Game Master confirmation at the Command Center
  before it's ever handed to a team — this is intentional, not a bug.

## Outstanding Issues (action required before the event)

- **`FINAL_FLAG_CIPHERTEXT` / `FINAL_FLAG_MISSION_IDS` on Railway** — could not be verified
  from this environment (no Railway CLI session available here). The application code and
  tests prove the reconstruction is correct and deterministic *given correct config*, but
  someone with Railway dashboard access must confirm those two env vars are actually set on
  the production service before the event, using `scripts/derive_final_flag.py` against
  production's real `EVENT_SALT` and the real booth Mission ids (`scripts/verify_missions.py`
  lists them). Until set, `/missions/final-flag/requirements` correctly 404s rather than
  fabricating a flag — so the failure mode is "feature unavailable," not "wrong flag," but it
  must be set for the event to be completable at all.

## Rollback Plan

- `main` at `73c3f0b` is the current release candidate; the prior commit `8f5f384` is the
  last known-good state before today's dead-code removal (a pure deletion with no behavior
  change — low risk either way).
- Railway deploys from `main` — reverting is `git revert 73c3f0b` (or redeploying the prior
  commit from the Railway dashboard) followed by a push.
- Database: no schema changes were made in this audit, so no migration rollback is needed for
  today's changes specifically. General rollback for any future migration is
  `flask db downgrade`.

## Deployment Checklist

- [x] All tests passing (172/172)
- [x] No debug code / unfinished stubs in the codebase
- [x] No dead code discovered has been removed
- [x] Git tree clean, `main` pushed to `origin/main`
- [x] Migrations at a single, unbranched head
- [ ] Confirm `FINAL_FLAG_CIPHERTEXT` / `FINAL_FLAG_MISSION_IDS` set correctly on Railway
      production (manual — see Outstanding Issues)
- [ ] Live click-through of the full event flow in a browser against the deployed Railway URL
      (login → knowledge check → Monaco → submit → grading → fragment → leaderboard → booth
      routing → final flag) — recommended once as final confirmation, since this audit
      verified the pipeline through automated tests and a server-side route smoke test, not a
      real browser session.

## Test Summary

- 172/172 automated tests passing, 0 failures, 0 skips (~160s runtime)
- 30+ routes smoke-tested live via test client, 0 server errors
