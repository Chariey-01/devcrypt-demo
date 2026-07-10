"""Generate cryptographically random team keys and staff passwords for a real event.

Run this AFTER seed.py (which sets up missions/evidence/MCQs and wipes the whole
database). This script only touches Team and User rows — it's safe to re-run any
time to add teams/staff or rotate everyone's credentials, without touching mission
content.

Secrets are only ever shown here, once, in plaintext. Only their bcrypt hashes are
stored in the database — there is no way to recover a lost key/password, only to
regenerate a new one by re-running this script for that team/account.

Usage:
    python3 generate_credentials.py \
        --teams "Alpha Squad" "Bravo Squad" "Charlie Squad" \
        --game-masters gm@devcrypt.local \
        --booth-agents agent1@devcrypt.local agent2@devcrypt.local \
        --security-officers officer@devcrypt.local \
        --out credentials.csv
"""

import argparse
import csv
import secrets

from app import create_app
from app.extensions import db
from app.models import Team, User

# Excludes 0/O and 1/I/L so a team reading a printed key card aloud can't confuse them.
TEAM_KEY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_team_key(length=8):
    return "".join(secrets.choice(TEAM_KEY_ALPHABET) for _ in range(length))


def generate_password():
    return secrets.token_urlsafe(18)


def upsert_teams(names):
    rows = []
    for name in names:
        key = generate_team_key()
        team = Team.query.filter_by(name=name).first()
        if team is None:
            team = Team(name=name)
            db.session.add(team)
        team.set_key(key)
        rows.append({"role": "team", "name": name, "login": name, "secret": key})
    return rows


def upsert_staff(role, emails):
    rows = []
    for email in emails:
        password = generate_password()
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, role=role)
            db.session.add(user)
        user.set_password(password)
        rows.append({"role": role, "name": email, "login": email, "secret": password})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teams", nargs="+", default=["Alpha Squad", "Bravo Squad"])
    parser.add_argument("--game-masters", nargs="+", default=["gm@devcrypt.local"])
    parser.add_argument("--booth-agents", nargs="+", default=["agent1@devcrypt.local", "agent2@devcrypt.local"])
    parser.add_argument("--security-officers", nargs="+", default=["officer@devcrypt.local"])
    parser.add_argument("--out", default="credentials.csv")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = []
        rows += upsert_teams(args.teams)
        rows += upsert_staff("game_master", args.game_masters)
        rows += upsert_staff("booth_agent", args.booth_agents)
        rows += upsert_staff("security_officer", args.security_officers)
        db.session.commit()

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["role", "name", "login", "secret"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} credentials -> {args.out}")
    print(
        "This file has plaintext secrets. Print the team keys onto key cards, "
        "hand staff their logins, then delete this file — it can't be regenerated, "
        "only replaced by re-running this script."
    )


if __name__ == "__main__":
    main()
