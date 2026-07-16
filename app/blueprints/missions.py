import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request

from ..decorators import current_team, team_required
from ..extensions import db
from ..models import CodeSubmission, Mission, TeamMCQAnswer, TeamMission
from ..services.audit_service import AuditService
from ..services.cipher_service import CipherService
from ..services.event_service import EventService
from ..services.grading_service import GradingEngine
from ..services.mission_service import MissionService
from ..services.scoring_service import ScoringService
from ..sockets import notify_mod, notify_team

missions_bp = Blueprint("missions", __name__, url_prefix="/missions")
logger = logging.getLogger("devcrypt.missions")

cipher_service = CipherService()
scoring_service = ScoringService()
mission_service = MissionService(scoring=scoring_service, cipher=cipher_service)
event_service = EventService()
grading_engine = GradingEngine()
audit_service = AuditService()

NARRATIVE = {
    "mcq_correct": "CIPHER LETTER DECODED",
    "mcq_wrong": "SIGNAL UNCLEAR — NODE STILL COMPROMISED",
    "challenge_pass": "NODE SECURED. FRAGMENT ACQUIRED.",
    "challenge_fail": "PATCH REJECTED — VULNERABILITY STILL ACTIVE.",
    "challenge_queued": "SUBMISSION ROUTED TO FIELD AGENT FOR REVIEW.",
    "flag_final": "METAVERSE CORE RESTORED.",
    "cooldown": "NODE ON COOLDOWN.",
}


@missions_bp.route("/play")
@team_required
def play():
    return render_template("player/dashboard.html")


def _serialize_mcq(mcq, team_mission):
    answered = None
    if team_mission:
        answered = next((a for a in team_mission.mcq_answers if a.mcq_id == mcq.id), None)
    return {
        "id": mcq.id,
        "question_text": mcq.question_text,
        "options": [{"id": o.id, "option_text": o.option_text} for o in mcq.options],
        "answered": answered is not None,
        "was_correct": answered.is_correct if answered else None,
        "selected_option_id": answered.selected_option_id if answered else None,
    }


def _hint_text(challenge):
    # Agent-authored hints (Hint rows) take precedence; legacy single hint_text is the
    # fallback for missions that predate the multi-hint authoring flow.
    if challenge.hints:
        return challenge.hints[0].text
    return challenge.hint_text


def _serialize_grading_results(results):
    return [
        {
            "name": r.name,
            "visibility": r.visibility,
            "passed": r.passed,
            "weight": r.weight,
            "failure_message": r.failure_message,
            "input_data": r.input_data,
            "expected_output": r.expected_output,
            "actual_output": r.actual_output,
        }
        for r in results
    ]


def _serialize_challenge(challenge, team_mission):
    options = None
    if challenge.type == "mcq" and challenge.steps:
        options = [line.strip() for line in challenge.steps.splitlines() if line.strip()]
    payload = {
        "type": challenge.type,
        "prompt": challenge.prompt,
        "options": options,
        "hint_text": _hint_text(challenge) if (team_mission and team_mission.hint_used) else None,
        "grading_mode": challenge.grading_mode,
    }
    if challenge.grading_mode == "auto":
        payload.update(
            {
                "title": challenge.title,
                "language": challenge.language,
                "function_signature": challenge.function_signature,
                "starter_code": challenge.starter_code,
                "max_attempts": challenge.max_attempts,
                "attempts_used": team_mission.attempts if team_mission else 0,
            }
        )
    return payload


@missions_bp.route("/status")
@team_required
def status():
    team = current_team()
    state = event_service.get_state()
    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, team_mission = mission_service.current_mission_for(team, missions)

    # Compact per-booth progress sequence for the player's mission timeline UI — purely
    # additive JSON key, doesn't touch any existing key.
    team_missions_by_mission_id = {tm.mission_id: tm for tm in team.team_missions}
    current_mission_id = mission.id if mission is not None else None
    timeline = []
    for m in missions:
        existing = team_missions_by_mission_id.get(m.id)
        if existing and existing.status in ("passed", "overridden"):
            tl_status = existing.status
        elif m.id == current_mission_id:
            tl_status = "current"
        else:
            tl_status = "not_started"
        timeline.append({"mission_id": m.id, "title": m.title, "status": tl_status})

    payload = {
        "timeline": timeline,
        "event_status": state.status,
        "broadcast": (
            {"message": state.broadcast_message, "at": state.broadcast_at.isoformat()}
            if state.broadcast_message
            else None
        ),
        "team": {
            "name": team.name,
            "score": team.score,
            "integrity": team.integrity,
            "hints_used": team.hints_used,
            "hints_remaining": max(0, state.hint_limit - team.hints_used),
        },
        "cryptogram": cipher_service.board_state(team, missions),
        "fragments": [
            {"mission_id": f.mission_id, "value": f.cipher_value} for f in team.fragments
        ],
        "finished": mission is None,
        "mission": None,
    }

    if mission is not None:
        team_mission = mission_service.get_or_create_team_mission(team, mission)
        db.session.commit()

        remaining_penalty = None
        if team_mission.penalty_until and team_mission.penalty_until > datetime.utcnow():
            remaining_penalty = int((team_mission.penalty_until - datetime.utcnow()).total_seconds())

        payload["mission"] = {
            "id": mission.id,
            "title": mission.title,
            "narrative": mission.narrative,
            "time_limit": mission.time_limit,
            "started_at": team_mission.started_at.isoformat() if team_mission.started_at else None,
            "status": team_mission.status,
            "attempts": team_mission.attempts,
            "penalty_remaining": remaining_penalty,
            "evidence_files": [
                {"label": e.label, "file_type": e.file_type, "content": e.content}
                for e in mission.evidence_files
            ],
            "mcqs": [_serialize_mcq(m, team_mission) for m in mission.mcqs],
            "mcqs_complete": len(team_mission.mcq_answers) >= len(mission.mcqs),
            "challenge": _serialize_challenge(mission.challenge, team_mission)
            if mission.challenge
            else None,
            "pending_review": bool(team_mission.submission_text),
        }

    return jsonify(payload)


