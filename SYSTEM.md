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
                                            on code subs)   unlocks final    override, CSV
                                                             vault)          export)
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
- `ClearanceStamp` rows written by a Security Officer are read by the Player Portal (mission
  6 checks `len(team.clearance_stamps) >= 2` before allowing a submission) and by the
  Leaderboard (`clearance` column).
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

## 6. Why polling instead of WebSockets

`flask-socketio` is initialized (`app/extensions.py`) but unused for this pass. Two reasons,
both already in the PRD itself:

1. **NFR-05** requires the demo to run with zero internet access. The Socket.IO *protocol*
   needs a matching client-side JS library, which normally comes from a CDN or an npm build
   step — neither is compatible with "one laptop, no internet, no build step" (ADR-03).
2. The PRD's own tech-stack table pre-approves this: *"Degrades gracefully to polling if
   WebSocket is unavailable."*

Every "live" surface (player cryptogram/timer, booth queue, GM dashboard, public leaderboard)
polls its JSON endpoint every 2 seconds via plain `fetch()` — comfortably inside NFR-01's
2-second leaderboard-update requirement, with no CDN dependency. If a future phase adds real
WebSockets, the server-side `flask-socketio` wiring is already there to build on.

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

## 9. Running the whole thing locally to see all four roles interact

```bash
cd devcrypt
source .venv/bin/activate
pip install -r requirements.txt
python3 seed.py
flask --app run.py run --host=0.0.0.0 --port=5000
```

Open four browser tabs (or windows) at `http://localhost:5000`:

1. **Game Master** — `/auth/login` → `gm@devcrypt.local` / `changeme` → click **Start event**.
2. **Team** — `/auth/team-login` → `Alpha Squad` / `ALPHA01` → answer the 3 MCQs on
   Discovery Node, submit anything for the code challenge.
3. **Booth Agent** — `/auth/login` → `agent1@devcrypt.local` / `changeme` → select
   "Discovery Node — DEPLOY" → the team's submission appears in the queue → click **PASS**.
   Tab 2 reflects the fragment/cryptogram update within ~2 seconds.
5. **Security Officer** — `/auth/login` → `officer@devcrypt.local` / `changeme` → issue both
   clearance stamps to Alpha Squad once they reach mission 6, so the final vault unlocks.

Watch the public leaderboard at `/leaderboard/` (no login) update live as all of this happens.

See `DEPLOYMENT.md` for local one-command setup details and the production (Render/Railway)
deployment guide.
