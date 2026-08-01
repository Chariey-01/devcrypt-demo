"""Phase 1a of the multi-event platform migration: EventState was renamed to Event (same table
data, just no longer forced to id=1), and Team/Mission/User/EventLog gained a nullable
event_id. This phase is meant to be invisible -- the full existing suite passing unmodified is
the main proof of that; these tests pin down the specific new surface area."""

from app.extensions import db
from app.models import Event, EventLog, Mission, Team, User
from app.services.event_service import EventService


def test_get_active_event_auto_creates_exactly_like_the_old_get_state_did(app):
    with app.app_context():
        assert Event.query.count() == 0
        event = EventService().get_active_event()
        assert event.status == "draft"
        assert Event.query.count() == 1
        # Calling again must not create a second row.
        again = EventService().get_active_event()
        assert again.id == event.id


def test_event_id_columns_exist_and_are_nullable_on_every_scoped_model(app):
    with app.app_context():
        event = Event(status="running")
        db.session.add(event)
        db.session.commit()

        team = Team(name="Alpha", score=0, integrity=100, event_id=event.id)
        team.set_key("ALPHA01")
        mission = Mission(
            title="Node",
            type="code",
            narrative="n",
            cipher_word="X",
            booth_id=1,
            order_index=1,
            event_id=event.id,
        )
        gm = User(email="gm@test.local", role="game_master")  # event_id left NULL on purpose
        gm.set_password("pw")
        db.session.add_all([team, mission, gm])
        db.session.commit()

        assert team.event_id == event.id
        assert mission.event_id == event.id
        assert gm.event_id is None  # founding GM accounts aren't locked to one event

        log = EventLog(actor_role="team", action="test_action", event_id=event.id)
        db.session.add(log)
        db.session.commit()
        assert log.event_id == event.id
