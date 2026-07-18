from datetime import datetime

from flask import Blueprint, jsonify, render_template

from ..models import Mission, Team
from ..services.event_service import EventService
from ..services.mission_service import MissionService

leaderboard_bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")
mission_service = MissionService()
event_service = EventService()


@leaderboard_bp.route("/")
def leaderboard():
    return render_template("leaderboard.html")


@leaderboard_bp.route("/data")
def data():
    if not event_service.get_state().leaderboard_public:
        return jsonify({"hidden": True, "leaderboard": []})

    teams = Team.query.all()
    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    total_missions = len(missions)
    rows = []
    for team in teams:
        missions_done = [tm for tm in team.team_missions if tm.status in ("passed", "overridden")]
        overridden = any(tm.status == "overridden" for tm in team.team_missions)
        current, _ = mission_service.current_mission_for(team, missions)
        if total_missions and len(missions_done) >= total_missions:
            status = "finished"
            current_mission = "Grid Core Restored"
        elif overridden:
            status = "overridden"
            current_mission = current.title if current else "—"
        else:
            status = "active"
            current_mission = current.title if current else "—"

        rows.append(
            {
                "team": team.name,
                "score": team.score,
                "integrity": team.integrity,
                "fragments": len(team.fragments),
                "clearance": len(team.clearance_stamps),
                "current_mission": current_mission,
                "elapsed": (datetime.utcnow() - team.created_at).total_seconds(),
                "status": status,
            }
        )

    rows.sort(key=lambda r: (-r["score"], -r["integrity"], r["elapsed"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    return jsonify({"leaderboard": rows, "total_missions": total_missions})
