import base64
import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db, limiter
from ..models import (
    Challenge,
    CodeSubmission,
    EventLog,
    FinalFlagConfirmation,
    Mission,
    Team,
    TeamMember,
    TeamMission,
    User,
)
from ..repositories.team_repo import TeamRepository
from ..services.admin_reset_service import AdminResetService
from ..services.analytics_service import AnalyticsService
from ..services.audit_service import AuditService
from ..services.cipher_service import CipherService
from ..services.credential_service import generate_password, generate_team_key
from ..services.event_service import EventService
from ..services.mission_service import MissionService
from ..services.scoring_service import ScoringService
from ..sockets import notify_global, notify_mod, notify_team

mod_bp = Blueprint("mod", __name__, url_prefix="/mod")

scoring_service = ScoringService()
cipher_service = CipherService()
audit_service = AuditService()
mission_service = MissionService(scoring=scoring_service, cipher=cipher_service, audit=audit_service)
analytics_service = AnalyticsService(mission_service=mission_service)
event_service = EventService()
team_repo = TeamRepository()
admin_reset_service = AdminResetService()


@mod_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@mod_bp.route("/")
@login_required
@roles_required("game_master")
def dashboard():
    return render_template("mod/dashboard.html", state=event_service.get_state())


@mod_bp.route("/data")
@login_required
@roles_required("game_master")
def data():
    teams = Team.query.order_by(Team.name).all()
    # Published only — must match what the player's own /missions/status sees, so the GM
    # dashboard's "current mission" column never shows a draft mission a team can't actually
    # reach (mod.py:99's list_missions is intentionally unfiltered — GMs manage drafts too).
    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    total_missions = len(missions)
    rows = []
    for team in teams:
        missions_done = sum(
            1 for tm in team.team_missions if tm.status in ("passed", "overridden", "soft_locked")
        )
        overridden = any(tm.status == "overridden" for tm in team.team_missions)
        soft_locked_missions = [tm.mission.title for tm in team.team_missions if tm.status == "soft_locked"]
        current, _ = mission_service.current_mission_for(team, missions)
        finished = total_missions and missions_done >= total_missions
        rows.append(
            {
                "id": team.id,
                "name": team.name,
                "score": team.score,
                "integrity": team.integrity,
                "current_mission": current.title if current else "Finished",
                "missions_done": missions_done,
                "fragments": len(team.fragments),
                "clearance": len(team.clearance_stamps),
                "hints_used": team.hints_used,
                "status": "finished" if finished else ("overridden" if overridden else "active"),
                "soft_locked_missions": soft_locked_missions,
                "elapsed": (datetime.utcnow() - team.created_at).total_seconds(),
                "starting_mission_id": team.starting_mission_id,
                "members": [{"id": m.id, "name": m.name, "email": m.email} for m in team.members],
            }
        )
    state = event_service.get_state()
    return jsonify(
        {
            "teams": rows,
            "event_status": state.status,
            "broadcast": state.broadcast_message,
            "total_missions": total_missions,
        }
    )


@mod_bp.route("/team/<int:team_id>")
@login_required
@roles_required("game_master")
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    tm_ids = [tm.id for tm in team.team_missions]
    # EventLog.team_id == team.id covers every row logged since the structured-audit-fields
    # migration; the target_type/target_id clause is kept alongside it (as an OR, not a
    # replacement) so older rows -- logged before team_id existed and never backfilled -- still
    # show up here too.
    legacy_match = (
        (EventLog.target_type == "team_mission") & (EventLog.target_id.in_(tm_ids))
        if tm_ids
        else (EventLog.target_type == "team") & (EventLog.target_id == team.id)
    )
    logs = EventLog.query.filter(
        db.or_(EventLog.team_id == team.id, legacy_match)
    ).order_by(EventLog.logged_at.desc()).all()
    return render_template("mod/team_detail.html", team=team, logs=logs, table_id="log-grid")


