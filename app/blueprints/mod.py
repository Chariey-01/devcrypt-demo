import base64
import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db
from ..models import CodeSubmission, EventLog, Mission, Team, TeamMember, TeamMission, User
from ..repositories.team_repo import TeamRepository
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
event_service = EventService()
team_repo = TeamRepository()


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
    missions = Mission.query.order_by(Mission.order_index).all()
    rows = []
    for team in teams:
        missions_done = sum(1 for tm in team.team_missions if tm.status in ("passed", "overridden"))
        overridden = any(tm.status == "overridden" for tm in team.team_missions)
        current, _ = mission_service.current_mission_for(team, missions)
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
                "status": "finished" if missions_done >= 6 else ("overridden" if overridden else "active"),
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
        }
    )


@mod_bp.route("/team/<int:team_id>")
@login_required
@roles_required("game_master")
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    tm_ids = [tm.id for tm in team.team_missions]
    logs = EventLog.query.filter(
        (EventLog.target_type == "team_mission") & (EventLog.target_id.in_(tm_ids))
        if tm_ids
        else (EventLog.target_type == "team") & (EventLog.target_id == team.id)
    ).order_by(EventLog.logged_at.desc()).all()
    return render_template("mod/team_detail.html", team=team, logs=logs)


@mod_bp.route("/missions")
@login_required
@roles_required("game_master")
def list_missions():
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
    audit_service.log(current_user, "game_master", "team_created", "team", team.id)
    db.session.commit()
    return jsonify({"id": team.id, "name": team.name, "key": key}), 201


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
    audit_service.log(current_user, "game_master", "starting_booth_set", "team", team.id)
    db.session.commit()
    return jsonify({"ok": True, "starting_mission_id": team.starting_mission_id})


@mod_bp.route("/credentials/generate", methods=["POST"])
@login_required
@roles_required("game_master")
def generate_credential():
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required."}), 400

    if kind == "team":
        team = Team.query.filter_by(name=name).first()
        secret = generate_team_key()
        if team is None:
            team = team_repo.create_team(name, secret)
        else:
            team.set_key(secret)
        login_path = "/auth/team-login"
        qr_lines = [f"DevCrypt Team: {name}", f"Key: {secret}"]
    elif kind in ("game_master", "booth_agent", "security_officer"):
        user = User.query.filter_by(email=name).first()
        secret = generate_password()
        if user is None:
            user = User(email=name, role=kind)
            db.session.add(user)
        user.set_password(secret)
        login_path = "/auth/login"
        qr_lines = [f"DevCrypt Staff ({kind})", f"Email: {name}", f"Password: {secret}"]
    else:
        return jsonify({"error": "kind must be 'team', 'game_master', 'booth_agent', or 'security_officer'."}), 400

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


@mod_bp.route("/override-score/<int:team_mission_id>", methods=["POST"])
@login_required
@roles_required("game_master")
def override_score(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    data = request.get_json(silent=True) or {}
    try:
        new_score = int(data.get("score"))
    except (TypeError, ValueError):
        return jsonify({"error": "score must be an integer."}), 400

    delta = new_score - team_mission.score
    team_mission.score = new_score
    team_mission.team.score = max(0, team_mission.team.score + delta)
    audit_service.log(
        current_user, "game_master", "score_override", "team_mission", team_mission.id, metadata=str(new_score)
    )
    db.session.commit()
    notify_team(team_mission.team_id, "score_override")
    notify_mod("score_override")
    notify_global("leaderboard_refresh")
    return jsonify({"ok": True, "score": team_mission.score, "team_score": team_mission.team.score})


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
    if team_mission.status in ("passed", "overridden"):
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
