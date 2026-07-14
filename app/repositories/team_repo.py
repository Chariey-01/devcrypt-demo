from ..extensions import db
from ..models import Team


class TeamRepository:
    def create_team(self, name, key):
        team = Team(name=name)
        team.set_key(key)
        db.session.add(team)
        db.session.commit()
        return team

    def get_team_by_name(self, name):
        # Team names are unique and this is a plain indexed-friendly column
        # comparison, so it stays fast regardless of team count. Only after
        # narrowing to one row do we pay bcrypt's deliberately slow check
        # (measured ~500-700ms) -- doing that per-row across every team
        # (the old approach) does not scale past a couple dozen teams.
        return Team.query.filter(db.func.lower(Team.name) == name.lower()).first()

    def list_all(self):
        return Team.query.order_by(Team.name).all()
