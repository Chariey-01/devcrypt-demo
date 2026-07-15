from datetime import datetime

from ..extensions import db
from ..models import EventState
from ..sockets import notify_global


class EventService:
    def get_state(self):
        state = EventState.query.get(1)
        if not state:
            # "draft" only ever applies to a brand-new install — existing deployments
            # already have a row (typically "not_started" or later) and are unaffected.
            # Every check elsewhere in the app already only asks "status == running", so
            # "draft" blocks play identically to "not_started" without new branches.
            state = EventState(id=1, status="draft")
            db.session.add(state)
            db.session.commit()
        return state

    def publish(self):
        state = self.get_state()
        if state.status == "draft":
            state.status = "not_started"
        db.session.commit()
        return state

    def archive(self):
        state = self.get_state()
        state.status = "archived"
        db.session.commit()
        return state

    def start(self):
        state = self.get_state()
        state.status = "running"
        state.started_at = datetime.utcnow()
        db.session.commit()
        notify_global("event_start")
        return state

    def pause(self):
        state = self.get_state()
        state.status = "paused"
        db.session.commit()
        notify_global("event_pause")
        return state

    def end(self):
        state = self.get_state()
        state.status = "ended"
        db.session.commit()
        notify_global("event_end")
        return state

    def broadcast(self, message):
        state = self.get_state()
        state.broadcast_message = message
        state.broadcast_at = datetime.utcnow()
        db.session.commit()
        notify_global("broadcast")
        return state
