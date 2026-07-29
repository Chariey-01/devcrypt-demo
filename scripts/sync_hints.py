"""Idempotently sync BOOTH_HINTS (below) into the database as real Hint rows, one per booth.

Every booth currently only has a single legacy Challenge.hint_text string, which
_available_hint_texts() (app/blueprints/missions.py) falls back to as a single-hint list only
when no real Hint rows exist. Combined with ScoringService.MAX_HINTS_PER_BOOTH, that meant only
1 hint was ever actually available per booth, not the 3 required for today's event. This script
adds 3 real Hint rows per booth (Agent-authored hints take precedence over hint_text, so the
legacy field is left alone -- harmless, just unused once real Hint rows exist).

Safe to run repeatedly: for each booth, replaces that booth's entire Hint set with whatever is
currently in BOOTH_HINTS below. Touches ONLY Hint rows. Never touches Team/TeamMission/
CodeSubmission/Fragment/Challenge.prompt/starter_code/test_code or any other table -- a team
mid-event who already took a hint keeps that fact (TeamMission.hints_taken is untouched), they'll
just see this booth's new hint text on their next hint request instead of the old one.

Usage:
    python3 scripts/sync_hints.py             # prints a summary, asks to confirm
    python3 scripts/sync_hints.py --yes        # skip the confirmation prompt
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Hint, Mission

# booth_id -> ordered list of 3 hint texts (progressively more specific).
BOOTH_HINTS = {
    1: [
        "Duplicate tasks should invalidate the workflow -- track which task IDs you've already seen.",
        "Compare the current task against the expected next task carefully, not just against the previous one.",
        "Think about what an empty workflow should return, and what the final return statement is actually checking.",
    ],
    2: [
        "Check each of the three rules independently for every record -- an employee can be flagged by more than one rule.",
        "Normalize bank accounts (strip spaces, lowercase) before comparing them across different employees.",
        "A repeated row for the same employee sharing its own account shouldn't, by itself, trigger the shared-account rule.",
    ],
    3: [
        "Normalize both names the same way (lowercase, trim, collapse repeated spaces) before comparing them.",
        "Check for invalid scores before computing the average -- an invalid score list should never reach the average comparison.",
        "The issue codes must come back in the exact order they're checked in the spec, not the order they logically happened.",
    ],
    4: [
        "Split the input line on spaces to get one entry per device.",
        "Count how many entries equal the string \"1\" -- not the integer 1.",
        "The count itself is the whole answer -- print just that number, nothing else.",
    ],
    5: [
        "A single checkpoint is already a valid sequence of length 1.",
        "Consider what should happen when the list contains only one element.",
        "Watch your initial values for `longest` and `current` -- they should reflect that one checkpoint alone is a valid run.",
    ],
    6: [
        "Track a running consecutive-failure counter per IP address.",
        "A successful login for an IP should reset that IP's counter back to zero.",
        "You only need 5+ consecutive failures for the SAME IP -- failures from different IPs never combine.",
    ],
}


def sync_hints(quiet=False):
    """Pure sync logic, callable from inside an existing app context. Returns
    (booths_synced, hints_created)."""
    plan = []
    for booth_id, texts in BOOTH_HINTS.items():
        mission = Mission.query.filter_by(booth_id=booth_id).first()
        if mission is None or mission.challenge is None:
            if not quiet:
                print(f"booth_id={booth_id}: no Mission/Challenge row found -- skipping.")
            continue
        plan.append((mission.challenge, texts))

    total_created = 0
    for challenge, texts in plan:
        for old_hint in list(challenge.hints):
            db.session.delete(old_hint)
        db.session.flush()
        for order_index, text in enumerate(texts):
            db.session.add(Hint(challenge_id=challenge.id, order_index=order_index, text=text))
            total_created += 1

    db.session.commit()
    return len(plan), total_created


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Apply without an interactive confirm prompt.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        preview = []
        for booth_id, texts in BOOTH_HINTS.items():
            mission = Mission.query.filter_by(booth_id=booth_id).first()
            if mission is None or mission.challenge is None:
                print(f"booth_id={booth_id}: no Mission/Challenge row found -- skipping.")
                continue
            preview.append((mission, len(mission.challenge.hints), len(texts)))

        if not preview:
            print("No matching booths found -- nothing to do.")
            return

        print(f"{len(preview)} booth(s) will have their hints replaced:\n")
        for mission, existing_count, new_count in preview:
            print(f"  booth_id={mission.booth_id} ({mission.title}): {existing_count} existing hint(s) -> {new_count} new")
        print()

        if not args.yes:
            answer = input("Apply these changes? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted -- no changes made.")
                return

        booths_synced, total_created = sync_hints()
        print(f"Synced {total_created} hint(s) across {booths_synced} booth(s).")


if __name__ == "__main__":
    main()
