"""Seed the 6 named event teams with fixed credentials and staggered starting booths, so
moderators don't have to create them by hand before the event.

Idempotent and additive only: never touches any other team (e.g. teams created earlier for
testing/QA) and never re-creates or re-passwords a team that already exists by name -- re-running
this after the event started is safe, it just skips teams that are already there. Uses the
existing Team.starting_mission_id + mission_service.ordered_for_team() booth-rotation mechanism
(already built -- see app/services/mission_service.py) rather than any new progression logic:
each team's booth order is its assigned starting booth, then the remaining booths in order,
wrapping back to booth 1.

Usage:
    python3 scripts/seed_event_teams.py             # prints a plan, asks to confirm
    python3 scripts/seed_event_teams.py --yes        # skip the confirmation prompt
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Mission, Team

# (team name, login key/password, starting booth_id)
EVENT_TEAMS = [
    ("Team CIPHER", "Cipher2026!", 1),
    ("Team PHANTOM", "Phantom2026!", 2),
    ("Team VORTEX", "Vortex2026!", 3),
    ("Team NEXUS", "Nexus2026!", 4),
    ("Team SPECTER", "Specter2026!", 5),
    ("Team ZERO DAY", "ZeroDay2026!", 6),
]


def build_plan():
    """Returns (plan, skipped). plan is [(name, key, mission)] to create; skipped is
    [(name, reason)] for teams already present or whose booth is missing."""
    plan = []
    skipped = []
    for name, key, booth_id in EVENT_TEAMS:
        if Team.query.filter_by(name=name).first() is not None:
            skipped.append((name, "already exists -- left untouched"))
            continue
        mission = Mission.query.filter_by(booth_id=booth_id).first()
        if mission is None:
            skipped.append((name, f"no Mission with booth_id={booth_id} -- can't set a starting booth"))
            continue
        plan.append((name, key, mission))
    return plan, skipped


def apply_plan(plan):
    for name, key, mission in plan:
        team = Team(name=name, starting_mission_id=mission.id)
        team.set_key(key)
        db.session.add(team)
    db.session.commit()
    return len(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Apply without an interactive confirm prompt.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        plan, skipped = build_plan()

        if skipped:
            print(f"{len(skipped)} team(s) skipped:\n")
            for name, reason in skipped:
                print(f"  - {name}: {reason}")
            print()

        if not plan:
            print("Nothing to create -- all event teams already exist.")
            return

        print(f"{len(plan)} team(s) will be created:\n")
        for name, key, mission in plan:
            print(f"  {name}  key={key}  starting_booth=booth_id {mission.booth_id} ({mission.title})")
        print()

        if not args.yes:
            answer = input("Create these teams? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted -- no changes made.")
                return

        created = apply_plan(plan)
        print(f"Created {created} team(s).")


if __name__ == "__main__":
    main()
