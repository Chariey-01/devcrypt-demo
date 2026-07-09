from ..extensions import db
from ..models import Mission


class MissionRepository:
    def list_ordered(self):
        return Mission.query.order_by(Mission.order_index).all()

    def get(self, mission_id):
        return Mission.query.get(mission_id)

    def create_mission(
        self, title, type, narrative, cipher_word, booth_id=None, order_index=0, time_limit=None
    ):
        mission = Mission(
            title=title,
            type=type,
            narrative=narrative,
            cipher_word=cipher_word,
            booth_id=booth_id,
            order_index=order_index,
            time_limit=time_limit,
        )
        db.session.add(mission)
        db.session.commit()
        return mission
