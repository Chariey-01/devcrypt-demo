from app.extensions import db
from app.models import (
    Challenge,
    EventState,
    KnowledgeOption,
    KnowledgeQuestion,
    Mission,
    Team,
    TeamMission,
    TestCase,
    User,
)


def _login_agent(client, email="agent@test.local"):
    return client.post("/auth/login", data={"email": email, "password": "pw"})


def _login_team(client):
    return client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})


def _setup_mission_with_challenge(app):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([agent, team])
        db.session.add(EventState(status="running"))
        db.session.commit()

        mission = Mission(
            title="Cyber Node", type="code", narrative="n", cipher_word="CYBER",
            booth_id=1, order_index=1, owner_agent_id=agent.id,
        )
        db.session.add(mission)
        db.session.flush()
        challenge = Challenge(mission_id=mission.id, type="code", prompt="Double it.", grading_mode="auto")
        db.session.add(challenge)
        db.session.flush()
        db.session.add(
            TestCase(
                challenge_id=challenge.id, name="case", input_data="3", expected_output="6",
                weight=1, visibility="visible", order_index=0,
            )
        )
        db.session.commit()
        return mission.id, team.id, agent.id


def test_agent_can_author_a_knowledge_question_via_the_dashboard(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _login_agent(client)

    res = client.post(
        f"/agent/missions/{mission_id}/knowledge-questions",
        json={
            "question_text": "What attack exploits human psychology?",
            "options": [
                {"option_text": "Phishing", "is_correct": True},
                {"option_text": "Buffer overflow", "is_correct": False},
            ],
        },
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["question_text"] == "What attack exploits human psychology?"
    assert len(body["options"]) == 2


def test_creating_a_question_requires_exactly_one_correct_option(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _login_agent(client)

    res = client.post(
        f"/agent/missions/{mission_id}/knowledge-questions",
        json={
            "question_text": "Q?",
            "options": [
                {"option_text": "A", "is_correct": True},
                {"option_text": "B", "is_correct": True},
            ],
        },
    )
    assert res.status_code == 400


def _add_question(app, mission_id, correct_text="Phishing"):
    with app.app_context():
        q = KnowledgeQuestion(mission_id=mission_id, question_text="What attack exploits human psychology?")
        db.session.add(q)
        db.session.flush()
        correct = KnowledgeOption(question_id=q.id, option_text=correct_text, is_correct=True)
        wrong = KnowledgeOption(question_id=q.id, option_text="Buffer overflow", is_correct=False)
        db.session.add_all([correct, wrong])
        db.session.commit()
        return q.id, correct.id, wrong.id


def test_challenge_stage_is_hidden_until_knowledge_check_answered(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_question(app, mission_id)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    assert status["mission"]["knowledge_check_complete"] is False
    assert len(status["mission"]["knowledge_questions"]) == 1

    # Both run-tests and submit must refuse until the Knowledge Check is done.
    res = client.post("/missions/challenge/run-tests", json={"code": "print(6)"})
    assert res.status_code == 400
    res = client.post("/missions/challenge/submit", json={"code": "print(6)"})
    assert res.status_code == 400


def test_correct_answer_scores_points_and_unlocks_the_challenge(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    question_id, correct_id, wrong_id = _add_question(app, mission_id)
    _login_team(client)

    res = client.post(f"/missions/knowledge-check/{question_id}/answer", json={"option_id": correct_id})
    body = res.get_json()
    assert body["correct"] is True

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        assert team.score == 3  # KNOWLEDGE_CORRECT

    status = client.get("/missions/status").get_json()
    assert status["mission"]["knowledge_check_complete"] is True

    # Now unlocked.
    res = client.post("/missions/challenge/run-tests", json={"code": "print(int(input())*2)"})
    assert res.status_code == 200


def test_wrong_answer_scores_nothing_and_stays_locked(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    question_id, correct_id, wrong_id = _add_question(app, mission_id)
    _login_team(client)

    res = client.post(f"/missions/knowledge-check/{question_id}/answer", json={"option_id": wrong_id})
    assert res.get_json()["correct"] is False

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        assert team.score == 0

    status = client.get("/missions/status").get_json()
    # Wrong answer still *counts* as answered (one attempt per question) — complete either way.
    assert status["mission"]["knowledge_check_complete"] is True


def test_answering_twice_does_not_double_score(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    question_id, correct_id, wrong_id = _add_question(app, mission_id)
    _login_team(client)

    client.post(f"/missions/knowledge-check/{question_id}/answer", json={"option_id": correct_id})
    res = client.post(f"/missions/knowledge-check/{question_id}/answer", json={"option_id": correct_id})
    assert res.get_json()["already_answered"] is True

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        assert team.score == 3  # not 6


def test_correct_answer_reveals_a_cipher_clue_but_real_fragment_still_requires_the_challenge(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    question_id, correct_id, wrong_id = _add_question(app, mission_id)
    _login_team(client)

    status_before = client.get("/missions/status").get_json()
    revealed_before = status_before["cryptogram"][0]["revealed"]
    assert not any(revealed_before)  # nothing revealed yet

    client.post(f"/missions/knowledge-check/{question_id}/answer", json={"option_id": correct_id})

    status_after = client.get("/missions/status").get_json()
    revealed_after = status_after["cryptogram"][0]["revealed"]
    assert any(revealed_after)  # a clue is now revealed
    assert not all(revealed_after)  # but not the whole word -- that's only on a real pass
    assert status_after["fragments"] == []  # and definitely no real Fragment yet

    # Now clear the challenge for real -- the actual fragment only comes from this.
    client.post("/missions/challenge/submit", json={"code": "n = int(input())\nprint(n * 2)\n"})
    status_final = client.get("/missions/status").get_json()
    assert len(status_final["fragments"]) == 1
