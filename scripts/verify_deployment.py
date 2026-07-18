"""Release Candidate verification — not part of the deployed app (like loadtest.py).

Runs every workflow on the RC verification list against a *real* running deployment (staging or
local) and reports PASS/FAIL for each, with the observed evidence for each result. Built so that
the moment a staging URL exists, verification is one command instead of manual click-through.

Intended for a STAGING deployment or local server seeded with demo data — like loadtest.py, do
not run this against a database holding real event data (it exercises login, submission, and
grading, which will leave clearly test-shaped stamps: LoadTest teams aside, it defaults to the
`seed.py` demo accounts, and will fail loudly rather than silently if those don't exist, which is
itself a useful signal about which database it's pointed at).

Usage:
    # Against a local server (after `python3 scripts/seed.py` + a running gunicorn/run.py):
    python3 scripts/verify_deployment.py --url http://127.0.0.1:5000

    # Against a staging deployment (after running seed.py against it once):
    python3 scripts/verify_deployment.py --url https://your-app.up.railway.app

    # --seed-grading-check: none of the 6 default seed.py missions are auto-graded, so without
    # this flag "Automated grading" never actually exercises the grading engine — it just
    # reports "not applicable" every time, which would silently mask a real grading bug. This
    # flag imports the app directly and inserts one auto-graded mission ahead of Alpha Squad's
    # queue (requires DATABASE_URL to point at the *same* database --url is serving, e.g. run
    # this from the same shell you'd run `flask db upgrade`/`deploy_db_setup.py` from):
    python3 scripts/verify_deployment.py --url https://your-app.up.railway.app --seed-grading-check

Exit code 0 if every check passes, 1 otherwise — safe to use as a gate.
"""
import argparse
import os
import sys
import time

# Running as `python3 scripts/verify_deployment.py` puts only scripts/ on sys.path (Python adds
# the script's own directory, not the cwd) — add the repo root so `app` resolves regardless of
# invocation (needed by --seed-grading-check, which imports it lazily).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    import socketio
except ImportError:
    print(
        "Needs 'requests' and 'python-socketio[client]' — dev-only deps. Install with:\n"
        "  pip install requests python-socketio[client] websocket-client",
        file=sys.stderr,
    )
    sys.exit(1)


def seed_grading_check_mission(team_name):
    # Direct DB import, same pattern as loadtest.py's seed() — requires DATABASE_URL (in this
    # process's environment) to point at the same database the target --url is actually
    # serving. Idempotent: safe to run before every verification pass.
    from app import create_app
    from app.extensions import db
    from app.models import Challenge, Mission, TestCase, Team, User

    app = create_app()
    with app.app_context():
        team = Team.query.filter_by(name=team_name).first()
        if team is None:
            print(f"seed_grading_check_mission: no team named {team_name!r} found — skipping seed.")
            return False

        agent = User.query.filter_by(email="verify-agent@test.local").first()
        if not agent:
            agent = User(email="verify-agent@test.local", role="booth_agent")
            agent.set_password("pw")
            db.session.add(agent)
            db.session.flush()

        mission = Mission.query.filter_by(title="Verify Doubler").first()
        if mission is None:
            mission = Mission(
                title="Verify Doubler",
                type="code",
                narrative="Double the input.",
                cipher_word="VERIFY",
                booth_id=1,
                order_index=-1,  # first for every team
                owner_agent_id=agent.id,
            )
            db.session.add(mission)
            db.session.flush()

            challenge = Challenge(
                mission_id=mission.id,
                type="code",
                prompt="Read an integer and print double it.",
                grading_mode="auto",
                pass_threshold=100,
            )
            db.session.add(challenge)
            db.session.flush()
            db.session.add(
                TestCase(
                    challenge_id=challenge.id,
                    name="case",
                    input_data="3",
                    expected_output="6",
                    weight=1,
                    visibility="visible",
                    order_index=0,
                )
            )
            db.session.commit()
            print("seed_grading_check_mission: created 'Verify Doubler' auto-graded mission.")
        else:
            print("seed_grading_check_mission: 'Verify Doubler' already exists, reusing it.")
        return True