@mod_bp.route("/activity")
@login_required
@roles_required("game_master")
def activity():
    logs = EventLog.query.order_by(EventLog.logged_at.desc()).limit(100).all()
    return jsonify(
        {
            "logs": [
                {
                    "when": log.logged_at.strftime("%H:%M:%S"),
                    "actor_role": log.actor_role,
                    "action": log.action,
                    "metadata": log.event_metadata,
                    "team": log.team.name if log.team_id else None,
                    "result": log.result,
                    "score_delta": log.score_delta,
                }
                for log in logs
            ]
        }
    )


@mod_bp.route("/missions")
@login_required
@roles_required("game_master")
def list_missions():
    # Deliberately unfiltered by status — GMs manage draft/archived missions too (e.g. setting
    # a starting booth or assigning an agent before the mission is published).
    missions = Mission.query.order_by(Mission.order_index).all()
    return jsonify(
        {
            "missions": [
                {"id": m.id, "title": m.title, "booth_id": m.booth_id, "owner_agent_id": m.owner_agent_id}
                for m in missions
            ]
        }
    )


@mod_bp.route("/team", methods=["POST"])
@login_required
@roles_required("game_master")
def create_team():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required."}), 400
    if Team.query.filter_by(name=name).first():
        return jsonify({"error": "A team with that name already exists."}), 409
    key = generate_team_key()
    team = team_repo.create_team(name, key)
    audit_service.log(current_user, "game_master", "team_created", "team", team.id, team_id=team.id)
    db.session.commit()
    return jsonify({"id": team.id, "name": team.name, "key": key}), 201


@mod_bp.route("/team/<int:team_id>", methods=["PATCH"])
@login_required
@roles_required("game_master")
def rename_team(team_id):
    team = Team.query.get_or_404(team_id)
    data = request.get_json(silent=True) or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"error": "name is required."}), 400
    existing = Team.query.filter(Team.name == new_name, Team.id != team.id).first()
    if existing:
        return jsonify({"error": "A team with that name already exists."}), 409
    old_name = team.name
    team.name = new_name
    audit_service.log(
        current_user, "game_master", "team_renamed", "team", team.id,
        team_id=team.id, metadata=f"{old_name} -> {new_name}",
    )
    db.session.commit()
    notify_mod("team_renamed")
    return jsonify({"id": team.id, "name": team.name})


@mod_bp.route("/team/<int:team_id>", methods=["DELETE"])
@login_required
@roles_required("game_master")
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    audit_service.log(current_user, "game_master", "team_deleted", "team", team.id, metadata=team.name)
    admin_reset_service.delete_team(team)
    notify_mod("team_deleted")
    notify_global("leaderboard_refresh")
    return jsonify({"ok": True})


@mod_bp.route("/team/<int:team_id>/reset", methods=["POST"])
@login_required
@roles_required("game_master")
def reset_team(team_id):
    team = Team.query.get_or_404(team_id)
    audit_service.log(
        current_user, "game_master", "team_progress_reset", "team", team.id,
        team_id=team.id, metadata=team.name,
    )
    admin_reset_service.reset_team(team)
    notify_team(team.id, "team_reset")
    notify_mod("team_reset")
    notify_global("leaderboard_refresh")
    return jsonify({"ok": True})


@mod_bp.route("/teams/reset-all", methods=["POST"])
@login_required
@roles_required("game_master")
def reset_all_teams():
    # Full clean slate (every team's progress, leaderboard history, and the entire
    # activity log) — the moment testing ends and the real event begins, not a mid-event
    # single-team retry (that's reset_team above). The log entry below is written AFTER
    # reset_all_teams() clears EventLog, so it survives as the one record that a reset
    # happened, instead of being wiped by its own action.
    team_count = Team.query.count()
    admin_reset_service.reset_all_teams()
    audit_service.log(current_user, "game_master", "all_teams_reset", metadata=f"{team_count} teams")
    db.session.commit()
    notify_mod("teams_reset_all")
    notify_global("leaderboard_refresh")
    return jsonify({"ok": True, "teams_reset": team_count})


