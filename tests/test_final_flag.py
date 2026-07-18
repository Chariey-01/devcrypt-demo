import pytest

from app import create_app
from app.config import Config, engine_options_for
from app.extensions import db
from app.models import Mission, Team, TeamMission
from app.services.final_flag_service import FinalFlagService

TEST_SALT = "test-salt-for-final-flag"
REAL_FLAG = "FLAG{grid_core_restored}"


def _make_config(mission_ids):
    service = FinalFlagService(TEST_SALT, None)
    ciphertext = service.encrypt(REAL_FLAG, mission_ids)

    class FinalFlagTestConfig(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_ENGINE_OPTIONS = engine_options_for(SQLALCHEMY_DATABASE_URI)
        SECRET_KEY = "test-secret"
        EVENT_SALT = TEST_SALT
        FINAL_FLAG_CIPHERTEXT = ciphertext
        FINAL_FLAG_MISSION_IDS = mission_ids

    return FinalFlagTestConfig


@pytest.fixture
def flag_app_and_missions():
    # Explicit ids (rather than letting the DB auto-increment) so _make_config can compute a
    # matching ciphertext before any row exists — mirrors derive_final_flag.py's real usage,
    # which is always run against ids already known from scripts/verify_missions.py.
    mission_ids = [101, 102, 103]
    app = create_app(_make_config(mission_ids))
    with app.app_context():
        db.create_all()
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        missions = [
            Mission(id=mid, title=f"Node {mid}", type="code", narrative="x", cipher_word="X", booth_id=mid, order_index=mid)
            for mid in mission_ids
        ]
        db.session.add_all(missions)
        db.session.commit()
        team_id = team.id

    return app, mission_ids, team_id


def _login(client):
    return client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})


def test_final_flag_denied_before_any_mission_passed(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    client = app.test_client()
    _login(client)

    res = client.get("/missions/final-flag")
    assert res.status_code == 403
    assert "flag" not in res.get_json()


def test_final_flag_denied_with_only_some_missions_passed(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    with app.app_context():
        db.session.add(TeamMission(team_id=team_id, mission_id=mission_ids[0], status="passed"))
        db.session.commit()
    client = app.test_client()
    _login(client)

    res = client.get("/missions/final-flag")
    assert res.status_code == 403
    assert "flag" not in res.get_json()


def test_final_flag_reconstructed_once_all_required_missions_passed(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    with app.app_context():
        for mid in mission_ids:
            db.session.add(TeamMission(team_id=team_id, mission_id=mid, status="passed"))
        db.session.commit()
    client = app.test_client()
    _login(client)

    res = client.get("/missions/final-flag")
    assert res.status_code == 200
    assert res.get_json()["flag"] == REAL_FLAG


def test_final_flag_not_configured_returns_404(app, client):
    # The shared conftest TestConfig has no FINAL_FLAG_CIPHERTEXT set at all — confirms the
    # route fails closed (never fabricates or falls back to any default flag value) rather than
    # erroring in some way that could leak information.
    with app.app_context():
        team = Team(name="Bravo", score=0, integrity=100)
        team.set_key("BRAVO01")
        db.session.add(team)
        db.session.commit()
    client.post("/auth/team-login", data={"name": "Bravo", "key": "BRAVO01"})

    res = client.get("/missions/final-flag")
    assert res.status_code == 404
