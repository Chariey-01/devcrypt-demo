from ..extensions import db
from ..models import Team


class TeamRepository:
    def create_team(self, name, key, event_id=None):
        team = Team(name=name, event_id=event_id)
        team.set_key(key)
        db.session.add(team)
        db.session.commit()
        return team

    def get_team_by_name(self, name, event_id=None):
        # Team names are unique and this is a plain indexed-friendly column
        # comparison, so it stays fast regardless of team count. Only after
        # narrowing to one row do we pay bcrypt's deliberately slow check
        # (measured ~500-700ms) -- doing that per-row across every team
        # (the old approach) does not scale past a couple dozen teams.
        query = Team.query.filter(db.func.lower(Team.name) == name.lower())
        if event_id is not None:
            # A team with no event_id yet (not stamped by every creation path until Phase 1d
            # tightens this to NOT NULL) still matches by bare name -- only two teams that both
            # *do* carry an event_id need it to match. Once every team is reliably stamped,
            # this OR clause stops doing anything and can be dropped.
            query = query.filter(db.or_(Team.event_id == event_id, Team.event_id.is_(None)))
        return query.first()

    def list_all(self):
        return Team.query.order_by(Team.name).all()
