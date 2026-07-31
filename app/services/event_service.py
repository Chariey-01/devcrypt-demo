from datetime import datetime

from ..extensions import db
from ..models import Event, TeamMission
from ..sockets import notify_global


class EventService:
    def get_active_event(self):
        # Phase 1a: there is no Event CRUD yet (that's Phase 1c), so exactly one Event row can
        # ever exist -- this is behaviorally identical to the old singleton get_state(), just
        # renamed ahead of Phase 1c, where "the active event" starts meaning something real
        # (the one event whose status isn't draft/ended/archived, enforced at that point so at
        # most one is ever running/paused at a time). Until then, "most recent row, or create
        # one" reproduces today's exact behavior for the one event that exists.
        event = Event.query.order_by(Event.id.desc()).first()
        if not event:
            # "draft" only ever applies to a brand-new install — existing deployments
            # already have a row (typically "not_started" or later) and are unaffected.
            # Every check elsewhere in the app already only asks "status == running", so
            # "draft" blocks play identically to "not_started" without new branches.
            event = Event(status="draft")
            db.session.add(event)
            db.session.commit()
        return event

    def publish(self):
        state = self.get_active_event()
        if state.status == "draft":
            state.status = "not_started"
        db.session.commit()
        return state

    def archive(self):
        state = self.get_active_event()
        state.status = "archived"
        db.session.commit()
        return state

    def start(self):
        state = self.get_active_event()
        if state.status == "paused" and state.paused_at is not None:
            # Resuming, not starting fresh -- give back exactly the wall-clock duration the
            # event was paused for, to every mission still in progress, so a pause never eats
            # into a team's remaining time. A team that hasn't reached a booth yet (started_at
            # still NULL) is untouched -- its clock starts for real the next time it polls,
            # same as MissionService.get_or_create_team_mission handles for a not-yet-started
            # event.
            pause_duration = datetime.utcnow() - state.paused_at
            in_progress = TeamMission.query.filter(
                TeamMission.submitted_at.is_(None), TeamMission.started_at.isnot(None)
            ).all()
            for team_mission in in_progress:
                team_mission.started_at += pause_duration
            state.paused_at = None
        else:
            state.started_at = datetime.utcnow()
        state.status = "running"
        db.session.commit()
        notify_global("event_start")
        return state

    def pause(self):
        state = self.get_active_event()
        state.status = "paused"
        state.paused_at = datetime.utcnow()
        db.session.commit()
        notify_global("event_pause")
        return state

    def end(self):
        state = self.get_active_event()
        state.status = "ended"
        db.session.commit()
        notify_global("event_end")
        return state

    def broadcast(self, message):
        state = self.get_active_event()
        state.broadcast_message = message
        state.broadcast_at = datetime.utcnow()
        db.session.commit()
        notify_global("broadcast")
        return state