@missions_bp.route("/mcq/<int:mcq_id>/answer", methods=["POST"])
@team_required
def answer_mcq(mcq_id):
    team = current_team()
    state = event_service.get_state()
    if state.status != "running":
        return jsonify({"error": "Event is not currently running."}), 409

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    mcq = next((m for m in mission.mcqs if m.id == mcq_id), None)
    if mcq is None:
        return jsonify({"error": "That question does not belong to your current mission."}), 404

    team_mission = mission_service.get_or_create_team_mission(team, mission)

    existing = TeamMCQAnswer.query.filter_by(team_mission_id=team_mission.id, mcq_id=mcq.id).first()
    if existing:
        return jsonify(
            {
                "correct": existing.is_correct,
                "message": NARRATIVE["mcq_correct"] if existing.is_correct else NARRATIVE["mcq_wrong"],
                "already_answered": True,
            }
        )

    data = request.get_json(silent=True) or {}
    raw_option_id = data.get("option_id", request.form.get("option_id"))
    try:
        option_id = int(raw_option_id)
    except (TypeError, ValueError):
        return jsonify({"error": "option_id is required."}), 400
    option = next((o for o in mcq.options if o.id == option_id), None)
    if option is None:
        return jsonify({"error": "Invalid option."}), 400

    answer = TeamMCQAnswer(
        team_mission_id=team_mission.id,
        mcq_id=mcq.id,
        selected_option_id=option.id,
        is_correct=option.is_correct,
    )
    db.session.add(answer)

    if option.is_correct:
        scoring_service.score_mcq_correct(team, team_mission)

    db.session.commit()

    return jsonify(
        {
            "correct": option.is_correct,
            "message": NARRATIVE["mcq_correct"] if option.is_correct else NARRATIVE["mcq_wrong"],
        }
    )