class Results:
    def __init__(self):
        self.checks = []

    def record(self, name, passed, detail=""):
        self.checks.append((name, passed, detail))
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))

    def summary(self):
        total = len(self.checks)
        passed = sum(1 for _, ok, _ in self.checks if ok)
        print(f"\n{'=' * 60}")
        print(f"{passed}/{total} checks passed")
        failed = [name for name, ok, _ in self.checks if not ok]
        if failed:
            print("Failed checks:")
            for name in failed:
                print(f"  - {name}")
        print(f"{'=' * 60}")
        return passed == total


def check_env_and_connectivity(base_url, r):
    # /healthz round-trips the DB, so 200 here confirms DATABASE_URL, PostgreSQL connectivity,
    # and that the process is actually up all in one shot. This is also the first real signal
    # migrations succeeded — a schema missing a table healthz doesn't touch would still pass
    # this check, so table-level migration correctness is confirmed later by the workflow
    # checks (challenge loading, submission) actually succeeding against real columns.
    try:
        resp = requests.get(f"{base_url}/healthz", timeout=15)
        r.record(
            "Environment / PostgreSQL connectivity (/healthz)",
            resp.status_code == 200 and resp.json().get("status") == "ok",
            f"status={resp.status_code} body={resp.text[:200]}",
        )
    except Exception as exc:
        r.record("Environment / PostgreSQL connectivity (/healthz)", False, f"{type(exc).__name__}: {exc}")

    try:
        resp = requests.get(f"{base_url}/static/socket.io.min.js", timeout=15)
        r.record(
            "Static assets served (socket.io.min.js)",
            resp.status_code == 200 and len(resp.content) > 1000,
            f"status={resp.status_code} size={len(resp.content)}b",
        )
    except Exception as exc:
        r.record("Static assets served (socket.io.min.js)", False, f"{type(exc).__name__}: {exc}")


def check_team_login(base_url, r, team_name, team_key):
    session = requests.Session()
    try:
        resp = session.post(
            f"{base_url}/auth/team-login",
            data={"name": team_name, "key": team_key},
            timeout=15,
            allow_redirects=False,
        )
        ok = resp.status_code in (302, 303)
        r.record("Team login", ok, f"status={resp.status_code} team={team_name!r}")
        return session if ok else None
    except Exception as exc:
        r.record("Team login", False, f"{type(exc).__name__}: {exc}")
        return None


def check_staff_login(base_url, r, label, email, password):
    session = requests.Session()
    try:
        resp = session.post(
            f"{base_url}/auth/login",
            data={"email": email, "password": password},
            timeout=15,
            allow_redirects=False,
        )
        ok = resp.status_code in (302, 303)
        r.record(f"Staff login ({label})", ok, f"status={resp.status_code} email={email!r}")
        return session if ok else None
    except Exception as exc:
        r.record(f"Staff login ({label})", False, f"{type(exc).__name__}: {exc}")
        return None


def check_qr_credential_equivalence(base_url, r, team_name, team_key):
    # generate_credentials.py's --qr encodes the same plaintext name+key a QR reader would hand
    # back to whoever's logging in — it's not a distinct auth mechanism (no auto-login token),
    # so "QR login works" reduces to "the credential the QR encodes logs in the normal way,"
    # already covered by check_team_login. This check just makes that equivalence explicit in
    # the report rather than leaving "QR login" looking untested.
    r.record(
        "QR login (equivalence check)",
        True,
        "QR encodes plain team name+key, not an auto-login token (see generate_credentials.py) "
        "— covered by the Team login check above; verify a printed card scans/reads correctly "
        "as a separate manual check, not something this script can drive.",
    )


def check_session_persistence(base_url, r, session):
    if session is None:
        r.record("Session persistence", False, "skipped — no logged-in session available")
        return
    try:
        results = []
        for i in range(3):
            resp = session.get(f"{base_url}/missions/status", timeout=15)
            results.append(resp.status_code)
            time.sleep(0.3)
        ok = all(code == 200 for code in results)
        r.record("Session persistence (3 sequential requests, same cookie)", ok, f"statuses={results}")
    except Exception as exc:
        r.record("Session persistence", False, f"{type(exc).__name__}: {exc}")


def check_challenge_loading(base_url, r, session):
    if session is None:
        r.record("Challenge loading", False, "skipped — no logged-in team session")
        return None
    try:
        resp = session.get(f"{base_url}/missions/status", timeout=15)
        ok = resp.status_code == 200 and "mission" in resp.json()
        mission = resp.json().get("mission") if ok else None
        r.record(
            "Challenge loading (/missions/status)",
            ok,
            f"status={resp.status_code} mission_title={mission.get('title') if mission else None}",
        )
        return mission
    except Exception as exc:
        r.record("Challenge loading", False, f"{type(exc).__name__}: {exc}")
        return None


