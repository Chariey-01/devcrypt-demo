"""Read-only report of every Mission row and its Challenge configuration — not part of the
deployed app (like verify_deployment.py). Answers, precisely, "how many vaults actually exist
and are they set up correctly?" without guessing from the outside via HTTP.

Only issues SELECT queries — makes no writes, safe to run directly against production.

Usage:
    # Point DATABASE_URL at whatever database you want to inspect, then:
    python3 scripts/verify_missions.py

    # Against Railway: copy DATABASE_URL from the Railway dashboard's Postgres service
    # (or run this from a shell where it's already exported the way deploy_db_setup.py expects).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Mission

app = create_app()
with app.app_context():
    missions = Mission.query.order_by(Mission.order_index).all()

    if not missions:
        print("No Mission rows exist in this database at all — zero vaults, published or not.")
        sys.exit(0)

    print(f"{len(missions)} Mission row(s) found:\n")
    print(f"{'#':<4}{'Booth':<7}{'Status':<11}{'Type':<7}{'Grading':<16}{'Tests':<7}{'Title'}")
    print("-" * 80)

    status_counts = {}
    for m in missions:
        status_counts[m.status] = status_counts.get(m.status, 0) + 1
        c = m.challenge
        if c is None:
            grading = "NO CHALLENGE"
            ctype = "-"
            test_count = "-"
        else:
            grading = c.grading_mode or "(none)"
            ctype = c.type or "(none)"
            test_count = str(len(c.test_cases)) if grading == "auto" else "-"
        print(
            f"{m.id:<4}{m.booth_id:<7}{m.status:<11}{ctype:<7}{grading:<16}{test_count:<7}{m.title}"
        )

    print("\nStatus breakdown:", ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    published = status_counts.get("published", 0)
    print(f"\nPlayers currently see {published} published vault(s).")
    if published < len(missions):
        print(
            f"{len(missions) - published} mission(s) exist but are NOT published — invisible to "
            "players until a Booth Agent publishes them from the Agent Dashboard."
        )

    no_challenge = [m for m in missions if m.challenge is None]
    if no_challenge:
        print(
            f"\n{len(no_challenge)} mission(s) have NO Challenge row at all yet: "
            + ", ".join(m.title for m in no_challenge)
        )

    manual_code = [
        m
        for m in missions
        if m.challenge and m.type == "code" and m.challenge.grading_mode != "auto"
    ]
    if manual_code:
        print(
            f'\n{len(manual_code)} mission(s) are type="code" but grading_mode is NOT "auto" '
            "(so they show the plain answer box, not the code editor): "
            + ", ".join(m.title for m in manual_code)
        )
