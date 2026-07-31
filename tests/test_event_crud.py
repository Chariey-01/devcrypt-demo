"""Phase 1c: Event CRUD (create/duplicate/switch/publish/archive) and the "only one event live
at a time" invariant. Phase 1a/1b covered the schema and query scoping; this is the first phase
where a second Event row can actually be created through the product itself, not just directly
via the ORM in a test fixture."""
from app.extensions import db
from app.models import Challenge, Event, Hint, KnowledgeOption, KnowledgeQuestion, Mission, TestCase, User


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    return res


def _setup_gm(app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        db.session.commit()


def test_dashboard_visit_lazily_creates_a_single_draft_event(client, app):
    _setup_gm(app)
    _login_gm(client)
    client.get("/mod/")
    with app.app_context():
        assert Event.query.count() == 1
        assert Event.query.first().status == "draft"


def test_create_event_adds_a_new_draft_and_selects_it(client, app):
    _setup_gm(app)
    _login_gm(client)
    client.get("/mod/")  # event 1

    res = client.post("/mod/events", data={"name": "Career Fair 2027"}, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        events = Event.query.order_by(Event.id).all()
        assert len(events) == 2
        assert events[-1].name == "Career Fair 2027"
        assert events[-1].status == "draft"

    with client.session_transaction() as sess:
        assert sess["gm_event_id"] == events[-1].id


def test_only_one_event_can_be_published_at_a_time(client, app):
    _setup_gm(app)
    _login_gm(client)
    client.get("/mod/")
    client.post("/mod/event/publish")
    client.post("/mod/event/start")  # event 1 now running

    client.post("/mod/events", data={"name": "Career Fair 2027"})
    with app.app_context():
        event2_id = Event.query.order_by(Event.id.desc()).first().id

    client.post("/mod/events/switch", data={"event_id": str(event2_id)})
    res = client.post("/mod/event/publish", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        assert Event.query.get(event2_id).status == "draft"  # blocked, unchanged


def test_ending_the_active_event_lets_the_other_publish(client, app):
    _setup_gm(app)
    _login_gm(client)
    client.get("/mod/")
    client.post("/mod/event/publish")
    client.post("/mod/event/start")
    with app.app_context():
        event1_id = Event.query.first().id

    client.post("/mod/events", data={"name": "Career Fair 2027"})
    with app.app_context():
        event2_id = Event.query.order_by(Event.id.desc()).first().id
    client.post("/mod/events/switch", data={"event_id": str(event2_id)})

    # Still blocked while event 1 is running.
    client.post("/mod/event/publish")
    with app.app_context():
        assert Event.query.get(event2_id).status == "draft"

    # End event 1 (switch back, end it, switch forward again).
    client.post("/mod/events/switch", data={"event_id": str(event1_id)})
    client.post("/mod/event/end")
    client.post("/mod/events/switch", data={"event_id": str(event2_id)})
    client.post("/mod/event/publish")
    with app.app_context():
        assert Event.query.get(event2_id).status == "not_started"


def test_switching_events_changes_what_the_dashboard_and_settings_edit(client, app):
    _setup_gm(app)
    _login_gm(client)
    client.get("/mod/")
    with app.app_context():
        event1_id = Event.query.first().id

    client.post("/mod/events", data={"name": "Career Fair 2027"})
    with app.app_context():
        event2_id = Event.query.order_by(Event.id.desc()).first().id

    client.post("/mod/events/switch", data={"event_id": str(event2_id)})
    client.post("/mod/event-settings", data={"name": "Renamed via settings"})

    with app.app_context():
        assert Event.query.get(event2_id).name == "Renamed via settings"
        assert Event.query.get(event1_id).name is None  # untouched


def test_duplicate_event_copies_missions_and_challenge_content_not_teams_or_logs(client, app):
    _setup_gm(app)
    _login_gm(client)
    client.get("/mod/")
    with app.app_context():
        source_event = Event.query.first()
        mission = Mission(
            title="Node", type="code", narrative="n", cipher_word="X",
            booth_id=1, order_index=1, status="published", event_id=source_event.id,
        )
        db.session.add(mission)
        db.session.flush()
        challenge = Challenge(
            mission_id=mission.id, type="code", prompt="p", grading_mode="auto", pass_threshold=80,
        )
        db.session.add(challenge)
        db.session.flush()
        db.session.add(
            TestCase(challenge_id=challenge.id, name="t1", expected_output="6", weight=1, order_index=0)
        )
        db.session.add(Hint(challenge_id=challenge.id, text="hint 1", order_index=0))
        question = KnowledgeQuestion(mission_id=mission.id, question_text="q?", order_index=0)
        db.session.add(question)
        db.session.flush()
        db.session.add(KnowledgeOption(question_id=question.id, option_text="a", is_correct=True))
        db.session.commit()
        source_event_id = source_event.id

    res = client.post(
        f"/mod/events/{source_event_id}/duplicate", data={"name": "2027 copy"}, follow_redirects=True
    )
    assert res.status_code == 200

    with app.app_context():
        new_event = Event.query.filter_by(name="2027 copy").first()
        assert new_event is not None
        assert new_event.status == "draft"

        new_missions = Mission.query.filter_by(event_id=new_event.id).all()
        assert len(new_missions) == 1
        new_mission = new_missions[0]
        assert new_mission.title == "Node"
        assert new_mission.status == "draft"  # always drafted, regardless of source status

        new_challenge = new_mission.challenge
        assert new_challenge is not None
        assert new_challenge.prompt == "p"
        assert len(new_challenge.test_cases) == 1
        assert len(new_challenge.hints) == 1
        assert len(new_mission.knowledge_questions) == 1
        assert len(new_mission.knowledge_questions[0].options) == 1

        # Teams/logs are never duplicated -- a fresh event starts with none.
        from app.models import Team

        assert Team.query.filter_by(event_id=new_event.id).count() == 0