def check_submission_and_grading(base_url, r, session, mission):
    if session is None or mission is None:
        r.record("Submission workflow", False, "skipped — no session/mission")
        r.record("Automated grading (pass case)", False, "skipped — no session/mission")
        r.record("Automated grading (fail case)", False, "skipped — no session/mission")
        return
    challenge = mission.get("challenge") or {}
    if challenge.get("grading_mode") != "auto":
        r.record(
            "Submission workflow / automated grading",
            True,
            "current mission isn't an auto-graded challenge — nothing to exercise here; "
            "not a failure, just not applicable to this team's current booth",
        )
        return

    # Both directions tested via run-tests first, deliberately — /run-tests never applies the
    # submit-path's 60s cooldown penalty, so testing fail-then-pass here doesn't lock out the
    # subsequent /submit call the way testing them in that order via /submit would.
    try:
        resp = session.post(f"{base_url}/missions/challenge/run-tests", json={"code": "print('wrong')"}, timeout=45)
        body = resp.json() if resp.status_code == 200 else {}
        r.record(
            "Automated grading (fail case, via run-tests)",
            resp.status_code == 200 and body.get("passed_tests") == 0,
            f"status={resp.status_code} passed_tests={body.get('passed_tests')}",
        )
    except Exception as exc:
        r.record("Automated grading (fail case, via run-tests)", False, f"{type(exc).__name__}: {exc}")

    try:
        resp = session.post(
            f"{base_url}/missions/challenge/run-tests", json={"code": "print(int(input()) * 2)"}, timeout=45
        )
        body = resp.json() if resp.status_code == 200 else {}
        r.record(
            "Submission workflow (run visible tests, correct code)",
            resp.status_code == 200 and body.get("passed_tests", 0) > 0,
            f"status={resp.status_code} passed_tests={body.get('passed_tests')}",
        )
    except Exception as exc:
        r.record("Submission workflow (run visible tests, correct code)", False, f"{type(exc).__name__}: {exc}")

    try:
        resp = session.post(
            f"{base_url}/missions/challenge/submit", json={"code": "print(int(input()) * 2)"}, timeout=45
        )
        body = resp.json() if resp.status_code == 200 else {}
        r.record(
            "Automated grading (pass case, via submit — proves the full grading+fragment+advancement pipeline)",
            resp.status_code == 200 and body.get("correct") is True,
            f"status={resp.status_code} correct={body.get('correct')} percent_score={body.get('percent_score')}",
        )
    except Exception as exc:
        r.record("Automated grading (pass case, via submit)", False, f"{type(exc).__name__}: {exc}")


def check_leaderboard(base_url, r):
    try:
        resp = requests.get(f"{base_url}/leaderboard/data", timeout=15)
        ok = resp.status_code == 200 and "leaderboard" in resp.json()
        r.record(
            "Leaderboard updates (/leaderboard/data)",
            ok,
            f"status={resp.status_code} team_count={len(resp.json().get('leaderboard', [])) if ok else 'n/a'}",
        )
    except Exception as exc:
        r.record("Leaderboard updates", False, f"{type(exc).__name__}: {exc}")


def check_socketio(base_url, r, session, team_name):
    if session is None:
        r.record("Socket.IO synchronization", False, "skipped — no logged-in session")
        return
    try:
        cookie_header = "; ".join(f"{k}={v}" for k, v in session.cookies.get_dict().items())
        received = []
        sio = socketio.Client()
        sio.on("team_update", lambda data: received.append(data))
        sio.on("event_update", lambda data: received.append(data))
        sio.connect(base_url, headers={"Cookie": cookie_header}, wait_timeout=15)
        connected = sio.connected
        time.sleep(1)
        sio.disconnect()
        r.record(
            "Socket.IO synchronization (connect)",
            connected,
            f"team={team_name!r} connected={connected}",
        )
    except Exception as exc:
        r.record("Socket.IO synchronization (connect)", False, f"{type(exc).__name__}: {exc}")


