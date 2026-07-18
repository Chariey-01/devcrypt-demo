"""Generate cryptographically random team keys and staff passwords for a real event.

Run this AFTER seed.py (which sets up missions/evidence/MCQs and wipes the whole
database). This script only touches Team and User rows — it's safe to re-run any
time to add teams/staff or rotate everyone's credentials, without touching mission
content.

Secrets are only ever shown here, once, in plaintext. Only their bcrypt hashes are
stored in the database — there is no way to recover a lost key/password, only to
regenerate a new one by re-running this script for that team/account.

Usage:
    python3 scripts/generate_credentials.py \
        --teams "Alpha Squad" "Bravo Squad" "Charlie Squad" \
        --game-masters gm@devcrypt.local \
        --booth-agents agent1@devcrypt.local agent2@devcrypt.local \
        --security-officers officer@devcrypt.local \
        --out credentials.csv

Add --qr to also print one QR code per credential (requires "qrcode[pil]",
see requirements.txt) into --qr-dir. Each QR encodes plain login details as
text, not a clickable link, so scanning it doesn't log anyone in on its own
-- it just saves whoever's printing key cards from mistyping a random string.
"""

import argparse
import csv
import os
import re
import sys

# Running as `python3 scripts/generate_credentials.py` puts only scripts/ on sys.path (Python
# adds the script's own directory, not the cwd) — add the repo root so `app` resolves regardless
# of invocation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Team, User
from app.services.credential_service import generate_password, generate_team_key


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


def _safe_filename(text):
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def write_qr_codes(rows, qr_dir, base_url):
    import qrcode

    qr_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        if row["role"] == "team":
            lines = [f"DevCrypt Team: {row['name']}", f"Key: {row['secret']}"]
            login_path = "/auth/team-login"
        else:
            lines = [f"DevCrypt Staff ({row['role']})", f"Email: {row['login']}", f"Password: {row['secret']}"]
            login_path = "/auth/login"
        if base_url:
            lines.append(f"Login at: {base_url.rstrip('/')}{login_path}")

        img = qrcode.make("\n".join(lines))
        filename = qr_dir / f"{row['role']}_{_safe_filename(row['name'])}.png"
        img.save(filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teams", nargs="+", default=["Alpha Squad", "Bravo Squad"])
    parser.add_argument("--game-masters", nargs="+", default=["gm@devcrypt.local"])
    parser.add_argument("--booth-agents", nargs="+", default=["agent1@devcrypt.local", "agent2@devcrypt.local"])
    parser.add_argument("--security-officers", nargs="+", default=["officer@devcrypt.local"])
    parser.add_argument("--out", default="credentials.csv")
    parser.add_argument("--qr", action="store_true", help="Also write one QR code PNG per credential")
    parser.add_argument("--qr-dir", default="credentials_qr", help="Directory for QR PNGs (used with --qr)")
    parser.add_argument("--base-url", default="", help="Included as a login link inside each QR code, e.g. https://your-app.up.railway.app")
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

    if args.qr:
        from pathlib import Path

        qr_dir = Path(args.qr_dir)
        write_qr_codes(rows, qr_dir, args.base_url)
        print(f"Wrote {len(rows)} QR codes -> {qr_dir}/")

    print(
        "These files have plaintext secrets. Print the team keys/QR codes onto key cards, "
        "hand staff their logins, then delete both this file and the QR folder — they "
        "can't be regenerated, only replaced by re-running this script."
    )


if __name__ == "__main__":
    main()
