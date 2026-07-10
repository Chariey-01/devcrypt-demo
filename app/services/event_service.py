from datetime import datetime

from ..extensions import db
from ..models import EventState


class EventService:
    def get_state(self):
        state = EventState.query.get(1)
        if not state:
            state = EventState(id=1, status="not_started")
            db.session.add(state)
            db.session.commit()
        return state

    def start(self):
        state = self.get_state()
        state.status = "running"
        state.started_at = datetime.utcnow()
        db.session.commit()
        return state

    def pause(self):
        state = self.get_state()
        state.status = "paused"
        db.session.commit()
        return state

    def end(self):
        state = self.get_state()
        state.status = "ended"
        db.session.commit()
        return state

    def broadcast(self, message):
        state = self.get_state()
        state.broadcast_message = message
        state.broadcast_at = datetime.utcnow()
        db.session.commit()
        return state
