from app.extensions import db
from app.models import (
    ClearanceStamp,
    CodeSubmission,
    EventLog,
    Fragment,
    LeaderboardSnapshot,
    Mission,
    Team,
    TeamMember,
    TeamMission,
    User,
)


def _setup(app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        officer = User(email="officer@test.local", role="security_officer")
        officer.set_password("pw")
        team = Team(name="Alpha", score=40, integrity=80, hints_used=2)
        team.set_key("ALPHA01")
        db.session.add_all([gm, officer, team])
        db.session.flush()

        mission = Mission(
            title="Doubler Node",
            type="code",
            narrative="Double the input.",
            cipher_word="DOUBLE",
            booth_id=1,
            order_index=1,
        )
        db.session.add(mission)
        db.session.flush()
        team.booth_current = mission.id

        team_mission = TeamMission(
            team_id=team.id, mission_id=mission.id, status="passed", attempts=2, score=40
        )
        db.session.add(team_mission)
        db.session.flush()

        # CodeSubmission is the FK relationship that AdminResetService's bulk-delete originally
        # missed (cascade="all, delete-orphan" is declared on the ORM relationship, but bulk
        # Query.delete() bypasses the ORM entirely and never triggers it) — passed silently
        # under SQLite's default lenient FK enforcement, then threw a real ForeignKeyViolation
        # the first time it ran against production Postgres. Included here so this exact class
        # of bug can never pass a local test run again.
        db.session.add(
            CodeSubmission(
                team_mission_id=team_mission.id, code="print(1)", mode="submit", passed=True
            )
        )
        db.session.add(Fragment(team_id=team.id, mission_id=mission.id, cipher_value="AB:CD"))
        db.session.add(ClearanceStamp(team_id=team.id, officer_id=officer.id, checkpoint_id=1))
        db.session.add(TeamMember(team_id=team.id, name="Alice"))
        db.session.commit()
        return team.id, mission.id


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)


def test_rename_team(app, client):
    team_id, _ = _setup(app)
    _login_gm(client)

    res = client.patch(f"/mod/team/{team_id}", json={"name": "Bravo"})
    assert res.status_code == 200
    with app.app_context():
        assert Team.query.get(team_id).name == "Bravo"


def test_rename_team_rejects_duplicate(app, client):
    team_id, _ = _setup(app)
    with app.app_context():
        other = Team(name="Charlie")
        other.set_key("CHARLIE01")
        db.session.add(other)
        db.session.commit()
    _login_gm(client)

    res = client.patch(f"/mod/team/{team_id}", json={"name": "Charlie"})
    assert res.status_code == 409


def test_delete_team_cascades_all_child_rows(app, client):
    team_id, mission_id = _setup(app)
    _login_gm(client)

    res = client.delete(f"/mod/team/{team_id}")
    assert res.status_code == 200

    with app.app_context():
        assert Team.query.get(team_id) is None
        assert TeamMission.query.filter_by(team_id=team_id).count() == 0
        assert Fragment.query.filter_by(team_id=team_id).count() == 0
        assert ClearanceStamp.query.filter_by(team_id=team_id).count() == 0
        assert TeamMember.query.filter_by(team_id=team_id).count() == 0
        assert CodeSubmission.query.count() == 0  # was tied to the deleted team's only TeamMission
        # Mission itself (event content, not team progress) must survive.
        assert Mission.query.get(mission_id) is not None


def test_reset_team_clears_progress_but_keeps_team_and_members(app, client):
    team_id, mission_id = _setup(app)
    _login_gm(client)

    res = client.post(f"/mod/team/{team_id}/reset")
    assert res.status_code == 200

    with app.app_context():
        team = Team.query.get(team_id)
        assert team is not None
        assert team.score == 0
        assert team.integrity == 100
        assert team.hints_used == 0
        assert team.booth_current is None
        assert TeamMission.query.filter_by(team_id=team_id).count() == 0
        assert Fragment.query.filter_by(team_id=team_id).count() == 0
        assert ClearanceStamp.query.filter_by(team_id=team_id).count() == 0
        assert CodeSubmission.query.count() == 0
        # Team identity and roster survive a progress reset.
        assert TeamMember.query.filter_by(team_id=team_id).count() == 1
        assert Mission.query.get(mission_id) is not None


def test_reset_all_teams_clears_every_team_and_event_history(app, client):
    team_id, mission_id = _setup(app)
    with app.app_context():
        second = Team(name="Bravo", score=15, integrity=90)
        second.set_key("BRAVO01")
        db.session.add(second)
        db.session.flush()
        second_id = second.id
        db.session.add(TeamMission(team_id=second.id, mission_id=mission_id, status="in_progress"))
        db.session.add(LeaderboardSnapshot(team_id=team_id, rank=1, score=40, integrity=80))
        db.session.add(EventLog(actor_role="game_master", action="pre_existing_noise"))
        db.session.commit()
        assert (
            EventLog.query.count() == 1
        )  # just the noise row — _setup() writes DB rows directly, no audit calls

    _login_gm(client)
    res = client.post("/mod/teams/reset-all")
    assert res.status_code == 200
    assert res.get_json()["teams_reset"] == 2

    with app.app_context():
        for tid in (team_id, second_id):
            team = Team.query.get(tid)
            assert team.score == 0
            assert team.integrity == 100
            assert TeamMission.query.filter_by(team_id=tid).count() == 0
        assert LeaderboardSnapshot.query.count() == 0
        # Old activity is gone, but the reset action itself left exactly one trace.
        logs = EventLog.query.all()
        assert len(logs) == 1
        assert logs[0].action == "all_teams_reset"
        # Team rows and event content (missions) survive a reset — only progress is cleared.
        assert Team.query.count() == 2
        assert Mission.query.get(mission_id) is not None
