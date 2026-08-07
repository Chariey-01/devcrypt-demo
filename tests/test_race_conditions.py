"""Regression coverage for two real races found during the production stabilization audit --
both confirmed as genuinely reachable under gevent's cooperative concurrency (a double-click, or
two browser tabs), not just theoretical. Follows test_scoring_concurrency.py's own established
technique: a single-threaded test can't fire two real concurrent HTTP requests, so the "other"
concurrent writer is simulated via a raw connection that bypasses db.session entirely, mirroring
exactly what an independent second request's own session would do. Tests the observable outcome
(no crash, no double-award) rather than which specific guard catches it -- the pre-existing
check-then-act path and the new UniqueConstraint/IntegrityError handler are both valid ways to
land on the same correct result, and a real race could hit either depending on timing."""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Event, Mission, Team, TeamKnowledgeAnswer, TeamMission
from app.services.mission_service import MissionService


def test_team_knowledge_answers_unique_constraint_rejects_a_duplicate(app):
    # Direct test of the schema-level guard the route's IntegrityError handling depends on -- if
    # this constraint is ever accidentally dropped, this fails loudly on its own, independent of
    # whether the route-level test below happens to pass for a different reason.
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        mission = Mission(title="Node", type="code", narrative="n", cipher_word="X", order_index=0)
        db.session.add_all([team, mission])
        db.session.commit()

        team_mission = TeamMission(team_id=team.id, mission_id=mission.id, status="in_progress")
        db.session.add(team_mission)
        db.session.commit()

        from app.models import KnowledgeOption, KnowledgeQuestion

        question = KnowledgeQuestion(mission_id=mission.id, question_text="Q?")
        db.session.add(question)
        db.session.flush()
        opt_a = KnowledgeOption(question_id=question.id, option_text="A", is_correct=True)
        opt_b = KnowledgeOption(question_id=question.id, option_text="B", is_correct=False)
        db.session.add_all([opt_a, opt_b])
        db.session.commit()

        db.session.add(
            TeamKnowledgeAnswer(
                team_mission_id=team_mission.id,
                question_id=question.id,
                selected_option_id=opt_a.id,
                is_correct=True,
            )
        )
        db.session.commit()

        db.session.add(
            TeamKnowledgeAnswer(
                team_mission_id=team_mission.id,
                question_id=question.id,
                selected_option_id=opt_b.id,
                is_correct=False,
            )
        )
        try:
            db.session.commit()
            raise AssertionError("expected an IntegrityError from the unique constraint")
        except IntegrityError:
            db.session.rollback()


