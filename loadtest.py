"""Local load-test tool for DevCrypt — not part of the deployed app (like generate_credentials.py).

Simulates N teams concurrently logging in, opening a Socket.IO connection, polling status, and
submitting code (a mix of correct/incorrect/duplicate-rapid-fire submissions to exercise the
race-condition guard in MissionService.complete_mission()) against a *running* server.

Usage:
    # 1. Seed load-test data into the target DB (only do this once per DB):
    python3 loadtest.py --seed --teams 40

    # 2. Run the load test against a running server (start it separately first, e.g.
    #    `gunicorn -k gevent -w 1 -b 127.0.0.1:5000 --timeout 60 --graceful-timeout 60
    #    "app:create_app()"` — the real production worker config, not `python3 run.py`):
    python3 loadtest.py --url http://127.0.0.1:5000 --teams 40
"""
import argparse
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    import socketio
except ImportError:
    print(
        "This tool needs 'requests' and 'python-socketio[client]' — dev-only deps, "
        "not part of the deployed app. Install with:\n"
        "  pip install requests python-socketio[client] websocket-client",
        file=sys.stderr,
    )
    sys.exit(1)


def seed(num_teams):
    from app import create_app
    from app.extensions import db
    from app.models import Challenge, EventState, Mission, Team, TestCase, User

    app = create_app()
    with app.app_context():
        EventState.query.delete()
        Team.query.filter(Team.name.like("LoadTest%")).delete(synchronize_session=False)
        Mission.query.filter(Mission.title.like("LoadTest%")).delete(synchronize_session=False)
        db.session.commit()

        agent = User.query.filter_by(email="loadtest-agent@test.local").first()
        if not agent:
            agent = User(email="loadtest-agent@test.local", role="booth_agent")
            agent.set_password("pw")
            db.session.add(agent)

        db.session.add(EventState(status="running"))

        mission = Mission(
            title="LoadTest Doubler",
            type="code",
            narrative="Double the input.",
            cipher_word="LOADTEST",
            booth_id=1,
            order_index=-1,  # first for every team
        )
        db.session.add(mission)
        db.session.flush()
        mission.owner_agent_id = agent.id

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

        teams = []
        for i in range(num_teams):
            name = f"LoadTest Team {i:03d}"
            key = f"LOAD{i:03d}"
            team = Team(name=name, score=0, integrity=100)
            team.set_key(key)
            teams.append((name, key))
            db.session.add(team)

        db.session.commit()
        print(f"Seeded {num_teams} teams and 1 auto-graded mission (LoadTest Doubler).")
        return teams


def _run_one_team(base_url, name, key, results):
    session = requests.Session()
    t0 = time.time()
    try:
        r = session.post(f"{base_url}/auth/team-login", data={"name": name, "key": key}, timeout=45)
        if r.status_code not in (200, 302):
            results.append({"team": name, "error": f"login failed: {r.status_code}"})
            return

        cookie_header = "; ".join(f"{k}={v}" for k, v in session.cookies.get_dict().items())
        sio = socketio.Client()
        received = []
        sio.on("team_update", lambda data: received.append(data))
        sio.connect(base_url, headers={"Cookie": cookie_header}, wait_timeout=45)

        # A couple of status polls, matching the real 2s poll loop's request shape.
        for _ in range(2):
            session.get(f"{base_url}/missions/status", timeout=45)

        # Fire the same submission twice back-to-back (near-simultaneous from the server's
        # point of view) to stress the duplicate-submission race guard, plus one wrong
        # submission first to exercise the fail/cooldown path too.
        r_wrong = session.post(
            f"{base_url}/missions/challenge/submit", json={"code": "print(999)"}, timeout=30
        )
        with ThreadPoolExecutor(max_workers=2) as dup_pool:
            dup_futures = [
                dup_pool.submit(
                    session.post,
                    f"{base_url}/missions/challenge/submit",
                    json={"code": "print(int(input()) * 2)"},
                    timeout=45,
                )
                for _ in range(2)
            ]
            dup_results = [f.result() for f in dup_futures]

        elapsed = time.time() - t0
        sio.disconnect()

        pass_count = sum(1 for r in dup_results if r.status_code == 200 and r.json().get("correct"))
        results.append(
            {
                "team": name,
                "elapsed": elapsed,
                "wrong_status": r_wrong.status_code,
                "dup_statuses": [r.status_code for r in dup_results],
                "dup_pass_count": pass_count,
                "socket_events_received": len(received),
            }
        )
    except Exception as exc:  # noqa: BLE001 — a load test needs to record every failure mode
        results.append({"team": name, "error": f"{type(exc).__name__}: {exc}"})


def run_load_test(base_url, num_teams):
    teams = [(f"LoadTest Team {i:03d}", f"LOAD{i:03d}") for i in range(num_teams)]
    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=num_teams) as pool:
        futures = [pool.submit(_run_one_team, base_url, name, key, results) for name, key in teams]
        for f in as_completed(futures):
            f.result()
    total_elapsed = time.time() - t0

    errors = [r for r in results if "error" in r]
    ok = [r for r in results if "error" not in r]
    double_pass = [r for r in ok if r["dup_pass_count"] > 1]
    no_socket_push = [r for r in ok if r["socket_events_received"] == 0]

    print(f"\n{'=' * 60}")
    print(f"Load test: {num_teams} teams, wall clock {total_elapsed:.2f}s")
    print(f"{'=' * 60}")
    print(f"Succeeded: {len(ok)}/{num_teams}")
    print(f"Errors: {len(errors)}")
    for e in errors[:20]:
        print(f"  {e['team']}: {e['error']}")
    if ok:
        elapsed_vals = [r["elapsed"] for r in ok]
        print(
            f"Per-team elapsed: min={min(elapsed_vals):.2f}s "
            f"max={max(elapsed_vals):.2f}s "
            f"mean={statistics.mean(elapsed_vals):.2f}s "
            f"median={statistics.median(elapsed_vals):.2f}s"
        )
    print(f"Teams where BOTH duplicate submissions scored a pass (should be 0): {len(double_pass)}")
    for r in double_pass[:10]:
        print(f"  {r['team']}: dup_statuses={r['dup_statuses']}")
    print(f"Teams that received 0 socket push events (should be 0): {len(no_socket_push)}")
    for r in no_socket_push[:10]:
        print(f"  {r['team']}")

    ok_result = not errors and not double_pass
    print(f"\n{'PASS' if ok_result else 'FAIL'}")
    return ok_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", action="store_true", help="Seed load-test teams/mission into the DB first.")
    parser.add_argument("--teams", type=int, default=40, help="Number of teams to seed/simulate (default 40).")
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="Base URL of the running server.")
    args = parser.parse_args()

    if args.seed:
        seed(args.teams)
    else:
        success = run_load_test(args.url, args.teams)
        sys.exit(0 if success else 1)
