from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db
from ..models import ClearanceStamp, Team
from ..services.audit_service import AuditService
from ..sockets import notify_mod

security_bp = Blueprint("security", __name__, url_prefix="/security")

audit_service = AuditService()


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

    # Security Officer is audit-only: a clearance stamp is a logged record that this team
    # passed physical/security review at this checkpoint, never a scoring action — it must
    # never move a team's score or the leaderboard.
    stamp = ClearanceStamp(
        team_id=team.id, officer_id=current_user.id, checkpoint_id=checkpoint_id, notes=notes
    )
    db.session.add(stamp)
    audit_service.log(current_user, "security_officer", "clearance_stamp", "team", team.id)
    db.session.commit()
    notify_mod("clearance_stamp")

    flash(f"Clearance stamp {checkpoint_id} issued to {team.name}.", "success")
    return redirect(url_for("security.dashboard"))
