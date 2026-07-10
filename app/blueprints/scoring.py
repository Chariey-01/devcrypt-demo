from flask import Blueprint, jsonify

from ..decorators import current_team, team_required
from ..models import Mission

scoring_bp = Blueprint("scoring", __name__, url_prefix="/scoring")


@scoring_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@scoring_bp.route("/breakdown")
@team_required
def breakdown():
    team = current_team()
    missions = Mission.query.order_by(Mission.order_index).all()
    tm_map = {tm.mission_id: tm for tm in team.team_missions}
    rows = []
    for mission in missions:
        team_mission = tm_map.get(mission.id)
        rows.append(
            {
                "mission": mission.title,
                "status": team_mission.status if team_mission else "not_started",
                "score": team_mission.score if team_mission else 0,
                "integrity_delta": team_mission.integrity_delta if team_mission else 0,
                "attempts": team_mission.attempts if team_mission else 0,
                "hint_used": team_mission.hint_used if team_mission else False,
            }
        )
    return jsonify({"team_score": team.score, "team_integrity": team.integrity, "missions": rows})
