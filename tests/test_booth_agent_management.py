from flask import g

from app.extensions import db
from app.models import Mission, User


def _login_gm(client, app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        db.session.commit()
    return client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})


def test_game_master_creates_a_booth_agent_and_it_can_log_in(client, app):
    _login_gm(client, app)

    res = client.post(
        "/mod/credentials/generate",
        json={"kind": "booth_agent", "name": "newagent@test.local", "full_name": "Jordan Lee"},
    )
    assert res.status_code == 200
    password = res.get_json()["secret"]

    with app.app_context():
        agent = User.query.filter_by(email="newagent@test.local").first()
        assert agent is not None
        assert agent.role == "booth_agent"
        assert agent.full_name == "Jordan Lee"
        assert agent.is_active is True

    agent_client = app.test_client()
    login_res = agent_client.post("/auth/login", data={"email": "newagent@test.local", "password": password})
    assert login_res.status_code == 302
    # STAFF_DESTINATIONS routes a fresh booth_agent login straight to the CMS dashboard —
    # agents are grading-free monitors now, there's no separate manual-review queue to land on.
    assert login_res.headers["Location"].endswith("/agent/dashboard")


def test_game_master_can_edit_an_agent(client, app):
    _login_gm(client, app)
    client.post("/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"})
    with app.app_context():
        agent_id = User.query.filter_by(email="agent@test.local").first().id

    res = client.put(f"/mod/agents/{agent_id}", json={"full_name": "Sam Rivera", "email": "renamed@test.local"})
    assert res.status_code == 200
    with app.app_context():
        agent = User.query.get(agent_id)
        assert agent.full_name == "Sam Rivera"
        assert agent.email == "renamed@test.local"


def test_deactivated_agent_cannot_log_in(client, app):
    _login_gm(client, app)
    res = client.post(
        "/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"}
    )
    password = res.get_json()["secret"]
    with app.app_context():
        agent_id = User.query.filter_by(email="agent@test.local").first().id

    client.post(f"/mod/agents/{agent_id}/active", json={"is_active": False})

    agent_client = app.test_client()
    login_res = agent_client.post("/auth/login", data={"email": "agent@test.local", "password": password})
    assert login_res.status_code == 401


def test_deactivating_an_agent_locks_out_their_already_open_session_immediately(client, app):
    _login_gm(client, app)
    res = client.post("/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"})
    password = res.get_json()["secret"]
    with app.app_context():
        agent_id = User.query.filter_by(email="agent@test.local").first().id

    agent_client = app.test_client()
    agent_client.post("/auth/login", data={"email": "agent@test.local", "password": password})
    # Session is valid and working before deactivation.
    assert agent_client.get("/agent/missions").status_code == 200

    # Deactivate directly against the DB rather than via client.post(.../deactivate): under
    # pytest-flask, two test clients that are BOTH independently logged in via Flask-Login share
    # one app-context-scoped `g` for the test's duration, so a second client's HTTP login/action
    # clobbers `current_user` for the first client's *next* request too, regardless of which
    # client's cookie is actually sent. Going straight to the DB isolates this test to the one
    # thing it's actually verifying — that roles_required rechecks is_active on every request,
    # not just at login — without tripping over that unrelated test-harness quirk.
    with app.app_context():
        agent = User.query.get(agent_id)
        agent.is_active = False
        db.session.commit()

    # pytest-flask's autouse `_push_request_context` fixture keeps one request/app context (and
    # therefore one `flask.g`) alive for this whole test, so Flask-Login's own current_user
    # cache on `g` would otherwise still hold the *pre-deactivation* user object here even
    # though the DB has already changed — an artifact of the test harness, not of the real
    # per-request app. Clearing it forces the next request to re-resolve current_user from the
    # session cookie, matching what actually happens on a real, separate incoming request.
    if hasattr(g, "_login_user"):
        del g._login_user

    # Same still-logged-in session, no new login — must be locked out immediately. 401, not
    # 403: Flask-Login's UserMixin defines is_authenticated as `return self.is_active`, so an
    # inactive user is treated as fully unauthenticated by @login_required itself, before
    # roles_required's own is_active check ever runs.
    assert agent_client.get("/agent/missions").status_code == 401


def test_reactivating_an_agent_restores_login(client, app):
    _login_gm(client, app)
    res = client.post("/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"})
    password = res.get_json()["secret"]
    with app.app_context():
        agent_id = User.query.filter_by(email="agent@test.local").first().id

    client.post(f"/mod/agents/{agent_id}/active", json={"is_active": False})
    client.post(f"/mod/agents/{agent_id}/active", json={"is_active": True})

    agent_client = app.test_client()
    login_res = agent_client.post("/auth/login", data={"email": "agent@test.local", "password": password})
    assert login_res.status_code == 302


def test_cannot_delete_an_agent_who_still_owns_booths(client, app):
    _login_gm(client, app)
    client.post("/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"})
    with app.app_context():
        agent = User.query.filter_by(email="agent@test.local").first()
        mission = Mission(
            title="Owned Booth", type="code", narrative="n", cipher_word="X",
            booth_id=1, order_index=1, owner_agent_id=agent.id,
        )
        db.session.add(mission)
        db.session.commit()
        agent_id = agent.id

    res = client.delete(f"/mod/agents/{agent_id}")
    assert res.status_code == 409
    with app.app_context():
        assert User.query.get(agent_id) is not None


def test_can_delete_an_agent_with_no_owned_booths(client, app):
    _login_gm(client, app)
    client.post("/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"})
    with app.app_context():
        agent_id = User.query.filter_by(email="agent@test.local").first().id

    res = client.delete(f"/mod/agents/{agent_id}")
    assert res.status_code == 200
    with app.app_context():
        assert User.query.get(agent_id) is None


def test_cannot_assign_a_booth_to_a_deactivated_agent(client, app):
    _login_gm(client, app)
    client.post("/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"})
    with app.app_context():
        agent = User.query.filter_by(email="agent@test.local").first()
        agent_id = agent.id
        mission = Mission(
            title="Free Booth", type="code", narrative="n", cipher_word="Y", booth_id=2, order_index=2,
        )
        db.session.add(mission)
        db.session.commit()
        mission_id = mission.id

    client.post(f"/mod/agents/{agent_id}/active", json={"is_active": False})
    res = client.post(f"/mod/mission/{mission_id}/assign-agent", json={"agent_id": agent_id})
    assert res.status_code == 400
    with app.app_context():
        assert Mission.query.get(mission_id).owner_agent_id is None


def test_list_agents_reports_active_status_and_last_login(client, app):
    # Agent's own login has to happen (and finish) before the GM's login below, and no other
    # client authenticates after it — seeded that way specifically to sidestep the pytest-flask
    # shared-`g` quirk described in test_deactivating_an_agent_locks_out_their_already_open_
    # session_immediately above (two clients both live-authenticated via Flask-Login at once).
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        db.session.commit()

    agent_client = app.test_client()
    agent_client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    res = agent_client.post(
        "/mod/credentials/generate", json={"kind": "booth_agent", "name": "agent@test.local"}
    )
    password = res.get_json()["secret"]
    agent_client.post("/auth/logout")
    agent_client.post("/auth/login", data={"email": "agent@test.local", "password": password})

    client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    listing = client.get("/mod/agents").get_json()
    row = next(a for a in listing["agents"] if a["email"] == "agent@test.local")
    assert row["is_active"] is True
    assert row["last_login_at"] is not None