def test_conflicting_knowledge_answer_write_fails_closed_not_with_a_500(client, app, monkeypatch):
    # Same concern as the get_or_create_team_mission test below: inserting the "concurrent"
    # answer before calling the route would just hit the route's own pre-existing
    # "already answered?" check and return early -- proving that old code path works, not the
    # new except-IntegrityError one. score_knowledge_correct runs squarely between that
    # pre-check and the route's commit, so hooking it is what actually forces the race.
    #
    # What this actually exercises, discovered while writing it: db.session.refresh(team,
    # with_for_update=True) a few lines above autoflushes this request's own pending `answer`
    # insert immediately -- so by the time this hook's raw connection tries to write a
    # conflicting row, IT is the one that fails (SQLite allows only one writer), not the route's
    # own later commit. The route's except-block then rolls back (discarding this request's own,
    # already-flushed answer) and re-queries -- finding nothing, since neither write survived.
    # That "nobody's answer actually persisted" outcome is real and worth handling on its own:
    # originally this crashed with AttributeError on None.is_correct (a real bug this test
    # caught), now fixed to fail closed with a 409 asking the client to retry.
    import app.blueprints.missions as missions_module

    real_score = missions_module.scoring_service.score_knowledge_correct
    race_state = {}

    def racing_score(*args, **kwargs):
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO team_knowledge_answers "
                    "(team_mission_id, question_id, selected_option_id, is_correct) "
                    "VALUES (:tm, :q, :o, 1)"
                ),
                race_state,
            )
        return real_score(*args, **kwargs)

    monkeypatch.setattr(missions_module.scoring_service, "score_knowledge_correct", racing_score)

    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        mission = Mission(
            title="Node", type="code", narrative="n", cipher_word="X", order_index=0, booth_id=1
        )
        db.session.add_all([team, mission])
        db.session.add(Event(status="running"))
        db.session.commit()

        from app.models import KnowledgeOption, KnowledgeQuestion

        question = KnowledgeQuestion(mission_id=mission.id, question_text="Q?")
        db.session.add(question)
        db.session.flush()
        correct = KnowledgeOption(question_id=question.id, option_text="Right", is_correct=True)
        db.session.add(correct)
        db.session.commit()
        mission_id, question_id, correct_id = mission.id, question.id, correct.id

    client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})
    client.get("/missions/status")  # creates the TeamMission row via get_or_create_team_mission

    with app.app_context():
        team_mission = TeamMission.query.filter_by(mission_id=mission_id).first()
        team_mission_id = team_mission.id
        score_before = Team.query.filter_by(name="Alpha").first().score

    # The racing_score hook (registered above) fires mid-request, once this exact request has
    # already passed its own "already answered?" pre-check -- this is what actually exercises
    # the new except-IntegrityError branch instead of the pre-existing early-return one.
    race_state.update(tm=team_mission_id, q=question_id, o=correct_id)

    res = client.post(
        f"/missions/knowledge-check/{question_id}/answer", json={"option_id": correct_id}
    )
    # The real bug: this used to be an unhandled 500 (AttributeError on None.is_correct). Fixed
    # to fail closed instead -- a 409 telling the client to retry, never a crash, and critically,
    # never a fabricated "you got it right" response for an answer nothing actually recorded.
    assert res.status_code == 409

    with app.app_context():
        assert (
            TeamKnowledgeAnswer.query.filter_by(
                team_mission_id=team_mission_id, question_id=question_id
            ).count()
            == 0
        )
        # Neither the route's own (rolled back) attempt nor the conflicting raw write left a
        # score behind -- a clean failure, not a partial or double one.
        assert Team.query.filter_by(name="Alpha").first().score == score_before
        # The raw-connection "concurrent" insert deliberately bypasses scoring (it's simulating
        # only the row-level race, not re-running score_knowledge_correct) -- the real assertion
        # is that THIS request's own attempt didn't score on top of it once it saw the row.
        assert Team.query.filter_by(name="Alpha").first().score == score_before


def test_get_or_create_team_mission_is_idempotent_under_a_concurrent_creation(app, monkeypatch):
    # The vulnerable window is between get_or_create_team_mission's OWN "does this exist yet?"
    # check (which must see nothing, or this test would exercise the pre-existing "already
    # exists" branch instead of the new one) and its commit. audit.log() already runs squarely
    # inside that window -- monkeypatching it to land the "concurrent" insert there, instead of
    # before calling the method at all, is what actually forces execution into the new
    # except-IntegrityError branch rather than short-circuiting on the pre-check.
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        mission = Mission(title="Node", type="code", narrative="n", cipher_word="X", order_index=0)
        db.session.add_all([team, mission])
        db.session.commit()
        team_id, mission_id = team.id, mission.id

        service = MissionService()
        real_log = service.audit.log
        call_count = {"n": 0}

        def racing_log(*args, **kwargs):
            # Only race on the first call -- a real race happens once, not on every retry, and
            # get_or_create_team_mission's own bounded-retry guard depends on the conflict not
            # persisting indefinitely (exactly like a real one wouldn't).
            call_count["n"] += 1
            if call_count["n"] == 1:
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO team_missions (team_id, mission_id, status, hints_taken) "
                            "VALUES (:t, :m, 'in_progress', 0)"
                        ),
                        {"t": team_id, "m": mission_id},
                    )
            return real_log(*args, **kwargs)

        monkeypatch.setattr(service.audit, "log", racing_log)

        team = Team.query.get(team_id)
        mission = Mission.query.get(mission_id)
        result = service.get_or_create_team_mission(team, mission)

        assert result is not None
        assert TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).count() == 1