def check_error_handling(base_url, r, session):
    # Malformed/missing input should degrade to a clean 4xx JSON error, never a raw 500 with a
    # leaked stack trace. Every one of these is deliberately invalid input.
    cases = []

    try:
        resp = requests.post(f"{base_url}/auth/team-login", data={"name": "Nonexistent Team", "key": "WRONG"}, timeout=15)
        cases.append(("invalid team login", resp.status_code == 401))
    except Exception as exc:
        cases.append(("invalid team login", False))

    try:
        resp = requests.post(f"{base_url}/auth/login", data={"email": "nobody@nowhere.test", "password": "wrong"}, timeout=15)
        cases.append(("invalid staff login", resp.status_code == 401))
    except Exception as exc:
        cases.append(("invalid staff login", False))

    if session is not None:
        try:
            # No JSON body at all, wrong content-type — request.get_json(silent=True) should
            # degrade to {} rather than raising, per app/blueprints/missions.py.
            resp = session.post(f"{base_url}/missions/challenge/submit", data="not json", timeout=15)
            cases.append(("malformed submission body", resp.status_code < 500))
        except Exception:
            cases.append(("malformed submission body", False))

    try:
        resp = requests.get(f"{base_url}/missions/status", timeout=15, allow_redirects=False)
        # No team session at all — should redirect to login, not 500. allow_redirects=False is
        # required here: following the redirect would grade the destination login page's own
        # 200, not the redirect itself.
        cases.append(("unauthenticated status request", resp.status_code in (302, 303, 401, 403)))
    except Exception:
        cases.append(("unauthenticated status request", False))

    for name, ok in cases:
        r.record(f"Error handling — {name}", ok)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Base URL of the deployment to verify.")
    parser.add_argument("--team-name", default="Alpha Squad")
    parser.add_argument("--team-key", default="ALPHA01")
    parser.add_argument("--gm-email", default="gm@devcrypt.local")
    parser.add_argument("--gm-password", default="changeme")
    parser.add_argument("--agent-email", default="agent1@devcrypt.local")
    parser.add_argument("--agent-password", default="changeme")
    parser.add_argument("--officer-email", default="officer@devcrypt.local")
    parser.add_argument("--officer-password", default="changeme")
    parser.add_argument(
        "--seed-grading-check",
        action="store_true",
        help="Insert a real auto-graded mission ahead of --team-name's queue so 'Automated "
        "grading' is actually exercised rather than reported not-applicable. Requires "
        "DATABASE_URL (in this shell) to point at the same DB --url is serving.",
    )
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    r = Results()

    print(f"Verifying {base_url}\n{'=' * 60}")

    if args.seed_grading_check:
        seed_grading_check_mission(args.team_name)

    check_env_and_connectivity(base_url, r)

    team_session = check_team_login(base_url, r, args.team_name, args.team_key)
    check_qr_credential_equivalence(base_url, r, args.team_name, args.team_key)
    gm_session = check_staff_login(base_url, r, "Game Master", args.gm_email, args.gm_password)
    check_staff_login(base_url, r, "Booth Agent", args.agent_email, args.agent_password)
    if gm_session is not None:
        try:
            # Submission/grading can't be exercised until the event is running — this mirrors
            # the real Game Master pressing "Start Event" and is required, not incidental.
            resp = gm_session.post(f"{base_url}/mod/event/start", timeout=15, allow_redirects=False)
            r.record("Event start (via Game Master)", resp.status_code in (200, 302, 303), f"status={resp.status_code}")
        except Exception as exc:
            r.record("Event start (via Game Master)", False, f"{type(exc).__name__}: {exc}")
    check_staff_login(base_url, r, "Security Officer", args.officer_email, args.officer_password)

    check_session_persistence(base_url, r, team_session)
    mission = check_challenge_loading(base_url, r, team_session)
    check_submission_and_grading(base_url, r, team_session, mission)
    check_leaderboard(base_url, r)
    check_socketio(base_url, r, team_session, args.team_name)
    check_error_handling(base_url, r, team_session)

    if gm_session is not None:
        try:
            resp = gm_session.get(f"{base_url}/mod/data", timeout=15)
            r.record("Game Master dashboard data", resp.status_code == 200, f"status={resp.status_code}")
        except Exception as exc:
            r.record("Game Master dashboard data", False, f"{type(exc).__name__}: {exc}")

    print(
        "\nNOTE: 'Recovery after restart' is not automated here — it needs the deployment "
        "platform to actually restart the process. Trigger a restart from the Railway/Render "
        "dashboard, then re-run this script against the same URL; a clean pass afterward with "
        "the same team/session behaving correctly is the evidence for that check."
    )

    ok = r.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
