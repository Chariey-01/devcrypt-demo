# DevCrypt — API Reference

A route-by-route reference for the running application. This documents what's actually
implemented, not an aspirational API surface — generated from the current blueprints, not
written ahead of the code. For *why* these routes are shaped this way, see `SYSTEM_DESIGN.md`;
for the end-to-end role walkthroughs, see `SYSTEM.md`.

**Auth conventions used throughout:**
- `team session` — a team logged in via `/auth/team-login` (plain Flask session, `team_id` key).
- `role: X` — a staff user logged in via `/auth/login` (Flask-Login), gated by `@roles_required("X")`.
- No tag — publicly accessible, no login required.
- JSON routes accept/return `application/json` unless noted. Form routes (mostly under `/mod`,
  `/security`, `/booth`) accept standard HTML form POSTs and redirect on success.

---

## Auth (`/auth`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET/POST | `/auth/team-login` | — | Team name + key login. POST sets the team session. |
| GET/POST | `/auth/login` | — | Staff email + password login (any role). |
| POST | `/auth/logout` | — | Clears team session and/or Flask-Login session. |
| GET | `/auth/health` | — | Liveness probe. |

## Player (`/missions`) — team session required unless noted

| Method | Path | Description |
|---|---|---|
| GET | `/missions/play` | Renders the player dashboard shell. |
| GET | `/missions/status` | Full poll payload: team stats, cryptogram, fragments, current mission, `timeline` (all published missions' status for this team). Also Socket.IO-refreshed. |
| POST | `/missions/mcq/<id>/answer` | Submit an MCQ answer `{option_id}`. |
| POST | `/missions/challenge/submit` | Submit a challenge answer/code `{answer}` or `{code}`. Auto-graded challenges run the full test suite; routes to manual review if `auto_grading_disabled` is set. |
| POST | `/missions/hint` | Request a hint (gated by `EventState.hint_limit`, cost applied via `ScoringService`). |
| POST | `/missions/challenge/run-tests` | Run only visible test cases against submitted code — self-check, doesn't count as an attempt. 503 if `auto_grading_disabled`. |

## Cipher / Scoring (public read-only helpers)

| Method | Path | Description |
|---|---|---|
| GET | `/cipher/board` | Cryptogram board state for the logged-in team. |
| GET | `/scoring/breakdown` | Per-mission score/integrity breakdown for the logged-in team. |

## Leaderboard (`/leaderboard`) — public

| Method | Path | Description |
|---|---|---|
| GET | `/leaderboard/` | Public leaderboard page. |
| GET | `/leaderboard/data` | JSON rows, sorted by score/integrity/elapsed. Returns `{hidden: true, leaderboard: []}` when `EventState.leaderboard_public` is `False`. Includes `total_missions` (derived from published mission count, not hardcoded). |

## Booth Agent — legacy manual review (`/booth`) — role: booth_agent

| Method | Path | Description |
|---|---|---|
| GET/POST | `/booth/select` | Choose which published, `type="code"` mission to staff. |
| GET | `/booth/queue` | Review queue page. |
| GET | `/booth/queue/data` | Pending manual-review submissions for the selected mission. |
| GET | `/booth/alerts/data` | Recent alert feed for the booth/security toast UI. |
| POST | `/booth/submission/<team_mission_id>/pass` | Approve — completes the mission, awards fragment. |
| POST | `/booth/submission/<team_mission_id>/retry` | Reject — applies cooldown, increments attempts. |
| POST | `/booth/submission/<team_mission_id>/hint` | Release the configured hint. |
| POST | `/booth/submission/<team_mission_id>/override` | Force-pass with a heavy penalty, audit-logged. |

## Agent Dashboard — challenge authoring (`/agent`) — role: booth_agent

Every route below is scoped to missions where `owner_agent_id` matches the logged-in agent —
a mismatch 404s (not 403), so an agent can't tell another stakeholder's booth exists.

| Method | Path | Description |
|---|---|---|
| GET | `/agent/dashboard` | Renders the authoring SPA shell. |
| GET | `/agent/missions` | List this agent's own missions. |
| POST | `/agent/missions` | Create a new mission — starts as `status="draft"`. |
| GET | `/agent/missions/<id>` | Full mission detail (challenge, test cases, hints, assets — includes `solution_code`, owner-scoped only). |
| PUT | `/agent/missions/<id>` | Edit title/narrative/cipher_word/time_limit. |
| DELETE | `/agent/missions/<id>` | Delete a mission and everything under it. |
| POST | `/agent/missions/<id>/publish` | `draft`/`archived` → `published`. Requires a challenge to exist. |
| POST | `/agent/missions/<id>/unpublish` | `published` → `draft`. |
| POST | `/agent/missions/<id>/archive` | Any state → `archived`. |
| POST | `/agent/missions/<id>/duplicate` | Deep-copies challenge/tests/hints/assets into a new `status="draft"` mission. |
| PUT | `/agent/missions/<id>/challenge` | Create/update the challenge — prompt, starter code, solution, language, scoring config, `difficulty`. Always sets `grading_mode="auto"`. |
| POST | `/agent/missions/<id>/testcases` | Add a test case (`visibility`: visible/hidden). |
| PUT | `/agent/testcases/<id>` | Edit a test case. |
| DELETE | `/agent/testcases/<id>` | Remove a test case. |
| POST | `/agent/missions/<id>/testcases/reorder` | Reorder test cases `{order: [id, ...]}`. |
| GET | `/agent/missions/<id>/testcases/export` | JSON export of test cases. |
| POST | `/agent/missions/<id>/testcases/import` | Bulk-create test cases from a JSON array. |
| POST | `/agent/missions/<id>/hints` | Add a hint. |
| PUT | `/agent/hints/<id>` | Edit a hint. |
| DELETE | `/agent/hints/<id>` | Remove a hint. |
| POST | `/agent/missions/<id>/assets` | Add a supporting evidence file. |
| DELETE | `/agent/assets/<id>` | Remove an evidence file. |

## Security Officer (`/security`) — role: security_officer

Audit-only — does not gate mission progress (see `SYSTEM_DESIGN.md` §14).

| Method | Path | Description |
|---|---|---|
| GET | `/security/` | Checkpoint-stamping dashboard. |
| GET | `/security/data` | JSON: every team's stamped checkpoints. |
| POST | `/security/stamp` | Issue a clearance stamp `{team_id, checkpoint_id, notes}` — awards a score bonus, logs to `EventLog`, updates the leaderboard snapshot. |

## Game Master (`/mod`) — role: game_master

**Event lifecycle**

| Method | Path | Description |
|---|---|---|
| POST | `/mod/event/start` \| `/pause` \| `/end` | Event status transitions. |
| POST | `/mod/event/publish` \| `/archive` | Draft/archive the event itself (distinct from mission publish state). |
| POST | `/mod/broadcast` | Push a message to every connected client `{message}`. |
| GET/POST | `/mod/event-settings` | Event name/description, `hint_limit`, `leaderboard_public`, `auto_grading_disabled` (emergency kill switch). GET renders the form, POST saves. |

**Monitoring**

| Method | Path | Description |
|---|---|---|
| GET | `/mod/` | Dashboard shell. |
| GET | `/mod/data` | Live team table: score, integrity, current mission, status, `total_missions`. |
| GET | `/mod/team/<id>` | Per-team detail page: mission grid with Emergency Actions, Event Log. |
| GET | `/mod/activity` | Global activity feed — last 100 `EventLog` rows across every team/action. |
| GET | `/mod/submissions` | Last 50 `CodeSubmission` rows. |
| GET | `/mod/analytics` | Analytics dashboard page. |
| GET | `/mod/analytics/data` | Total submissions, pass/fail rate, avg completion time, hint usage, per-challenge stats, most-failed challenge. |

**Team & credential management**

| Method | Path | Description |
|---|---|---|
| POST | `/mod/team` | Create a team `{name}`. |
| POST | `/mod/team/<id>/member` | Add a roster member `{name, email}`. |
| DELETE | `/mod/team/<id>/member/<member_id>` | Remove a roster member. |
| POST | `/mod/team/<id>/starting-booth` | Set a team's starting mission `{mission_id}`. |
| POST | `/mod/credentials/generate` | Rotate a team key or staff password, optionally returns a QR data URI `{kind, name}`. |
| GET | `/mod/missions` | All missions regardless of status (GMs manage drafts too) — for assignment dropdowns. |
| GET | `/mod/agents` | Booth agents and their assigned missions. |
| POST | `/mod/mission/<id>/assign-agent` | Assign/unassign an agent to a mission `{agent_id}`. |

**Emergency Mode (see `SYSTEM.md` §6a)**

| Method | Path | Description |
|---|---|---|
| POST | `/mod/override/<team_mission_id>` | Force-pass a stuck mission, awards fragment. |
| POST | `/mod/override-score/<team_mission_id>` | Directly set a mission's score `{score}` (form field), propagates delta to team total. |
| POST | `/mod/reset-mission/<team_mission_id>` | Clear cooldown/attempts/pending-review without force-passing. 409 if already resolved. |

**Exports**

| Method | Path | Description |
|---|---|---|
| GET | `/mod/export.csv` | Team scores/leaderboard summary. |
| GET | `/mod/export/submissions.csv` | Every `CodeSubmission` row. |
| GET | `/mod/export/challenges.csv` | Per-challenge difficulty, grading mode, attempts, pass rate. |
| GET | `/mod/export/event-stats.csv` | Aggregate event metrics (same numbers as `/mod/analytics/data`). |

## Portals (`/`) — presentation only, no auth logic of their own

| Method | Path | Description |
|---|---|---|
| GET | `/team` | Branded front for team login. |
| GET | `/staff` | Branded front for staff login. |
| GET | `/moderator` | Branded front for Game Master login. |
| GET | `/healthz` | App-level health check — round-trips the database. |

---

## Socket.IO events

Not REST routes — documented separately since they're a different transport. See
`SYSTEM.md` §6 and `SYSTEM_DESIGN.md` §5 for the push-triggers-refresh design. Every emit is a
bare `{"type": "..."}` ping; the payload never carries game state.

| Event | Room | Fired by |
|---|---|---|
| `team_update` | `team-<id>` | Mission pass/override/score changes for that team. |
| `mod_update` | `mod` | Submissions, clearance stamps, score overrides, mission resets. |
| `event_update` | global | Event start/pause/end/broadcast, leaderboard refresh. |