@mod_bp.route("/team/<int:team_id>/member", methods=["POST"])
@login_required
@roles_required("game_master")
def add_team_member(team_id):
    team = Team.query.get_or_404(team_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required."}), 400
    member = TeamMember(team_id=team.id, name=name, email=(data.get("email") or "").strip() or None)
    db.session.add(member)
    db.session.commit()
    return jsonify({"id": member.id, "name": member.name, "email": member.email}), 201


@mod_bp.route("/team/<int:team_id>/member/<int:member_id>", methods=["DELETE"])
@login_required
@roles_required("game_master")
def remove_team_member(team_id, member_id):
    member = TeamMember.query.get_or_404(member_id)
    if member.team_id != team_id:
        abort(404)
    db.session.delete(member)
    db.session.commit()
    return jsonify({"ok": True})


@mod_bp.route("/team/<int:team_id>/starting-booth", methods=["POST"])
@login_required
@roles_required("game_master")
def set_starting_booth(team_id):
    team = Team.query.get_or_404(team_id)
    data = request.get_json(silent=True) or {}
    mission_id = data.get("mission_id")
    if mission_id:
        Mission.query.get_or_404(mission_id)
    team.starting_mission_id = mission_id or None
    audit_service.log(current_user, "game_master", "starting_booth_set", "team", team.id, team_id=team.id)
    db.session.commit()
    return jsonify({"ok": True, "starting_mission_id": team.starting_mission_id})


@mod_bp.route("/teams/distribute-booths", methods=["POST"])
@login_required
@roles_required("game_master")
def distribute_booths():
    # Round-robin over published missions ordered by order_index, teams ordered by id (their
    # creation order) — the simplest reliable algorithm that satisfies "distribute evenly,
    # minimise two teams starting at the same booth": team i gets missions[i % booth_count],
    # so consecutive teams always land on different booths and every booth gets either
    # floor(team_count/booth_count) or one more teams assigned as a starting point. This is a
    # one-time initial-assignment tool (run once before the event starts, or again to
    # reshuffle) — it does not track live queue/occupancy state, since that would need a
    # different mechanism (booth check-in) this event doesn't have yet.
    teams = Team.query.order_by(Team.id).all()
    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    if not teams or not missions:
        return jsonify({"error": "Need at least one team and one published booth."}), 400

    assignments = {}
    for i, team in enumerate(teams):
        mission = missions[i % len(missions)]
        team.starting_mission_id = mission.id
        assignments[team.id] = {"team": team.name, "starting_mission_id": mission.id, "booth": mission.title}

    audit_service.log(
        current_user, "game_master", "booths_distributed",
        metadata=f"{len(teams)} teams across {len(missions)} booths",
    )
    db.session.commit()
    notify_mod("booths_distributed")
    return jsonify({"ok": True, "assignments": list(assignments.values())})


@mod_bp.route("/credentials/generate", methods=["POST"])
@login_required
@roles_required("game_master")
@limiter.limit("30 per minute")
def generate_credential():
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required."}), 400

    if kind == "team":
        team = Team.query.filter_by(name=name).first()
        # Distinguish a moderator reissuing an existing team's key (the live-event recovery
        # path that prompted this audit work) from creating a brand-new team, before
        # team_repo.create_team/set_key below changes which of those is still true.
        reissuing = team is not None
        secret = generate_team_key()
        if team is None:
            team = team_repo.create_team(name, secret)
        else:
            team.set_key(secret)
        login_path = "/auth/team-login"
        qr_lines = [f"DevCrypt Team: {name}", f"Key: {secret}"]
    elif kind in ("game_master", "booth_agent", "security_officer"):
        user = User.query.filter_by(email=name).first()
        if user is not None and user.role != kind:
            return jsonify(
                {"error": f"{name} is already registered as a different role ({user.role})."}
            ), 409
        secret = generate_password()
        if user is None:
            user = User(email=name, role=kind)
            db.session.add(user)
        full_name = (data.get("full_name") or "").strip()
        if full_name:
            user.full_name = full_name
        user.set_password(secret)
        login_path = "/auth/login"
        qr_lines = [f"DevCrypt Staff ({kind})", f"Email: {name}", f"Password: {secret}"]
    else:
        return jsonify({"error": "kind must be 'team', 'game_master', 'booth_agent', or 'security_officer'."}), 400

    if kind == "team":
        action = "team_key_reissued" if reissuing else "team_created_with_key"
        audit_service.log(current_user, "game_master", action, "team", team.id, team_id=team.id, metadata=name)
    else:
        audit_service.log(current_user, "game_master", "credentials_generated", metadata=f"{kind}:{name}")
    db.session.commit()

    qr_data_uri = None
    try:
        import qrcode

        img = qrcode.make("\n".join(qr_lines))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        pass

    return jsonify({"login": name, "secret": secret, "login_path": login_path, "qr_data_uri": qr_data_uri})


@mod_bp.route("/agents")
@login_required
@roles_required("game_master")
def list_agents():
    agents = User.query.filter_by(role="booth_agent").order_by(User.email).all()
    rows = [
        {
            "id": agent.id,
            "email": agent.email,
            "full_name": agent.full_name,
            "is_active": agent.is_active,
            "last_login_at": agent.last_login_at.isoformat() if agent.last_login_at else None,
            "missions": [
                {
                    "id": m.id,
                    "title": m.title,
                    "grading_mode": m.challenge.grading_mode if m.challenge else None,
                }
                for m in Mission.query.filter_by(owner_agent_id=agent.id).all()
            ],
        }
        for agent in agents
    ]
    return jsonify({"agents": rows})


@mod_bp.route("/agents/<int:agent_id>", methods=["PUT"])
@login_required
@roles_required("game_master")
def update_agent(agent_id):
    agent = User.query.filter_by(id=agent_id, role="booth_agent").first_or_404()
    data = request.get_json(silent=True) or {}
    if "full_name" in data:
        agent.full_name = (data["full_name"] or "").strip() or None
    if "email" in data:
        new_email = (data["email"] or "").strip().lower()
        if not new_email:
            return jsonify({"error": "email cannot be blank."}), 400
        if User.query.filter(User.id != agent.id, User.email == new_email).first():
            return jsonify({"error": "That email is already in use."}), 409
        agent.email = new_email
    audit_service.log(current_user, "game_master", "agent_updated", "user", agent.id)
    db.session.commit()
    return jsonify({"ok": True, "id": agent.id, "email": agent.email, "full_name": agent.full_name})


@mod_bp.route("/agents/<int:agent_id>/active", methods=["POST"])
@login_required
@roles_required("game_master")
def set_agent_active(agent_id):
    agent = User.query.filter_by(id=agent_id, role="booth_agent").first_or_404()
    data = request.get_json(silent=True) or {}
    agent.is_active = bool(data.get("is_active", True))
    action = "agent_activated" if agent.is_active else "agent_deactivated"
    audit_service.log(current_user, "game_master", action, "user", agent.id, metadata=agent.email)
    db.session.commit()
    return jsonify({"ok": True, "is_active": agent.is_active})


@mod_bp.route("/agents/<int:agent_id>", methods=["DELETE"])
@login_required
@roles_required("game_master")
def delete_agent(agent_id):
    agent = User.query.filter_by(id=agent_id, role="booth_agent").first_or_404()
    owned = Mission.query.filter_by(owner_agent_id=agent.id).count()
    if owned:
        return jsonify(
            {"error": f"This agent still owns {owned} booth(s) — reassign or delete those first."}
        ), 409
    email = agent.email
    db.session.delete(agent)
    audit_service.log(current_user, "game_master", "agent_deleted", metadata=email)
    db.session.commit()
    return jsonify({"ok": True})


@mod_bp.route("/mission/<int:mission_id>/assign-agent", methods=["POST"])
@login_required
@roles_required("game_master")
def assign_agent(mission_id):
    mission = Mission.query.get_or_404(mission_id)
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    if agent_id:
        agent = User.query.get_or_404(agent_id)
        if agent.role != "booth_agent":
            return jsonify({"error": "User is not a booth agent."}), 400
        if not agent.is_active:
            return jsonify({"error": "That agent is deactivated — reactivate them before assigning a booth."}), 400
        mission.owner_agent_id = agent.id
    else:
        mission.owner_agent_id = None
    audit_service.log(current_user, "game_master", "agent_assigned", "mission", mission.id)
    db.session.commit()
    return jsonify({"ok": True, "owner_agent_id": mission.owner_agent_id})


@mod_bp.route("/submissions")
@login_required
@roles_required("game_master")
def list_submissions():
    subs = CodeSubmission.query.order_by(CodeSubmission.id.desc()).limit(50).all()
    rows = [
        {
            "id": s.id,
            "team": s.team_mission.team.name,
            "mission": s.team_mission.mission.title,
            "mode": s.mode,
            "percent_score": s.percent_score,
            "passed_tests": s.passed_tests,
            "total_tests": s.total_tests,
            "passed": s.passed,
            "created_at": s.created_at.isoformat(),
        }
        for s in subs
    ]
    return jsonify({"submissions": rows})


@mod_bp.route("/final-flag/pending")
@login_required
@roles_required("game_master")
def list_final_flag_pending():
    pending = (
        FinalFlagConfirmation.query.filter(FinalFlagConfirmation.confirmed_at.is_(None))
        .order_by(FinalFlagConfirmation.requested_at)
        .all()
    )
    rows = [
        {
            "team_id": c.team_id,
            "team_name": c.team.name,
            "requested_at": c.requested_at.isoformat() if c.requested_at else None,
        }
        for c in pending
    ]
    return jsonify({"pending": rows})


@mod_bp.route("/final-flag/<int:team_id>/confirm", methods=["POST"])
@login_required
@roles_required("game_master")
def confirm_final_flag(team_id):
    confirmation = FinalFlagConfirmation.query.filter_by(team_id=team_id).first_or_404()
    confirmation.confirmed_by = current_user.id
    confirmation.confirmed_at = datetime.utcnow()
    audit_service.log(
        current_user, "game_master", "final_flag_confirmed", "team", team_id,
        team_id=team_id, metadata=confirmation.team.name,
    )
    db.session.commit()
    notify_team(team_id, "final_flag_confirmed")
    notify_mod("final_flag_confirmed")
    return jsonify({"ok": True})


@mod_bp.route("/override-score/<int:team_mission_id>", methods=["POST"])
@login_required
@roles_required("game_master")
def override_score(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    # Once a mission is resolved, its score is immutable through this route — same rule as
    # the other override route (mod.override). A passed (or soft-locked) score must never be
    # silently rewritten; a genuine correction goes through reset-mission first so the change
    # is auditable as a status transition, not an in-place score edit.
    if team_mission.status in ("passed", "overridden", "soft_locked"):
        abort(409)
    try:
        new_score = int(request.form.get("score"))
    except (TypeError, ValueError):
        abort(400)

    delta = new_score - team_mission.score
    team_mission.score = new_score
    team_mission.team.score = max(0, team_mission.team.score + delta)
    audit_service.log(
        current_user, "game_master", "score_override", "team_mission", team_mission.id,
        team_id=team_mission.team_id, score_delta=delta, metadata=str(new_score),
    )
    db.session.commit()
    notify_team(team_mission.team_id, "score_override")
    notify_mod("score_override")
    analytics_service.snapshot_leaderboard()
    notify_global("leaderboard_refresh")
    return redirect(url_for("mod.team_detail", team_id=team_mission.team_id))


@mod_bp.route("/reset-mission/<int:team_mission_id>", methods=["POST"])
@login_required
@roles_required("game_master")
def reset_mission(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    if team_mission.status in ("passed", "overridden", "soft_locked"):
        abort(409)
    team_mission.penalty_until = None
    team_mission.attempts = 0
    team_mission.submission_text = None
    mission_service.unfreeze_submission(team_mission)
    audit_service.log(
        current_user, "game_master", "mission_reset", "team_mission", team_mission.id,
        team_id=team_mission.team_id,
    )
    db.session.commit()
    notify_team(team_mission.team_id, "mission_reset")
    notify_mod("mission_reset")
    return redirect(url_for("mod.team_detail", team_id=team_mission.team_id))


@mod_bp.route("/team-mission/<int:team_mission_id>/extend-timer", methods=["POST"])
@login_required
@roles_required("game_master")
def extend_timer(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    try:
        seconds = int(request.form.get("seconds"))
    except (TypeError, ValueError):
        abort(400)
    if seconds <= 0:
        abort(400)
    if not mission_service.extend_timer(team_mission, seconds, actor=current_user, actor_role="game_master"):
        abort(409)
    return redirect(url_for("mod.team_detail", team_id=team_mission.team_id))


@mod_bp.route("/event-settings", methods=["GET", "POST"])
@login_required
@roles_required("game_master")
def event_settings():
    state = event_service.get_state()
    if request.method == "POST":
        state.name = (request.form.get("name") or "").strip() or None
        state.description = (request.form.get("description") or "").strip() or None
        try:
            state.hint_limit = max(0, int(request.form.get("hint_limit", state.hint_limit)))
        except (TypeError, ValueError):
            pass
        try:
            state.soft_lock_min_attempts = max(
                0, int(request.form.get("soft_lock_min_attempts", state.soft_lock_min_attempts))
            )
        except (TypeError, ValueError):
            pass
        state.leaderboard_public = request.form.get("leaderboard_public") == "on"
        audit_service.log(
            current_user,
            "game_master",
            "event_settings_updated",
            metadata=(
                f"hint_limit={state.hint_limit} leaderboard_public={state.leaderboard_public} "
                f"soft_lock_min_attempts={state.soft_lock_min_attempts}"
            ),
        )
        db.session.commit()
        flash("Event settings saved.", "success")
        return redirect(url_for("mod.event_settings"))

    total_booths = Mission.query.filter_by(status="published").count()
    return render_template("mod/event_settings.html", state=state, total_booths=total_booths)


@mod_bp.route("/event/publish", methods=["POST"])
@login_required
@roles_required("game_master")
def publish_event():
    event_service.publish()
    audit_service.log(current_user, "game_master", "event_publish")
    db.session.commit()
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/event/archive", methods=["POST"])
@login_required
@roles_required("game_master")
def archive_event():
    event_service.archive()
    audit_service.log(current_user, "game_master", "event_archive")
    db.session.commit()
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/event/start", methods=["POST"])
@login_required
@roles_required("game_master")
def start_event():
    event_service.start()
    audit_service.log(current_user, "game_master", "event_start")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/event/pause", methods=["POST"])
@login_required
@roles_required("game_master")
def pause_event():
    event_service.pause()
    audit_service.log(current_user, "game_master", "event_pause")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/event/end", methods=["POST"])
@login_required
@roles_required("game_master")
def end_event():
    event_service.end()
    audit_service.log(current_user, "game_master", "event_end")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/broadcast", methods=["POST"])
@login_required
@roles_required("game_master")
def broadcast():
    message = request.form.get("message", "").strip()
    if message:
        event_service.broadcast(message)
        audit_service.log(current_user, "game_master", "broadcast", metadata=message)
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/override/<int:team_mission_id>", methods=["POST"])
@login_required
@roles_required("game_master")
def override(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    if team_mission.status in ("passed", "overridden", "soft_locked"):
        abort(409)
    mission_service.complete_mission(
        team_mission.team, team_mission, team_mission.mission, "overridden",
        actor=current_user, actor_role="game_master",
    )
    return redirect(url_for("mod.team_detail", team_id=team_mission.team_id))


@mod_bp.route("/export.csv")
@login_required
@roles_required("game_master")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["team", "score", "integrity", "fragments", "clearance_stamps", "missions_passed", "hints_used"]
    )
    for team in Team.query.order_by(Team.name).all():
        writer.writerow(
            [
                team.name,
                team.score,
                team.integrity,
                len(team.fragments),
                len(team.clearance_stamps),
                sum(1 for tm in team.team_missions if tm.status in ("passed", "overridden")),
                team.hints_used,
            ]
        )
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=devcrypt_report.csv"
    return response


@mod_bp.route("/export/submissions.csv")
@login_required
@roles_required("game_master")
def export_submissions_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["team", "mission", "mode", "total_tests", "passed_tests", "percent_score", "passed", "created_at"])
    subs = (
        CodeSubmission.query.join(TeamMission, CodeSubmission.team_mission_id == TeamMission.id)
        .order_by(CodeSubmission.created_at)
        .all()
    )
    for s in subs:
        writer.writerow(
            [
                s.team_mission.team.name,
                s.team_mission.mission.title,
                s.mode,
                s.total_tests,
                s.passed_tests,
                s.percent_score,
                s.passed,
                s.created_at.isoformat(),
            ]
        )
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=devcrypt_submissions.csv"
    return response


@mod_bp.route("/export/challenges.csv")
@login_required
@roles_required("game_master")
def export_challenges_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["mission", "difficulty", "grading_mode", "attempts", "passed", "pass_rate_percent"])
    stats_by_mission = {s["mission_id"]: s for s in analytics_service.challenge_stats()}
    for mission in Mission.query.order_by(Mission.order_index).all():
        challenge = mission.challenge
        stat = stats_by_mission.get(mission.id)
        writer.writerow(
            [
                mission.title,
                challenge.difficulty if challenge else "",
                challenge.grading_mode if challenge else "",
                stat["attempts"] if stat else 0,
                stat["passed"] if stat else 0,
                stat["pass_rate"] if stat else "",
            ]
        )
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=devcrypt_challenges.csv"
    return response


@mod_bp.route("/export/event-stats.csv")
@login_required
@roles_required("game_master")
def export_event_stats_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    pass_fail = analytics_service.pass_fail_counts()
    hint_usage = analytics_service.hint_usage()
    writer.writerow(["metric", "value"])
    writer.writerow(["total_submissions", analytics_service.total_submissions()])
    writer.writerow(["submissions_passed", pass_fail["passed"]])
    writer.writerow(["submissions_failed", pass_fail["failed"]])
    writer.writerow(["average_completion_seconds", analytics_service.average_completion_seconds() or ""])
    writer.writerow(["total_hints_used", hint_usage["total_hints_used"]])
    writer.writerow(["missions_with_hint_used", hint_usage["missions_with_hint_used"]])
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=devcrypt_event_stats.csv"
    return response


@mod_bp.route("/analytics")
@login_required
@roles_required("game_master")
def analytics():
    return render_template("mod/analytics.html")


@mod_bp.route("/analytics/data")
@login_required
@roles_required("game_master")
def analytics_data():
    pass_fail = analytics_service.pass_fail_counts()
    avg_seconds = analytics_service.average_completion_seconds()
    return jsonify(
        {
            "total_submissions": analytics_service.total_submissions(),
            "pass_fail": pass_fail,
            "average_completion_seconds": avg_seconds,
            "hint_usage": analytics_service.hint_usage(),
            "challenge_stats": analytics_service.challenge_stats(),
            "most_failed_challenge": analytics_service.most_failed_challenge(),
        }
    )
