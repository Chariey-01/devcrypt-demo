"""One-off, idempotent data fix for the 6 seeded booths' sponsor branding -- not part of the
deployed app (like verify_missions.py). Corrects title/narrative text (e.g. the old "Zuberi
Interactive" -> "Zuberi") and backfills the new Mission.tagline column.

Safe to run repeatedly against production. Touches ONLY Mission.title/narrative/tagline, matched
by the stable booth_id (never by title, since title text is exactly what's being corrected).
Never calls drop_all/delete/create_all, never touches Team/TeamMission/Fragment/EvidenceFile or
any other table. Running it twice is a no-op the second time -- every row will already match.

Requires the `tagline` column to already exist (run scripts/deploy_db_setup.py first if this is
a fresh deploy of the migration that adds it).

Usage:
    # Point DATABASE_URL at whatever database you want to fix, then:
    python3 scripts/fix_sponsor_branding.py            # prints a before/after diff, asks to confirm
    python3 scripts/fix_sponsor_branding.py --yes       # skip the confirmation prompt

    # Against Railway: copy DATABASE_URL from the Railway dashboard's Postgres service (or run
    # this from a shell where it's already exported the way deploy_db_setup.py expects).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Mission

# Keyed by booth_id (stable), not title -- title text is exactly what this script corrects.
# Kept in sync with scripts/seed.py's MISSIONS list.
CORRECT_BRANDING = {
    1: {
        "title": "Elewa — MVP Launch Pipeline",
        "tagline": "Building digital products and engineering talent.",
        "narrative": (
            "Elewa is walking a startup client through the final stage of the Elewa Way — "
            "shipping their MVP. GhostRoute-7 tampered with the launch checklist service: it "
            "needs to report exactly how many feature flags are actually ready to ship."
        ),
    },
    2: {
        "title": "Workforce Africa — Access Roster Audit",
        "tagline": "Pan-African HR, EOR and workforce management platform.",
        "narrative": (
            "Workforce Africa manages employee access for client companies across 40+ African "
            "markets. GhostRoute-7 duplicated entries in an access roster — every duplicated "
            "employee ID is a account that could grant someone access twice over."
        ),
    },
    3: {
        "title": "Unispot — Application Routing Desk",
        "tagline": "Routing student applications to universities abroad.",
        "narrative": (
            "Unispot routes student applications to partner universities abroad. GhostRoute-7 "
            "disrupted the processing-time tracker the advising team uses to set expectations "
            "with applicants — it needs to report the average turnaround, in whole days."
        ),
    },
    4: {
        "title": "Close the Gap — Secure Wipe Audit",
        "tagline": "Circular-economy IT refurbishment and secure e-waste disposal.",
        "narrative": (
            "Close the Gap refurbishes donated IT equipment at its Circular Economy Hub in "
            "Mombasa — every device must be securely wiped before it's redeployed. GhostRoute-7 "
            "corrupted the wipe-status tracker for an incoming batch of devices."
        ),
    },
    5: {
        "title": "Zuberi — BodaLands Leaderboard",
        "tagline": "African game studio building mobile games rooted in local culture.",
        "narrative": (
            "Zuberi builds BodaLands, a mobile game rooted in Nairobi's motorcycle taxi "
            "culture. GhostRoute-7 knocked out the leaderboard service — it needs to recover "
            "the top score from a batch of submitted match results."
        ),
    },
    6: {
        "title": "TBM Limited — Grid Core Restoration",
        "tagline": "Cybersecurity, cloud and enterprise IT services, IBM business partner.",
        "narrative": (
            "All five partner nodes are secured. TBM Limited — the event's cybersecurity and "
            "enterprise infrastructure partner — has been brought in for the final restoration. "
            "GhostRoute-7's last foothold is the Grid Core itself: every recovered fragment's "
            "integrity value must be summed before the core will restore."
        ),
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="Apply without an interactive confirm prompt."
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        changes = []
        for booth_id, correct in CORRECT_BRANDING.items():
            mission = Mission.query.filter_by(booth_id=booth_id).first()
            if mission is None:
                print(f"booth_id={booth_id}: no Mission row found — skipping.")
                continue
            row_changes = {}
            for field, correct_value in correct.items():
                current_value = getattr(mission, field)
                if current_value != correct_value:
                    row_changes[field] = (current_value, correct_value)
            if row_changes:
                changes.append((mission, row_changes))

        if not changes:
            print("Every booth already matches the correct branding — nothing to do.")
            return

        print(f"{len(changes)} Mission row(s) need updating:\n")
        for mission, row_changes in changes:
            print(f"booth_id={mission.booth_id} (Mission id={mission.id}):")
            for field, (before, after) in row_changes.items():
                print(f"  {field}:\n    before: {before!r}\n    after:  {after!r}")
            print()

        if not args.yes:
            answer = input("Apply these changes? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted — no changes made.")
                return

        for mission, row_changes in changes:
            for field, (_, after) in row_changes.items():
                setattr(mission, field, after)
        db.session.commit()
        print(f"Updated {len(changes)} Mission row(s).")


if __name__ == "__main__":
    main()
