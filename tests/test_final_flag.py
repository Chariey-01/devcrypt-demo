import json

import pytest

from app import create_app
from app.config import Config, engine_options_for
from app.extensions import db
from app.models import Fragment, Mission, Team, TeamMission
from app.services.final_flag_service import FinalFlagService

TEST_SALT = "test-salt-for-final-flag"
REAL_FLAG = "FLAG{grid_core_restored}"

# The actual event final code (see project requirements: this exact value must come out of the
# full fragment-collection -> validation -> decryption pipeline every single time, with zero
# variation). Exercised end-to-end below using the real production classes (FinalFlagService,
# the /missions/final-flag route), not a re-implementation of the crypto.
EVENT_FLAG = "M3T4V3R$3"
EVENT_MISSION_IDS = [201, 202, 203, 204, 205, 206]


def _make_config(mission_ids, flag=REAL_FLAG):
    service = FinalFlagService(TEST_SALT, None)
    ciphertext = service.encrypt(flag, mission_ids)

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


def _build_app_with_missions(mission_ids, flag=REAL_FLAG, team_name="Alpha", team_key="ALPHA01"):
    # Same shape as flag_app_and_missions above, but parametrized so it can be reused for the
    # real 6-vault, real-flag ("M3T4V3R$3") end-to-end verification below.
    app = create_app(_make_config(mission_ids, flag=flag))
    with app.app_context():
        db.create_all()
        team = Team(name=team_name, score=0, integrity=100)
        team.set_key(team_key)
        db.session.add(team)
        missions = [
            Mission(id=mid, title=f"Node {mid}", type="code", narrative="x", cipher_word="X", booth_id=mid, order_index=mid)
            for mid in mission_ids
        ]
        db.session.add_all(missions)
        db.session.commit()
        team_id = team.id
    return app, team_id


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


# ---------------------------------------------------------------------------
# End-to-end verification that the real event flag, "M3T4V3R$3", is what six
# correctly-entered fragments always reconstruct to — via the actual production
# classes (FinalFlagService + the /missions/final-flag route), never a
# reimplementation of the crypto.
# ---------------------------------------------------------------------------


def test_six_fragments_reconstruct_the_real_event_flag():
    app, team_id = _build_app_with_missions(EVENT_MISSION_IDS, flag=EVENT_FLAG)
    _pass_all_missions_with_fragments(app, team_id, EVENT_MISSION_IDS)
    client = app.test_client()
    _login(client)

    correct = {str(mid): f"F{mid}:XX" for mid in EVENT_MISSION_IDS}
    res = _post_flag(client, correct)

    assert res.status_code == 200
    assert res.get_json()["flag"] == "M3T4V3R$3"


def test_event_flag_reconstruction_is_repeatable_across_ten_consecutive_runs():
    # Fresh app/db/team each iteration so this is ten independent end-to-end runs, not one run
    # whose result is merely read ten times. Zero variation is the requirement: any run that
    # doesn't produce exactly "M3T4V3R$3" fails the whole test immediately.
    for i in range(10):
        app, team_id = _build_app_with_missions(
            EVENT_MISSION_IDS, flag=EVENT_FLAG, team_name=f"Run{i}", team_key=f"RUNKEY{i}"
        )
        with app.app_context():
            _pass_all_missions_with_fragments(app, team_id, EVENT_MISSION_IDS)
        client = app.test_client()
        client.post("/auth/team-login", data={"name": f"Run{i}", "key": f"RUNKEY{i}"})

        correct = {str(mid): f"F{mid}:XX" for mid in EVENT_MISSION_IDS}
        res = _post_flag(client, correct)

        assert res.status_code == 200, f"run {i} failed with status {res.status_code}: {res.get_json()}"
        flag = res.get_json()["flag"]
        assert flag == "M3T4V3R$3", f"run {i} produced {flag!r} instead of 'M3T4V3R$3'"


