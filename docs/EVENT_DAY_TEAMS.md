# DevCrypt — Event-Day Team Setup

## Team credentials

| Unit | Team Name | Login Key |
|------|-----------|-----------|
| Unit 01 | Team CIPHER | `Cipher2026!` |
| Unit 02 | Team PHANTOM | `Phantom2026!` |
| Unit 03 | Team VORTEX | `Vortex2026!` |
| Unit 04 | Team NEXUS | `Nexus2026!` |
| Unit 05 | Team SPECTER | `Specter2026!` |
| Unit 06 | Team ZERO DAY | `ZeroDay2026!` |

Teams log in at `/auth/team-login` with their exact team name and login key above.

These 6 teams are seeded automatically by `scripts/seed_event_teams.py` — safe to re-run at any
time (idempotent: skips any team that already exists, never touches any other team, e.g. teams
created earlier for testing/QA).

## Sponsor booth mapping

| Booth | Sponsor |
|-------|---------|
| 1 | Elewa |
| 2 | Workforce Africa |
| 3 | Unispot |
| 4 | Close the Gap |
| 5 | Zuberi |
| 6 | TBM Limited |

## Booth rotation

Every team starts at a different booth to avoid congestion, then follows the full 6-booth
sequence in order, wrapping back to booth 1 after booth 6. This uses the app's existing
starting-booth + rotation mechanism (`Team.starting_mission_id`, already built — see
`app/services/mission_service.py`'s `ordered_for_team()`), not new logic.

| Team | Full path |
|------|-----------|
| Team CIPHER | 1 → 2 → 3 → 4 → 5 → 6 |
| Team PHANTOM | 2 → 3 → 4 → 5 → 6 → 1 |
| Team VORTEX | 3 → 4 → 5 → 6 → 1 → 2 |
| Team NEXUS | 4 → 5 → 6 → 1 → 2 → 3 |
| Team SPECTER | 5 → 6 → 1 → 2 → 3 → 4 |
| Team ZERO DAY | 6 → 1 → 2 → 3 → 4 → 5 |

A team cannot skip ahead or repeat a booth out of order — the backend always computes "current
booth" as the first not-yet-resolved (passed/overridden/soft-locked) booth in that team's own
rotation, so this is enforced server-side, not just by what the UI happens to show.

## Event flow (for moderators)

1. Team logs in with their team name + key above.
2. Dashboard opens, showing their assigned starting booth immediately.
3. Team completes that booth's Knowledge Check (5 MCQs) — the coding challenge stays locked
   until all 5 are answered.
4. Monaco code editor unlocks. Team can use "Run Tests" freely, then "Submit" when ready.
5. On a passing submission: score updates, a cipher fragment is awarded, and the dashboard
   automatically shows the next booth in that team's rotation.
6. Repeat until all 6 booths are complete.
7. Once every fragment is collected, the Final Vault unlocks for that team to enter the
   decoded final flag.

## Where to make changes if something needs fixing before doors open

- **Reset a team's progress**: Game Master Dashboard → Team Management → Reset Team.
- **Adjust a team's starting booth**: Game Master Dashboard → Team Management → Starting Booth
  dropdown (per team), or the "Distribute Booths" button there for a fresh round-robin across
  all teams at once.
- **Re-sync challenge content** (problem statement, starter code, hidden tests) for any booth:
  `python3 scripts/import_challenge_content.py --yes` (reads from `content/challenges/`).
- **Re-sync hints** for any booth: `python3 scripts/sync_hints.py --yes`.
- **Re-sync the Knowledge Check bank**: `python3 scripts/sync_knowledge_bank.py --yes`.

None of the above touch Team/TeamMission/Fragment/score data for any team — they only replace
booth *content* (challenge text, test cases, hints, MCQ bank), so they're safe to re-run mid-event
if a booth's content needs a last-minute fix, though doing so while a team is actively mid-attempt
on that specific booth changes what they're solving out from under them (see the warning in each
script's own docstring).
