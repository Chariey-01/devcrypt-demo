from app.extensions import db, socketio
from app.models import Challenge, EventState, Mission, Team, TestCase, User
from app.services.event_service import EventService
from app.services.mission_service import MissionService

# socketio.test_client(app, flask_test_client=client) is the required coupling: it makes the
# socket handshake reuse that Flask test client's session cookie, so current_team()/current_user
# resolve correctly inside app/sockets.py's connect handler exactly like a real browser tab would.


def _setup(app):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team_a = Team(name="Alpha", score=0, integrity=100)
        team_a.set_key("ALPHA01")
        team_b = Team(name="Bravo", score=0, integrity=100)
        team_b.set_key("BRAVO01")
        db.session.add_all([agent, gm, team_a, team_b])
        db.session.add(EventState(status="running"))
        db.session.commit()

        mission = Mission(
            title="Doubler Node",
            type="code",
            narrative="Double the input.",
            cipher_word="DOUBLE",
            booth_id=1,
            order_index=1,
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
                name="visible case",
                input_data="3",
                expected_output="6",
                weight=1,
                visibility="visible",
                order_index=0,
            )
        )
        db.session.add(
            Mission(
                title="Trailing Node",
                type="flag",
                narrative="unused",
                cipher_word="TRAIL",
                booth_id=2,
                order_index=2,
            )
        )
        db.session.commit()
        return mission.id, team_a.id, team_b.id


def _login_team(client, name, key):
    res = client.post("/auth/team-login", data={"name": name, "key": key})
    assert res.status_code in (302, 200)
    return res


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    return res


def _event_names(received):
    return [msg["name"] for msg in received]


def test_team_client_receives_team_update_on_pass(app, client):
    _setup(app)
    _login_team(client, "Alpha", "ALPHA01")
    sio = socketio.test_client(app, flask_test_client=client)
    assert sio.is_connected()

    res = client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.status_code == 200
    assert res.get_json()["correct"] is True

    assert "team_update" in _event_names(sio.get_received())
    sio.disconnect()


def test_gm_client_receives_mod_update_on_pass(app, client):
    _setup(app)
    team_client = app.test_client()
    _login_team(team_client, "Alpha", "ALPHA01")

    gm_client = app.test_client()
    _login_gm(gm_client)
    sio_gm = socketio.test_client(app, flask_test_client=gm_client)
    assert sio_gm.is_connected()

    res = team_client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.status_code == 200

    assert "mod_update" in _event_names(sio_gm.get_received())
    sio_gm.disconnect()


def test_anonymous_client_receives_global_event_update(app, client):
    _setup(app)
    sio = socketio.test_client(app, flask_test_client=client)
    assert sio.is_connected()

    with app.app_context():
        EventService().pause()

    assert "event_update" in _event_names(sio.get_received())
    sio.disconnect()


def test_team_isolation_no_cross_team_leakage(app):
    _setup(app)
    client_a = app.test_client()
    _login_team(client_a, "Alpha", "ALPHA01")
    sio_a = socketio.test_client(app, flask_test_client=client_a)

    client_b = app.test_client()
    _login_team(client_b, "Bravo", "BRAVO01")
    sio_b = socketio.test_client(app, flask_test_client=client_b)

    assert sio_a.is_connected() and sio_b.is_connected()

    res = client_a.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.status_code == 200
    assert res.get_json()["correct"] is True

    assert "team_update" in _event_names(sio_a.get_received())
    assert "team_update" not in _event_names(sio_b.get_received())
    sio_a.disconnect()
    sio_b.disconnect()


def test_already_resolved_mission_does_not_double_emit(app, client):
    mission_id, team_a_id, _ = _setup(app)
    _login_team(client, "Alpha", "ALPHA01")
    sio = socketio.test_client(app, flask_test_client=client)
    assert sio.is_connected()

    with app.app_context():
        team = Team.query.get(team_a_id)
        mission = Mission.query.get(mission_id)
        service = MissionService()
        team_mission = service.get_or_create_team_mission(team, mission)

        first = service.complete_mission(team, team_mission, mission, "passed")
        assert first is not None

        second = service.complete_mission(team, team_mission, mission, "passed")
        assert second is None

    received = _event_names(sio.get_received())
    assert received.count("team_update") == 1
    sio.disconnect()


def test_agent_challenge_edit_pushes_global_update(app, client):
    # Confirms the Phase 3 sync fix: an Agent saving a challenge edit now notifies connected
    # players immediately (event_update -> refresh()) instead of only ever surfacing on the
    # next 2s poll tick.
    mission_id, _, _ = _setup(app)
    anon_client = app.test_client()
    sio = socketio.test_client(app, flask_test_client=anon_client)
    assert sio.is_connected()

    res = client.post("/auth/login", data={"email": "agent@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    res = client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={"prompt": "Read an integer and print triple it.", "starter_code": "n = int(input())"},
    )
    assert res.status_code == 200

    assert "event_update" in _event_names(sio.get_received())
    sio.disconnect()
