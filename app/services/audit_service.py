import logging

from ..extensions import db
from ..models import EventLog

logger = logging.getLogger("devcrypt.audit")


class AuditService:
    def log(self, actor, actor_role, action, target_type=None, target_id=None, metadata=None):
        entry = EventLog(
            actor_id=getattr(actor, "id", None),
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            event_metadata=metadata,
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