def test_fragment_order_is_deterministic_regardless_of_mission_id_list_order():
    # master_key() sorts mission_ids internally (see final_flag_service.py) specifically so that
    # the order Mission ids happen to be passed in (e.g. from a differently-ordered DB query)
    # can never change the derived key. Confirms that guarantee directly against the service.
    service = FinalFlagService(TEST_SALT, None)
    ciphertext = service.encrypt(EVENT_FLAG, EVENT_MISSION_IDS)

    forward = FinalFlagService(TEST_SALT, ciphertext)
    shuffled = FinalFlagService(TEST_SALT, ciphertext)

    assert forward.reconstruct(EVENT_MISSION_IDS) == "M3T4V3R$3"
    assert shuffled.reconstruct(list(reversed(EVENT_MISSION_IDS))) == "M3T4V3R$3"
    assert (
        forward.reconstruct(EVENT_MISSION_IDS)
        == shuffled.reconstruct(sorted(EVENT_MISSION_IDS, key=lambda x: -x))
    )


def test_final_flag_rejects_when_one_fragment_is_missing():
    app, team_id = _build_app_with_missions(EVENT_MISSION_IDS, flag=EVENT_FLAG)
    _pass_all_missions_with_fragments(app, team_id, EVENT_MISSION_IDS)
    client = app.test_client()
    _login(client)

    incomplete = {str(mid): f"F{mid}:XX" for mid in EVENT_MISSION_IDS[:-1]}
    res = _post_flag(client, incomplete)

    assert res.status_code == 400
    body = res.get_json()
    assert "flag" not in body
    assert body["incorrect_mission_ids"] == [EVENT_MISSION_IDS[-1]]


def test_final_flag_rejects_single_character_change_in_a_fragment():
    app, team_id = _build_app_with_missions(EVENT_MISSION_IDS, flag=EVENT_FLAG)
    _pass_all_missions_with_fragments(app, team_id, EVENT_MISSION_IDS)
    client = app.test_client()
    _login(client)

    tampered_mission = EVENT_MISSION_IDS[0]
    correct = {str(mid): f"F{mid}:XX" for mid in EVENT_MISSION_IDS}
    real_value = correct[str(tampered_mission)]
    # Flip exactly one character.
    correct[str(tampered_mission)] = real_value[:-1] + ("Y" if real_value[-1] != "Y" else "Z")

    res = _post_flag(client, correct)

    assert res.status_code == 400
    assert res.get_json()["incorrect_mission_ids"] == [tampered_mission]


def test_final_flag_rejects_fragments_swapped_between_two_missions():
    # Reordering/cross-assigning otherwise-valid-looking fragment values (entering vault A's real
    # code under vault B, and vice versa) must not decrypt successfully — each mission's expected
    # value is keyed to that specific mission_id.
    app, team_id = _build_app_with_missions(EVENT_MISSION_IDS, flag=EVENT_FLAG)
    _pass_all_missions_with_fragments(app, team_id, EVENT_MISSION_IDS)
    client = app.test_client()
    _login(client)

    mission_a, mission_b = EVENT_MISSION_IDS[0], EVENT_MISSION_IDS[1]
    swapped = {str(mid): f"F{mid}:XX" for mid in EVENT_MISSION_IDS}
    swapped[str(mission_a)], swapped[str(mission_b)] = swapped[str(mission_b)], swapped[str(mission_a)]

    res = _post_flag(client, swapped)

    assert res.status_code == 400
    assert set(res.get_json()["incorrect_mission_ids"]) == {mission_a, mission_b}


def test_final_flag_rejects_the_same_fragment_value_reused_across_two_missions():
    # A team pastes the same collected code into two different vault fields instead of each
    # vault's own code. At most one of the two missions can have that as its real value (HMAC
    # digests differ per mission_id), so this must never validate both.
    app, team_id = _build_app_with_missions(EVENT_MISSION_IDS, flag=EVENT_FLAG)
    _pass_all_missions_with_fragments(app, team_id, EVENT_MISSION_IDS)
    client = app.test_client()
    _login(client)

    mission_a, mission_b = EVENT_MISSION_IDS[0], EVENT_MISSION_IDS[1]
    duplicated = {str(mid): f"F{mid}:XX" for mid in EVENT_MISSION_IDS}
    duplicated[str(mission_b)] = duplicated[str(mission_a)]

    res = _post_flag(client, duplicated)

    assert res.status_code == 400
    assert mission_b in res.get_json()["incorrect_mission_ids"]
    assert mission_a not in res.get_json()["incorrect_mission_ids"]
