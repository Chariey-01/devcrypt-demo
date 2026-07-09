from ..extensions import db
from ..models import Team


class TeamRepository:
    def create_team(self, name, key):
        team = Team(name=name)
        team.set_key(key)
        db.session.add(team)
        db.session.commit()
        return team

    def get_team_by_key(self, key):
        # key_hash is bcrypt-salted, so it can't be looked up by equality;
        # verify against each row instead. Fine at demo/event scale (NFR-01: ~30 teams).
        for team in Team.query.all():
            if team.check_key(key):
                return team
        return None

    def list_all(self):
        return Team.query.order_by(Team.name).all()
