"""One-time setup: encrypt the event's final flag against a fixed set of Mission ids, using the
*target environment's* EVENT_SALT as the key material. Prints the two env vars to paste into
that environment (Railway dashboard, etc.) — never writes them anywhere itself, never touches
the database, and the plaintext flag is never stored, only ever typed once at the terminal.

Run this from the SAME environment whose EVENT_SALT you're targeting (e.g. with production's
EVENT_SALT exported locally, or via `railway run python3 scripts/derive_final_flag.py ...` if
using the Railway CLI) — the ciphertext this produces is only ever decryptable by a server that
has that exact EVENT_SALT.

Usage:
    # Find the Mission ids that should count toward the flag first:
    python3 scripts/verify_missions.py

    python3 scripts/derive_final_flag.py --flag "FLAG{...}" --mission-ids 1,2,3,4,5,6
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.final_flag_service import FinalFlagService


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flag", required=True, help="The real, secret final flag plaintext.")
    parser.add_argument(
        "--mission-ids",
        required=True,
        help="Comma-separated Mission ids that must ALL be passed to unlock the flag (see scripts/verify_missions.py).",
    )
    parser.add_argument(
        "--event-salt",
        default=os.getenv("EVENT_SALT"),
        help="Defaults to this shell's EVENT_SALT env var — must match the target deployment's.",
    )
    args = parser.parse_args()

    if not args.event_salt:
        print("EVENT_SALT not set (env var or --event-salt) — aborting.", file=sys.stderr)
        sys.exit(1)

    mission_ids = [int(x) for x in args.mission_ids.split(",") if x.strip()]
    if not mission_ids:
        print("--mission-ids must list at least one id.", file=sys.stderr)
        sys.exit(1)

    service = FinalFlagService(args.event_salt, None)
    ciphertext_b64 = service.encrypt(args.flag, mission_ids)

    # Round-trip check before printing anything, so a bug here can never hand out a ciphertext
    # that doesn't actually decrypt back to what was just typed in.
    verify_service = FinalFlagService(args.event_salt, ciphertext_b64)
    if verify_service.reconstruct(mission_ids) != args.flag:
        print("Internal error: round-trip check failed — ciphertext NOT generated.", file=sys.stderr)
        sys.exit(1)

    print("Round-trip check passed. Set these two environment variables on the target deployment:\n")
    print(f"FINAL_FLAG_CIPHERTEXT={ciphertext_b64}")
    print(f"FINAL_FLAG_MISSION_IDS={','.join(str(m) for m in mission_ids)}")
    print(
        "\nThe flag will only ever be reconstructed server-side, and only once a team has "
        "actually passed every one of those missions — see app/services/final_flag_service.py."
    )


if __name__ == "__main__":
    main()
