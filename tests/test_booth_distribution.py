from app.extensions import db
from app.models import Mission, Team, User


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)


def _setup(app, team_count=5, booth_count=3):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        team_ids = []
        for i in range(team_count):
            team = Team(name=f"Team {i}", score=0, integrity=100)
            team.set_key(f"KEY{i:04d}")
            db.session.add(team)
            db.session.flush()
            team_ids.append(team.id)
        mission_ids = []
        for i in range(booth_count):
            mission = Mission(
                title=f"Booth {i}",
                type="code",
                narrative="n",
                cipher_word="WORD",
                booth_id=i + 1,
                order_index=i,
            )
            db.session.add(mission)
            db.session.flush()
            mission_ids.append(mission.id)
        db.session.commit()
        return team_ids, mission_ids


def test_distribute_booths_round_robins_evenly(client, app):
    team_ids, mission_ids = _setup(app, team_count=7, booth_count=3)
    _login_gm(client)

    res = client.post("/mod/teams/distribute-booths")
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["assignments"]) == 7

    with app.app_context():
        teams = Team.query.order_by(Team.id).all()
        assigned = [t.starting_mission_id for t in teams]
        # 7 teams across 3 booths -> counts of [3, 2, 2] in some order, never all on one booth.
        from collections import Counter

        counts = Counter(assigned)
        assert len(counts) == 3
        assert sorted(counts.values()) == [2, 2, 3]

        # Consecutive teams (by creation order) never share a starting booth -- the round-robin
        # property that "minimises two teams arriving at the same booth" is about spread, not
        # a strict no-repeats guarantee once team_count > booth_count.
        for i in range(len(assigned) - 1):
            if i % 3 != 2:  # skip the wrap-around point where it legitimately repeats
                assert assigned[i] != assigned[i + 1]


def test_distribute_booths_requires_teams_and_booths(client, app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        db.session.commit()
    _login_gm(client)

    res = client.post("/mod/teams/distribute-booths")
    assert res.status_code == 400


def test_distribute_booths_overwrites_existing_assignment(client, app):
    team_ids, mission_ids = _setup(app, team_count=2, booth_count=2)
    with app.app_context():
        team = Team.query.get(team_ids[0])
        team.starting_mission_id = mission_ids[1]
        db.session.commit()
    _login_gm(client)

    res = client.post("/mod/teams/distribute-booths")
    assert res.status_code == 200

    with app.app_context():
        team = Team.query.get(team_ids[0])
        assert team.starting_mission_id == mission_ids[0]  # reassigned to the round-robin value
