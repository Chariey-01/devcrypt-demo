# DevCrypt — System Guide

This is the implementation companion to the PRD: what actually got built, how the four
roles connect to each other, and every place this build deliberately diverges from (or adds
to) the PRD's literal wording. If you only read one doc to understand the running system,
read this one.

## 1. The four roles, and how they connect

Everyone hits the same Flask app on the same URL (`/`). What they see depends on how they
log in — there is no separate app per role.

```
                        ┌─────────────────────┐
                        │   /  (role picker)   │
                        └──────────┬───────────┘
                 ┌──────────────────┴───────────────────┐
                 ▼                                       ▼
      /auth/team-login (name+key)              /auth/login (email+password)
                 │                                       │
                 ▼                        ┌───────────────┼────────────────┐
        session["team_id"]                ▼               ▼                ▼
                 │                  role=booth_agent  role=security_  role=game_master
                 ▼                        │             officer            │
        /missions/play                    ▼               ▼                ▼
     (Player Portal — team's        /booth/select    /security/       /mod/
      own mission loop,             → /booth/queue   (issue clearance  (live team table,
      polls /missions/status              (PASS / RETRY /  stamps, +25 pts   start/pause/end,
      every 2s)                            HINT / OVERRIDE      each,        broadcast,
                                            on code subs)   audit only —     override, CSV
                                                             no gameplay     export)
                                                             gate)
```

**Teams never log in with email/password** — they get a team name + key card at
registration (`TeamRepository.set_key`, bcrypt-hashed, never stored in plaintext). Staff
(Booth Agent / Security Officer / Game Master) are rows in the `users` table with a `role`
column, authenticated via Flask-Login. One Flask-Login session, one `role` field, one
`roles_required(*roles)` decorator (`app/decorators.py`) gates every staff route — there's no
separate app or codebase per role, just different templates and permitted routes.

**The connective tissue between all four roles is the database**, specifically:

