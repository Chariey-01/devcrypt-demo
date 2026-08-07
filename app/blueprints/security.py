from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db
from ..models import ClearanceStamp, Team
from ..services.audit_service import AuditService
from ..services.event_service import EventService, event_scope_filter
from ..sockets import notify_mod

security_bp = Blueprint("security", __name__, url_prefix="/security")

audit_service = AuditService()
event_service = EventService()


@security_bp.route("/")
@login_required
@roles_required("security_officer")
def dashboard():
    active_event = event_service.get_active_event()
    teams = Team.query.filter(event_scope_filter(Team, active_event.id)).order_by(Team.name).all()
    return render_template("security/dashboard.html", teams=teams)


@security_bp.route("/data")
@login_required
@roles_required("security_officer")
def data():
    active_event = event_service.get_active_event()
    teams = Team.query.filter(event_scope_filter(Team, active_event.id)).order_by(Team.name).all()
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
    # team_id=team.id (not just target_type/target_id) so this entry actually shows up on the
    # GM's per-team audit view (mod.team_detail): that view's fallback match for pre-team_id
    # legacy rows only matches target_type="team" when a team has zero team_missions -- once a
    # team has started any mission it falls through to a target_type="team_mission" match
    # instead, which a clearance_stamp row (target_type="team") never satisfies. Without
    # team_id set directly, this stamp was invisible on that page for every actively-playing
    # team, the exact case a Security Officer needs it visible for.
    audit_service.log(
        current_user, "security_officer", "clearance_stamp", "team", team.id, team_id=team.id
    )
    db.session.commit()
    notify_mod("clearance_stamp", team.event_id or event_service.get_active_event().id)

    flash(f"Clearance stamp {checkpoint_id} issued to {team.name}.", "success")
    return redirect(url_for("security.dashboard"))
