"""Read-only diagnostic for the two live bug reports: non-unique fragments across booths, and a
garbled final flag. Not part of the deployed app (like verify_missions.py, which it complements).

Only issues SELECT queries — makes no writes, safe to run directly against production.

For every stored Fragment row, recomputes what CipherService.generate_fragment() would produce
*right now*, using this process's live EVENT_SALT, and compares it against what's actually
stored. Since generate_fragment() is deterministic (HMAC-SHA256 keyed only by team_id, mission_id,
and EVENT_SALT — see app/services/cipher_service.py) and has never changed in the git history, a
mismatch here is the fingerprint of exactly one thing: the value was generated under a different
EVENT_SALT than the one currently configured (a rotated/changed secret, or a manually-inserted
row), never a code regression in the generator itself.

Separately flags any two fragments *for the same team* that share an identical value — under
correct HMAC-SHA256 output, two different mission_ids producing the same digest by chance is
cryptographically negligible, so a real duplicate here means generate_fragment() was actually
invoked twice with the same (team_id, mission_id) pair, which points at the mission_id resolution
logic (see MissionService.ordered_for_team / current_mission_for), not the hash function.

Usage:
    # Point DATABASE_URL and EVENT_SALT at whatever environment you want to inspect, then:
    python3 scripts/diagnose_fragments.py

    # Against Railway (env vars already injected):
    railway run python3 scripts/diagnose_fragments.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Fragment, Team
from app.services.cipher_service import CipherService

app = create_app()
cipher = CipherService()

with app.app_context():
    event_salt = app.config.get("EVENT_SALT")
    print(f"EVENT_SALT configured: {'yes' if event_salt else 'NO — missing/empty!'}")
    print(f"EVENT_SALT length: {len(event_salt) if event_salt else 0} chars\n")

    teams = Team.query.order_by(Team.name).all()
    if not teams:
        print("No Team rows exist in this database at all.")
        sys.exit(0)

    dupe_names = {}
    for t in teams:
        dupe_names.setdefault(t.name.strip().lower(), []).append(t.id)
    real_dupes = {name: ids for name, ids in dupe_names.items() if len(ids) > 1}
    if real_dupes:
        print("WARNING: duplicate team names found (different team_id, same name) — a login or")
        print("session bug that resolves to the wrong row would show up as unexplained fragment")
        print("mismatches even though generate_fragment() itself is correct:")
        for name, ids in real_dupes.items():
            print(f"  {name!r}: team_ids {ids}")
        print()

    total_fragments = 0
    total_mismatches = 0
    total_collisions = 0

    for team in teams:
        fragments = Fragment.query.filter_by(team_id=team.id).order_by(Fragment.mission_id).all()
        if not fragments:
            continue

        print(f"Team {team.name!r} (id={team.id}): {len(fragments)} fragment(s)")
        print(f"{'Mission':<9}{'Stored':<12}{'Expected now':<14}{'Match'}")

        seen_values = {}
        for f in fragments:
            total_fragments += 1
            expected = (
                cipher.generate_fragment(team.id, f.mission_id, event_salt)
                if event_salt
                else "(no salt)"
            )
            match = "OK" if f.cipher_value == expected else "MISMATCH"
            if match == "MISMATCH":
                total_mismatches += 1
            print(f"{f.mission_id:<9}{f.cipher_value:<12}{expected:<14}{match}")

            if f.cipher_value in seen_values:
                total_collisions += 1
                print(
                    f"  COLLISION: mission {f.mission_id} has the same stored value as "
                    f"mission {seen_values[f.cipher_value]} ({f.cipher_value!r})"
                )
            seen_values[f.cipher_value] = f.mission_id
        print()

    print("=" * 60)
    print(f"{total_fragments} fragment(s) checked across {len(teams)} team(s).")
    print(f"{total_mismatches} mismatch(es) vs. what today's EVENT_SALT would produce.")
    print(f"{total_collisions} same-team collision(s) (duplicate value across different missions).")
    if total_mismatches and not total_collisions:
        print(
            "\nAll stored values are internally unique but don't match today's EVENT_SALT — "
            "this is a salt mismatch (rotated secret, or a different salt was in effect when "
            "these were generated), not a fragment-generation bug."
        )
    if total_collisions:
        print(
            "\nGenuine collisions found — this means generate_fragment() was called more than "
            "once with the same (team_id, mission_id) pair. Check MissionService.complete_mission "
            "callers (booth pass/override, auto-grading pass, GM override) for a path that "
            "resolves the wrong mission_id for a given booth."
        )
    print("=" * 60)