@missions_bp.route("/challenge/submit", methods=["POST"])
@team_required
def submit_challenge():
    team = current_team()
    state = event_service.get_state()
    if state.status != "running":
        return jsonify({"error": "Event is not currently running."}), 409

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    challenge = mission.challenge
    team_mission = mission_service.get_or_create_team_mission(team, mission)

    if len(team_mission.mcq_answers) < len(mission.mcqs):
        return jsonify({"error": "Answer all threat assessment questions first."}), 400

    if team_mission.penalty_until and team_mission.penalty_until > datetime.utcnow():
        remaining = int((team_mission.penalty_until - datetime.utcnow()).total_seconds())
        return jsonify({"error": NARRATIVE["cooldown"], "penalty_remaining": remaining}), 429

    data = request.get_json(silent=True) or {}
    answer = data.get("answer", request.form.get("answer", ""))
    # Auto-graded submissions arrive as {"code": ...}, not {"answer": ...} — folding it in here
    # (rather than only inside the "auto" branch below) means the manual-review fallback below
    # still captures the actual submitted code when auto_grading_disabled reroutes an
    # otherwise-auto-graded challenge into that path, instead of silently discarding it.
    answer = data.get("code", answer)

    if challenge.grading_mode == "auto" and not state.auto_grading_disabled:
        if challenge.max_attempts and team_mission.attempts >= challenge.max_attempts:
            return jsonify({"error": "No attempts remaining for this challenge."}), 403

        code = data.get("code", answer)
        grading_result = grading_engine.run_all_tests(challenge, code)
        logger.info(
            "submission graded team=%r mission=%r passed=%s percent=%s tests=%s/%s",
            team.name,
            mission.title,
            grading_result.passed_threshold,
            grading_result.percent_score,
            grading_result.passed_tests,
            grading_result.total_tests,
        )
        db.session.add(
            CodeSubmission(
                team_mission_id=team_mission.id,
                code=code,
                mode="submit",
                total_tests=grading_result.total_tests,
                passed_tests=grading_result.passed_tests,
                weighted_score=grading_result.weighted_score,
                percent_score=grading_result.percent_score,
                passed=grading_result.passed_threshold,
                results_json=json.dumps(_serialize_grading_results(grading_result.results)),
            )
        )
        # actor=None (not a User row — teams aren't staff), team identity carried in metadata,
        # matching the existing convention for actions with no natural FK target (e.g.
        # "credentials_generated" in mod.py).
        audit_service.log(
            None,
            "team",
            "submission_graded",
            "team_mission",
            team_mission.id,
            metadata=f"{team.name}: {'passed' if grading_result.passed_threshold else 'failed'} "
            f"({grading_result.percent_score}%)",
        )

        if grading_result.passed_threshold:
            mission_service.complete_mission(team, team_mission, mission, "passed", grading_result=grading_result)
            return jsonify(
                {
                    "correct": True,
                    "message": NARRATIVE["challenge_pass"],
                    "percent_score": grading_result.percent_score,
                    "passed_tests": grading_result.passed_tests,
                    "total_tests": grading_result.total_tests,
                }
            )

        scoring_service.apply_retry_penalty(team, team_mission)
        team_mission.penalty_until = datetime.utcnow() + timedelta(seconds=60)
        db.session.commit()
        notify_team(team.id, "submission_failed")
        notify_mod("submission_failed")
        return jsonify(
            {
                "correct": False,
                "message": NARRATIVE["challenge_fail"],
                "percent_score": grading_result.percent_score,
                "passed_tests": grading_result.passed_tests,
                "total_tests": grading_result.total_tests,
            }
        )

    if challenge.type == "code":
        team_mission.submission_text = answer
        db.session.commit()
        logger.info("submission queued for manual review team=%r mission=%r", team.name, mission.title)
        notify_mod("submission_queued")
        return jsonify({"queued": True, "message": NARRATIVE["challenge_queued"]})

    correct = cipher_service.solve(answer, challenge.answer_key)
    logger.info("submission graded team=%r mission=%r passed=%s", team.name, mission.title, correct)
    if not correct:
        scoring_service.apply_retry_penalty(team, team_mission)
        team_mission.penalty_until = datetime.utcnow() + timedelta(seconds=60)
        db.session.commit()
        notify_team(team.id, "submission_failed")
        notify_mod("submission_failed")
        return jsonify({"correct": False, "message": NARRATIVE["challenge_fail"]})

    mission_service.complete_mission(team, team_mission, mission, "passed")
    message = NARRATIVE["flag_final"] if challenge.type == "flag" else NARRATIVE["challenge_pass"]
    return jsonify({"correct": True, "message": message})


@missions_bp.route("/hint", methods=["POST"])
@team_required
def request_hint():
    team = current_team()
    state = event_service.get_state()
    if team.hints_used >= state.hint_limit:
        return jsonify({"error": "No hints remaining for this event."}), 403

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    team_mission = mission_service.get_or_create_team_mission(team, mission)
    if team_mission.hint_used:
        return jsonify({"hint": _hint_text(mission.challenge)})

    scoring_service.apply_hint_penalty(team, team_mission)
    db.session.commit()
    return jsonify({"hint": _hint_text(mission.challenge)})


@missions_bp.route("/challenge/run-tests", methods=["POST"])
@team_required
def run_visible_tests():
    team = current_team()
    state = event_service.get_state()
    if state.status != "running":
        return jsonify({"error": "Event is not currently running."}), 409

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    challenge = mission.challenge
    if challenge is None or challenge.grading_mode != "auto":
        return jsonify({"error": "This challenge does not support test runs."}), 400
    if state.auto_grading_disabled:
        return jsonify({"error": "Automated grading is temporarily disabled — a Booth Agent will review submissions manually."}), 503

    team_mission = mission_service.get_or_create_team_mission(team, mission)
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    grading_result = grading_engine.run_visible_tests(challenge, code)
    db.session.add(
        CodeSubmission(
            team_mission_id=team_mission.id,
            code=code,
            mode="run_visible",
            total_tests=grading_result.total_tests,
            passed_tests=grading_result.passed_tests,
            weighted_score=grading_result.weighted_score,
            percent_score=grading_result.percent_score,
            passed=grading_result.passed_threshold,
            results_json=json.dumps(_serialize_grading_results(grading_result.results)),
        )
    )
    audit_service.log(
        None,
        "team",
        "visible_tests_run",
        "team_mission",
        team_mission.id,
        metadata=f"{team.name}: {grading_result.passed_tests}/{grading_result.total_tests} visible tests passed",
    )
    db.session.commit()
    notify_mod("visible_tests_run")

    return jsonify(
        {
            "results": _serialize_grading_results(grading_result.results),
            "passed_tests": grading_result.passed_tests,
            "total_tests": grading_result.total_tests,
        }
    )
