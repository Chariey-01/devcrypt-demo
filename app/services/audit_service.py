import logging

from flask import has_request_context
from flask import request as flask_request

from ..extensions import db
from ..models import EventLog

logger = logging.getLogger("devcrypt.audit")


class AuditService:
    def log(
        self, actor, actor_role, action, target_type=None, target_id=None, metadata=None,
        team_id=None, result=None, score_delta=None,
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
