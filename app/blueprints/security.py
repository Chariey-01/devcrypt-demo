from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db
from ..models import ClearanceStamp, Team
from ..services.analytics_service import AnalyticsService
from ..services.audit_service import AuditService
from ..services.scoring_service import ScoringService
from ..sockets import notify_global, notify_mod

security_bp = Blueprint("security", __name__, url_prefix="/security")

scoring_service = ScoringService()
audit_service = AuditService()
analytics_service = AnalyticsService()


@security_bp.route("/")
@login_required
@roles_required("security_officer")
def dashboard():
    teams = Team.query.order_by(Team.name).all()
    return render_template("security/dashboard.html", teams=teams)


@security_bp.route("/data")
@login_required
@roles_required("security_officer")
def data():
    teams = Team.query.order_by(Team.name).all()
    return jsonify(
        {
            "teams": [
                {
                    "id": team.id,
                    "name": team.name,
                    "stamps": [s.checkpoint_id for s in team.clearance_stamps],
                }
                for team in teams
            ]
        }
    )


@security_bp.route("/stamp", methods=["POST"])
@login_required
@roles_required("security_officer")
def issue_stamp():
    team_id = int(request.form["team_id"])
    checkpoint_id = int(request.form["checkpoint_id"])
    notes = request.form.get("notes", "")
    team = Team.query.get_or_404(team_id)

    if any(stamp.checkpoint_id == checkpoint_id for stamp in team.clearance_stamps):
        flash(f"Checkpoint {checkpoint_id} already stamped for {team.name}.", "error")
        return redirect(url_for("security.dashboard"))

    stamp = ClearanceStamp(
        team_id=team.id, officer_id=current_user.id, checkpoint_id=checkpoint_id, notes=notes
    )
    db.session.add(stamp)
    scoring_service.score_checkpoint(team)
    audit_service.log(current_user, "security_officer", "clearance_stamp", "team", team.id)
    db.session.commit()
    notify_mod("clearance_stamp")
    analytics_service.snapshot_leaderboard()
    notify_global("leaderboard_refresh")

    flash(f"Clearance stamp {checkpoint_id} issued to {team.name}.", "success")
    return redirect(url_for("security.dashboard"))
