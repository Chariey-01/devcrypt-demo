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


def test_agent_cannot_author_knowledge_questions_the_upload_interface_was_removed(client, app):
    # Product decision: Knowledge Check content is hardcoded in app/knowledge_bank.py and
    # synced via scripts/sync_knowledge_bank.py, never authored through the Agent Dashboard.
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
    assert res.status_code == 404


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


def _add_n_questions(app, mission_id, n):
    with app.app_context():
        ids = []
        for i in range(n):
            q = KnowledgeQuestion(mission_id=mission_id, question_text=f"Question {i}?", order_index=i)
            db.session.add(q)
            db.session.flush()
            correct = KnowledgeOption(question_id=q.id, option_text="Right", is_correct=True)
            wrong = KnowledgeOption(question_id=q.id, option_text="Wrong", is_correct=False)
            db.session.add_all([correct, wrong])
            db.session.commit()
            ids.append(q.id)
        return ids


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


def test_only_a_random_subset_of_five_is_served_from_a_larger_pool(client, app):
    from app.services.mission_service import KNOWLEDGE_CHECK_POOL_SIZE

    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_n_questions(app, mission_id, 15)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    served = status["mission"]["knowledge_questions"]
    assert len(served) == KNOWLEDGE_CHECK_POOL_SIZE == 5
    assert status["mission"]["knowledge_check_complete"] is False


def test_assigned_subset_is_stable_across_repeated_polls(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_n_questions(app, mission_id, 15)
    _login_team(client)

    first = client.get("/missions/status").get_json()
    second = client.get("/missions/status").get_json()
    first_ids = [q["id"] for q in first["mission"]["knowledge_questions"]]
    second_ids = [q["id"] for q in second["mission"]["knowledge_questions"]]
    assert first_ids == second_ids  # same 5, same order -- never reshuffled mid-booth


def test_booth_with_fewer_questions_than_pool_size_serves_all_of_them(client, app):
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_n_questions(app, mission_id, 3)  # fewer than the pool size of 5
    _login_team(client)

    status = client.get("/missions/status").get_json()
    assert len(status["mission"]["knowledge_questions"]) == 3


def test_cipher_reveal_uses_position_within_assigned_subset_not_raw_order_index(client, app):
    # A question's raw order_index in a 15-question pool could be far outside the cipher
    # word's length; the reveal must be based on where it sits in *this team's* 5-question
    # subset (0..4), not that raw index, or the modulo would land unpredictably.
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_n_questions(app, mission_id, 15)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    assigned = status["mission"]["knowledge_questions"]
    second_question_id = assigned[1]["id"]  # position 1 in the assigned subset
    with app.app_context():
        from app.models import KnowledgeOption

        correct_option_id = (
            KnowledgeOption.query.filter_by(question_id=second_question_id, is_correct=True).first().id
        )

    client.post(f"/missions/knowledge-check/{second_question_id}/answer", json={"option_id": correct_option_id})

    status_after = client.get("/missions/status").get_json()
    revealed = status_after["cryptogram"][0]["revealed"]
    # "CYBER" (mission's cipher_word, 5 letters) -- position 1 in the subset should reveal
    # index 1 % 5 == 1, regardless of that question's real order_index (which could be anywhere
    # in 0..14).
    assert revealed[1] is True
    assert sum(revealed) == 1


def test_replacing_a_booths_questions_reassigns_a_fresh_subset_instead_of_going_empty(client, app):
    # Regression test for the exact failure mode scripts/sync_knowledge_bank.py can trigger if
    # run mid-event: a team already has a stored subset, then every KnowledgeQuestion for that
    # booth gets deleted and recreated (fresh ids). Falling back to an empty list would make
    # knowledge_check_complete trivially true (0 answers >= 0 questions) and skip the Knowledge
    # Check entirely -- assign_knowledge_subset must instead notice none of the stored ids
    # still exist and assign a fresh subset.
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_n_questions(app, mission_id, 15)
    _login_team(client)

    first = client.get("/missions/status").get_json()
    assert len(first["mission"]["knowledge_questions"]) == 5

    with app.app_context():
        mission = Mission.query.get(mission_id)
        for q in list(mission.knowledge_questions):
            db.session.delete(q)
        db.session.commit()
        new_ids = _add_n_questions(app, mission_id, 15)

    second = client.get("/missions/status").get_json()
    served = second["mission"]["knowledge_questions"]
    assert len(served) == 5  # not 0
    assert second["mission"]["knowledge_check_complete"] is False
    assert all(q["id"] in new_ids for q in served)


def test_deleting_a_knowledge_question_with_a_recorded_answer_does_not_crash(client, app):
    # Regression test: TeamKnowledgeAnswer had no delete cascade from KnowledgeQuestion or
    # KnowledgeOption, so deleting a question a team had already answered hit a NOT NULL FK
    # violation -- the same bug class fixed for CodeSubmission/TeamMission, found while writing
    # scripts/sync_knowledge_bank.py (which needs to delete-and-replace a booth's questions).
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    question_id, correct_id, wrong_id = _add_question(app, mission_id)
    _login_team(client)

    client.post(f"/missions/knowledge-check/{question_id}/answer", json={"option_id": correct_id})

    with app.app_context():
        from app.models import KnowledgeQuestion, TeamKnowledgeAnswer

        question = KnowledgeQuestion.query.get(question_id)
        db.session.delete(question)
        db.session.commit()  # must not raise IntegrityError

        assert KnowledgeQuestion.query.get(question_id) is None
        assert TeamKnowledgeAnswer.query.filter_by(question_id=question_id).count() == 0


def test_run_tests_and_submit_unlock_after_completing_the_assigned_subset_from_a_larger_pool(client, app):
    # Regression test: run-tests/submit compared answers against the booth's FULL question pool
    # (mission.knowledge_questions, e.g. 15 in the real knowledge bank) instead of the 5-question
    # subset actually assigned to this team (assign_knowledge_subset). Every real booth has a
    # 15-question pool with only 5 assigned per team, so this made both routes permanently reject
    # every team that had, in fact, completed their entire Knowledge Check -- the coding challenge
    # could never be run or submitted by anyone.
    mission_id, team_id, agent_id = _setup_mission_with_challenge(app)
    _add_n_questions(app, mission_id, 15)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    assigned = status["mission"]["knowledge_questions"]
    assert len(assigned) == 5

    with app.app_context():
        for q in assigned:
            correct_option = KnowledgeOption.query.filter_by(question_id=q["id"], is_correct=True).first()
            client.post(f"/missions/knowledge-check/{q['id']}/answer", json={"option_id": correct_option.id})

    status_after = client.get("/missions/status").get_json()
    assert status_after["mission"]["knowledge_check_complete"] is True

    res = client.post("/missions/challenge/run-tests", json={"code": "n = int(input())\nprint(n * 2)\n"})
    assert res.status_code == 200, res.get_json()

    res = client.post("/missions/challenge/submit", json={"code": "n = int(input())\nprint(n * 2)\n"})
    assert res.status_code == 200, res.get_json()
