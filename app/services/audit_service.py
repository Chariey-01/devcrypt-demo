from ..extensions import db
from ..models import EventLog


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
        return entry
