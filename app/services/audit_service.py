import logging

from flask import has_request_context
from flask import request as flask_request

from ..extensions import db
from ..models import EventLog, Team

logger = logging.getLogger("devcrypt.audit")


class AuditService:
    def log(
        self, actor, actor_role, action, target_type=None, target_id=None, metadata=None,
        team_id=None, result=None, score_delta=None, event_id=None,
    ):
        entry = EventLog(
            actor_id=getattr(actor, "id", None),
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            event_metadata=metadata,
            team_id=team_id,
            result=result,
            score_delta=score_delta,
            # Auto-resolved (like ip_address/user_agent below) rather than threaded through
            # every one of this method's ~30 call sites individually -- explicit event_id is
            # still honored for the rare caller that already knows it precisely.
            event_id=event_id if event_id is not None else self._resolve_event_id(actor, team_id),
            # has_request_context() guard: every real call site today runs inside a request, but
            # this keeps AuditService safe to call from a script/shell context too.
            ip_address=flask_request.remote_addr if has_request_context() else None,
            user_agent=(
                (flask_request.user_agent.string or "")[:255] if has_request_context() else None
            ),
        )
        db.session.add(entry)
        # Every EventLog row (GM/agent/officer action) also gets a text log line for free —
        # the EventLog table is already visible in the GM dashboard, this is for the process
        # log (Railway) so event-day debugging doesn't require a DB query mid-incident.
        logger.info(
            "audit actor=%r role=%s action=%s target=%s:%s meta=%r",
            getattr(actor, "email", None) or getattr(actor, "name", None),
            actor_role,
            action,
            target_type,
            target_id,
            metadata,
        )
        return entry

    def _resolve_event_id(self, actor, team_id):
        # Cheapest, most specific signal first: the team this log entry is actually about.
        if team_id is not None:
            team = Team.query.get(team_id)
            if team is not None and team.event_id is not None:
                return team.event_id
        # Falls back to whichever team is making the current request, if any (covers call
        # sites -- e.g. hint_requested -- that pass team identity in metadata rather than
        # team_id).
        if has_request_context():
            from ..decorators import current_team

            team = current_team()
            if team is not None and team.event_id is not None:
                return team.event_id
        # A staff actor locked to one event.
        if getattr(actor, "event_id", None):
            return actor.event_id
        # Last resort: whichever event is currently active -- correct today since only one
        # event can exist before Phase 1c's Event CRUD, and still the right default afterward
        # for an actor/team with no more specific event of their own.
        from .event_service import EventService

        return EventService().get_active_event().id
