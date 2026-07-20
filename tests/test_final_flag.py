import json

import pytest

from app import create_app
from app.config import Config, engine_options_for
from app.extensions import db
from app.models import Fragment, Mission, Team, TeamMission
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


def _pass_all_missions_with_fragments(app, team_id, mission_ids):
    with app.app_context():
        for mid in mission_ids:
            db.session.add(TeamMission(team_id=team_id, mission_id=mid, status="passed"))
            db.session.add(Fragment(team_id=team_id, mission_id=mid, cipher_value=f"F{mid}:XX"))
        db.session.commit()


def _post_flag(client, fragments):
    return client.post("/missions/final-flag", data=json.dumps({"fragments": fragments}), content_type="application/json")


def test_requirements_denied_before_any_mission_passed(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    client = app.test_client()
    _login(client)

    res = client.get("/missions/final-flag/requirements")
    assert res.status_code == 403


def test_requirements_denied_with_only_some_missions_passed(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    with app.app_context():
        db.session.add(TeamMission(team_id=team_id, mission_id=mission_ids[0], status="passed"))
        db.session.commit()
    client = app.test_client()
    _login(client)

    res = client.get("/missions/final-flag/requirements")
    assert res.status_code == 403


def test_requirements_lists_vaults_once_all_missions_passed(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    _pass_all_missions_with_fragments(app, team_id, mission_ids)
    client = app.test_client()
    _login(client)

    res = client.get("/missions/final-flag/requirements")
    assert res.status_code == 200
    returned_ids = [v["mission_id"] for v in res.get_json()["vaults"]]
    assert returned_ids == mission_ids


def test_final_flag_denied_without_entering_fragments(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    _pass_all_missions_with_fragments(app, team_id, mission_ids)
    client = app.test_client()
    _login(client)

    res = _post_flag(client, {})
    assert res.status_code == 400
    body = res.get_json()
    assert "flag" not in body
    assert set(body["incorrect_mission_ids"]) == set(mission_ids)


def test_final_flag_denied_with_one_wrong_fragment(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    _pass_all_missions_with_fragments(app, team_id, mission_ids)
    client = app.test_client()
    _login(client)

    correct = {str(mid): f"F{mid}:XX" for mid in mission_ids}
    correct[str(mission_ids[0])] = "WRONG:VALUE"

    res = _post_flag(client, correct)
    assert res.status_code == 400
    assert res.get_json()["incorrect_mission_ids"] == [mission_ids[0]]


def test_final_flag_reconstructed_with_correct_fragments(flag_app_and_missions):
    app, mission_ids, team_id = flag_app_and_missions
    _pass_all_missions_with_fragments(app, team_id, mission_ids)
    client = app.test_client()
    _login(client)

    # Deliberately mixed case / stray whitespace — the server normalizes the same way
    # cipher_service.solve() does elsewhere in this codebase.
    correct = {str(mid): f"  f{mid}:xx  " for mid in mission_ids}

    res = _post_flag(client, correct)
    assert res.status_code == 200
    assert res.get_json()["flag"] == REAL_FLAG


def test_final_flag_wrong_salt_fails_closed_instead_of_returning_garbage(flag_app_and_missions):
    # Simulates exactly the production incident this guards against: FINAL_FLAG_CIPHERTEXT was
    # generated under one EVENT_SALT, but the server is now running with a different one (rotated,
    # or never matched in the first place). Before the fix, reconstruct() would decode with
    # errors="replace" and hand the team mojibake as if it were their real flag with a 200 OK.
    app, mission_ids, team_id = flag_app_and_missions
    _pass_all_missions_with_fragments(app, team_id, mission_ids)
    app.config["EVENT_SALT"] = "a-completely-different-salt-than-the-one-used-to-encrypt"
    client = app.test_client()
    _login(client)

    correct = {str(mid): f"F{mid}:XX" for mid in mission_ids}
    res = _post_flag(client, correct)

    assert res.status_code == 500
    body = res.get_json()
    assert "flag" not in body
    assert "Game Master" in body["error"]


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

    res = client.get("/missions/final-flag/requirements")
    assert res.status_code == 404