- `TeamMission` rows are where a team's in-progress work lives, and where Booth Agents /
  Game Master reach in to act on it (`PASS`/`RETRY`/`HINT`/`OVERRIDE` all mutate the same row
  a team's own `/missions/status` poll is reading).
- `ClearanceStamp` rows written by a Security Officer are audit-only — they award a small score
  bonus and show up on the GM dashboard / Leaderboard (`clearance` column), but do not gate any
  mission submission. (Earlier revisions of this system gated the final mission's submission on
  two stamps; that gate was removed since fragment possession is already server-verified proof
  of completion, and the gate had no precondition of its own — see git history around the
  Security Officer simplification for the reasoning.)
- `EventState` (singleton row) is written by the Game Master's Start/Pause/End/Broadcast
  controls and read by every Player Portal poll — this is how "Start Event" simultaneously
  unlocks all team portals without any direct communication between browsers.
- `EventLog` is an append-only audit trail every role writes to (mission pass/fail/override,
  hints, checkpoint stamps, broadcasts) and only the Game Master reads (team detail page).

## 2. The mission loop, end to end

1. Team logs in → lands on the first unresolved mission (`MissionService.current_mission_for`
   walks missions in `order_index` order, skipping anything already `passed`/`overridden`).
2. **Stage 0 — Evidence.** Tabs render `EvidenceFile` rows for the mission. No gating.
3. **Stage 1 — Threat Assessment.** Three `MCQ`s. Correct answers are free — no penalty for
   wrong ones (matches PRD section 14: MCQs don't block progression). Each correct answer
   reveals one cryptogram tile (`MCQOption.cipher_letter_index` → `MCQ.order_index`).
4. **Stage 2 — Mission Action** (`Challenge`), unlocked once all 3 MCQs are answered:
   - `type="flag"` or `type="mcq"` → auto-validated instantly, no human in the loop.
   - `type="code"` → always queued for a Booth Agent (`TeamMission.submission_text`); never
     auto-passes. This is the one stage where "employer interaction" (PRD's core
     differentiator) actually happens.
   - Wrong answers of any type: soft-lock kicks in — `TeamMission.penalty_until` (60s
     cooldown), `attempts` increments, integrity drops 5% from the 2nd attempt on. No team is
     ever hard-blocked (PRD ADR-05).
   - A hint (player-requested or Booth-Agent-triggered — same code path) costs 15 points and
     10% integrity, capped at 3 per team for the whole event (`Team.hints_used`), and reveals
     `Challenge.hint_text`.
5. On pass/override: `MissionService.complete_mission` awards bonuses (see §4), generates a
   `Fragment` (HMAC of team+mission, see §5), advances `Team.booth_current` to the next
   mission, and logs the action.
6. Mission 6 (RESTORE, `type="flag"`) is additionally gated on 2 `ClearanceStamp`s. Submitting
   `FLAG{RESTORE}` completes it — "finished" is computed on the fly (all 6 `TeamMission`s in
   `passed`/`overridden`), not a stored flag.

## 3. Schema additions beyond the PRD's section 13 overview

Section 13 of the PRD explicitly describes itself as an overview. Making the functional
requirements in sections 14/16/17/18 actually executable required a few things the overview
didn't spell out:

| Addition | Why |
|---|---|
| `Mission.cipher_word` | Section 15 requires each mission have a plaintext cipher word — no column existed for it. |
| `TeamMission.submission_text` | FR-06 requires the Booth Agent portal to display "the team's current submission" — has to live somewhere. |
| `TeamMission.penalty_until` | The soft-lock retry timer (section 14) needs a persisted deadline, not just an in-memory one (FR-11: no data loss on refresh). |
| `TeamMission.hint_used` | Drives the "no hint used" scoring bonus (section 16), which is per-mission, distinct from the event-wide hint cap. |
| `Team.hints_used` | The event-wide 3-hint budget (section 19) is per-team, not per-mission. |
| `EventState` (new table) | FR-10's Start/Pause/End/Broadcast controls need *some* persisted place to live. |

All six are additive — nothing in the original 14-table design was removed or renamed.

## 4. Scoring & integrity (`app/services/scoring_service.py`)

| Event | Score | Integrity |
|---|---|---|
| MCQ correct | +10 | — |
| Challenge pass | +20, +5 if no hint used, +5 if within `time_limit`, +10 more if all three MCQs correct + no hint + on time | — |
| Hint requested | −15 | −10% |
| Retry (2nd+ wrong attempt) | — | −5% |
| Mission Override | −30 | −20% |
| Clearance stamp issued | +25 | — |

`Team.integrity` is the live number shown on the leaderboard; `TeamMission.integrity_delta`
is the per-mission audit trail feeding it.

## 5. Cipher & Fragment engine (`app/services/cipher_service.py`)

- Caesar shift per mission is *derived*, not stored: `(order_index * 3 + 1) % 26`. Six
  missions, six distinct shifts, nothing to keep in sync.
- Fragment value = `HMAC-SHA256(EVENT_SALT, f"{team_id}:{mission_id}")`, formatted as hex
  pairs (`A9:1F` style) to match the PRD's example table. Per THREAT-04, this can't be
  precomputed by a participant without `EVENT_SALT`, which never leaves the server.
- The cryptogram board (`/cipher/board`, and embedded in `/missions/status`) returns both the
  masked/plaintext `display` string *and* a parallel `revealed` boolean array — the client
  needs the latter to animate/style newly-revealed tiles, since a plaintext letter and its
  Caesar-shifted counterpart both just look like "some uppercase letter."

## 6. Real-time push (Socket.IO), with polling as the guaranteed fallback

Earlier revisions of this doc described Socket.IO as initialized-but-unused, relying purely on
2-second polling. That's no longer accurate — Socket.IO push is active in production. The
design principle is **push-triggers-refresh, not push-carries-state**: every socket emit
(`app/sockets.py`) is a bare `{"type": "..."}` ping with no game data in the payload. The
browser responds by calling the *same* `refresh()` function its poll loop already calls. This
means there's exactly one rendering/serialization path (the REST endpoints), not two to keep in
sync, and a socket payload can never leak anything the REST endpoints already filter (hidden
test cases, `solution_code`, another team's fragment).

Every poll loop from the original design is **still there, unchanged**, as the fallback: if a
socket never connects or drops mid-session, the 2-second poll keeps everything
eventually-consistent regardless — exactly the guarantee the original NFR-05/ADR-03 reasoning
called for, just with an added low-latency path on top rather than instead of it.

This required an async-capable gunicorn worker (`-k gevent`, see §10/DEPLOYMENT.md), since sync
workers only support Socket.IO's HTTP long-polling fallback, never a true WebSocket upgrade.

## 6a. Emergency Mode & operational safety valves

Three Game Master tools exist specifically for live-event incident recovery, all audit-logged
(`app/blueprints/mod.py`):

- **Reset Mission** — clears a stuck `TeamMission`'s cooldown/attempts/pending-review state
  without force-passing it or wiping legitimate progress. For "a bug gave this team a bad
  60-second penalty" or "attempts got exhausted incorrectly," not for undoing a real result.
- **Force Pass + Fragment** (the pre-existing mission override) — force-completes a stuck
  mission, same code path as an auto/manual pass.
- **Set Score** — direct score correction on a `TeamMission`, propagated to the team total.

A fourth, event-wide switch lives in **Event Settings** (`/mod/event-settings`,
§8b): **disable automated grading**. If the grading sandbox misbehaves mid-event, this reroutes
every auto-graded submission into the existing manual-review queue instead of executing
submitted code — a kill switch, not a cosmetic toggle.

Structured logging (`logging.basicConfig`, wired in `app/__init__.py`) writes team/staff logins,
challenge submissions, grading outcomes, Socket.IO connects/disconnects, and every audited
GM/agent/officer action to stdout — visible directly in Railway's log viewer without a database
query mid-incident.

## 7. Challenge types — what's auto vs. human-reviewed

Per section 14's own challenge-type table, only `code` challenges need a human validator.
`mcq` and `flag` are auto-validated by design, not as a cut we made. The seeded 6 missions
exercise all three: DEPLOY/TOKENS/SCHEMA are `code` (booth agent review), PACKET/INJECT are
`mcq` (auto), RESTORE is `flag` (auto, final vault).

## 8. Agent-managed auto-graded challenges (new)

The `code` challenges above are the legacy path — always human-reviewed, per section 7. An
Agent (the same `booth_agent` role, no new role added) can now build a second kind of
challenge through `/agent/dashboard`: a problem statement, starter code, a private solution,
a scoring config (pass threshold, bonus points, retry limit), and a test suite of
visible/hidden cases. Saving that content sets `Challenge.grading_mode = "auto"` on the
mission, which is the one flag every downstream code path checks — nothing else about the
mission loop changes.

For a team, an `"auto"` mission replaces the free-text answer box with a code editor plus
**Run Visible Tests** (self-check against only the visible cases) and **Submit Solution**
(runs the full suite server-side via `GradingEngine`, in a sandboxed subprocess — no human
in the loop). A pass reuses the exact same `MissionService.complete_mission()` path as
today's flag/mcq auto-validation: fragment generated, cryptogram tile revealed, team
advanced to the next mission. Hidden test cases and `Challenge.solution_code` are never
sent to the browser at any point — see `SYSTEM_DESIGN.md` section 13 for the full design.

An Agent only ever sees and edits missions where `Mission.owner_agent_id` is their own user
id; the Game Master assigns that ownership from `/mod/` (Agents & Booths panel) and can also
generate team credentials + QR codes, add team members, and set a team's starting booth
from the same dashboard — but has no route that can edit a `Challenge`'s content.

**Mission lifecycle**: every `Mission` has a `status` — `draft` (default for newly-created
missions; invisible to players, fixes a real gap where a half-authored mission with no
challenge yet was previously already player-visible with a broken panel), `published`
(the default for every mission that existed before this field was added, so nothing already
live changed behavior), or `archived`. Player-facing queries, the leaderboard, and the GM
dashboard's "current mission" column all filter to `published` — a draft can never appear as a
team's current mission anywhere. The Agent Dashboard adds Publish/Unpublish/Archive actions,
**Duplicate** (deep-copies a mission's challenge/tests/hints/files into a fresh draft — a
starting point for a variant, not a finished publish-ready copy), an optional agent-declared
`difficulty` (easy/medium/hard, display-only), and a read-only **Preview as Player** tab that
simulates the player view without exposing `solution_code` or hidden-test detail.

## 7a. Moderator Activity Feed, Analytics, and Exports

**Activity Feed** (`/mod/activity`) — the same `EventLog` audit trail already described in §1,
surfaced globally (previously only queryable per-team on a team's detail page) and
Socket.IO-refreshed on the existing `mod_update` event. Individual code submissions and test
runs now write an `EventLog` row too (previously only the eventual mission pass/override was
logged) — the actor is `None` since a team isn't a `User` row; team identity and outcome are
carried in the log's metadata field instead.

**Analytics Dashboard** (`/mod/analytics`) — total submissions, pass/fail rate, average
completion time (`TeamMission.completed_at - started_at`, both already populated by the
existing mission-completion flow — no new tracking needed), hint usage, and per-challenge
pass-rate/most-failed-challenge (derived from real `CodeSubmission` attempts — a useful
empirical cross-check against a challenge's agent-declared `difficulty` label). Visualized with
the existing `.timer-bar` CSS and data tables — no charting library added.
`LeaderboardSnapshot` existed as a model since the original schema but was never written to;
it's now populated on every score-affecting event (mission completion, clearance stamp, score
override) via the same `notify_global("leaderboard_refresh")` signal those paths already fired,
rather than a new scheduler.

**Exports** — beyond the original team-summary CSV, `/mod/export/submissions.csv`,
`/mod/export/challenges.csv`, and `/mod/export/event-stats.csv` cover submission history,
per-challenge stats, and aggregate event statistics respectively.

## 8b. Event Settings

`/mod/event-settings` centralizes event name/description, the per-team hint budget (previously
hardcoded as `3` independently in three places — display in `/missions/status`, the actual
enforcement gate in the hint-request route, and the booth queue's display — all three now read
`EventState.hint_limit`), whether the public leaderboard is visible (staff dashboards are never
affected by this), and the automated-grading kill switch described in §6a. Total published-booth
count is shown read-only, derived from `Mission.query`, deliberately **not** a separately
editable number — a config value that could drift out of sync with the actual mission set would
just reintroduce the same class of bug fixed by deriving the "finished" threshold from the real
count instead of a hardcoded `6` (also fixed this pass, in `leaderboard.py` and `mod.py`, plus
the same hardcoded `/6` and `/2` denominators in two frontend templates).

## 9. Running the whole thing locally to see all roles interact

```bash
cd devcrypt
source .venv/bin/activate
pip install -r requirements.txt
python3 seed.py
python3 run.py
```

`flask run` will *not* work here — it never executes the `if __name__ == "__main__":` block
that calls `socketio.run()`, so it silently falls back to a dev server that can't hold a
WebSocket upgrade open. `python3 run.py` is the only local entrypoint that exercises the same
gevent/Socket.IO path as production.

Open browser tabs (or windows) at `http://localhost:5000`:

1. **Game Master** — `/auth/login` → `gm@devcrypt.local` / `changeme` → click **Start event**.
2. **Team** — `/auth/team-login` → `Alpha Squad` / `ALPHA01` → answer the 3 MCQs on
   Discovery Node, submit anything for the code challenge.
3. **Booth Agent** — `/auth/login` → `agent1@devcrypt.local` / `changeme` → select
   "Discovery Node — DEPLOY" → the team's submission appears in the queue → click **PASS**.
   Tab 2 reflects the fragment/cryptogram update instantly via Socket.IO (or within ~2s if the
   socket hasn't connected, via the poll fallback).
4. **Security Officer** — `/auth/login` → `officer@devcrypt.local` / `changeme` → issue a
   clearance stamp to Alpha Squad; confirm it shows up on the GM dashboard and leaderboard
   (audit/bonus only — it does not gate mission progress).

Watch the public leaderboard at `/leaderboard/` (no login) update live as all of this happens.
Try `/mod/analytics` and `/mod/activity` from the Game Master tab, and `/agent/dashboard`
(login as `agent1@devcrypt.local`) to see the challenge-authoring surface.

See `DEPLOYMENT.md` for local one-command setup details and the production (Railway) deployment
guide, `API.md` for the full route reference, and `SYSTEM_DESIGN.md` for the architectural
reasoning behind these decisions.
