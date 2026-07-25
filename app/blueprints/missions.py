import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request

from ..decorators import current_team, team_required
from ..extensions import db
from ..models import (
    CodeSubmission,
    EvidenceFile,
    Fragment,
    FinalFlagConfirmation,
    Mission,
    TeamKnowledgeAnswer,
    TeamMission,
)
from ..services.audit_service import AuditService
from ..services.cipher_service import CipherService
from ..services.event_service import EventService
from ..services.final_flag_service import FinalFlagService
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
    "challenge_pass": "NODE SECURED. FRAGMENT ACQUIRED.",
    "challenge_fail": "PATCH REJECTED — VULNERABILITY STILL ACTIVE.",
    "flag_final": "GRID CORE RESTORED.",
    "cooldown": "NODE ON COOLDOWN.",
    "knowledge_correct": "CIPHER CLUE DECODED.",
    "knowledge_wrong": "INCORRECT — NO CLUE REVEALED.",
}


@missions_bp.route("/play")
@team_required
def play():
    return render_template("player/dashboard.html")


def _hint_text(challenge):
    # Agent-authored hints (Hint rows) take precedence; legacy single hint_text is the
    # fallback for missions that predate the multi-hint authoring flow.
    if challenge.hints:
        return challenge.hints[0].text
    return challenge.hint_text


def _serialize_knowledge_question(question, team_mission):
    answered = None
    if team_mission:
        answered = next((a for a in team_mission.knowledge_answers if a.question_id == question.id), None)
    return {
        "id": question.id,
        "question_text": question.question_text,
        "options": [{"id": o.id, "option_text": o.option_text} for o in question.options],
        "answered": answered is not None,
        "was_correct": answered.is_correct if answered else None,
    }


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
    payload = {
        "type": challenge.type,
        "prompt": challenge.prompt,
        "hint_text": _hint_text(challenge) if (team_mission and team_mission.hint_used) else None,
        "grading_mode": challenge.grading_mode,
    }
    if challenge.grading_mode == "auto":
        last_submission = None
        if team_mission:
            last_submission = (
                CodeSubmission.query.filter_by(team_mission_id=team_mission.id, mode="submit")
                .order_by(CodeSubmission.id.desc())
                .first()
            )
        payload.update(
            {
                "title": challenge.title,
                "language": challenge.language,
                "function_signature": challenge.function_signature,
                "starter_code": challenge.starter_code,
                "last_submitted_code": last_submission.code if last_submission else None,
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

    # Compact per-booth progress sequence for the player's mission timeline UI — built from
    # this team's own rotated visiting order (mission_service.ordered_for_team), not the raw
    # booth-number order, so a team starting mid-rotation sees the sequence they're actually
    # walking (e.g. 4,5,6,1,2,3) instead of a fixed 1-through-6 with "4" just highlighted.
    team_missions_by_mission_id = {tm.mission_id: tm for tm in team.team_missions}
    current_mission_id = mission.id if mission is not None else None
    ordered_missions = mission_service.ordered_for_team(team, missions)
    timeline = []
    next_mission_payload = None
    for i, m in enumerate(ordered_missions):
        existing = team_missions_by_mission_id.get(m.id)
        if existing and existing.status in ("passed", "overridden", "soft_locked"):
            tl_status = existing.status
        elif m.id == current_mission_id:
            tl_status = "current"
            if i + 1 < len(ordered_missions):
                next_mission_payload = {"mission_id": ordered_missions[i + 1].id, "title": ordered_missions[i + 1].title}
        else:
            tl_status = "not_started"
        timeline.append({"mission_id": m.id, "title": m.title, "status": tl_status})
    booths_completed = sum(1 for t in timeline if t["status"] in ("passed", "overridden", "soft_locked"))

    payload = {
        "timeline": timeline,
        "next_mission": next_mission_payload,
        "booths_completed": booths_completed,
        "booths_total": len(missions),
        "event_status": state.status,
        "soft_lock_min_attempts": state.soft_lock_min_attempts,
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
        "cryptogram": cipher_service.board_state(team, ordered_missions),
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
            "tagline": mission.tagline,
            "narrative": mission.narrative,
            "time_limit": mission.time_limit,
            "started_at": team_mission.started_at.isoformat() if team_mission.started_at else None,
            "status": team_mission.status,
            "attempts": team_mission.attempts,
            "penalty_remaining": remaining_penalty,
            # Frozen the instant a deciding submission arrived — once present, the frontend
            # must show these instead of computing a live countdown from started_at, and must
            # never let grading/review time move them.
            "submitted_at": team_mission.submitted_at.isoformat() if team_mission.submitted_at else None,
            "elapsed_seconds": team_mission.elapsed_seconds,
            "time_remaining_frozen": team_mission.time_remaining,
            "submission_status": team_mission.submission_status,
            "grading_status": team_mission.grading_status,
            "evidence_files": [
                {
                    "id": e.id,
                    "label": e.label,
                    "file_type": e.file_type,
                    "content": e.content,
                    "has_binary": bool(e.data),
                    "mime_type": e.mime_type,
                    "filename": e.filename,
                }
                for e in mission.evidence_files
            ],
            "challenge": _serialize_challenge(mission.challenge, team_mission)
            if mission.challenge
            else None,
            "pending_review": bool(team_mission.submission_text),
        }
        assigned_questions = mission_service.assign_knowledge_subset(team_mission, mission)
        payload["mission"]["knowledge_questions"] = [
            _serialize_knowledge_question(q, team_mission) for q in assigned_questions
        ]
        payload["mission"]["knowledge_check_complete"] = len(team_mission.knowledge_answers) >= len(
            assigned_questions
        )

    return jsonify(payload)


@missions_bp.route("/assets/<int:asset_id>/download")
@team_required
def download_asset(asset_id):
    # Same trust level the "content" field of a text-mode evidence asset already has today —
    # served to any authenticated team, not scoped to whichever mission it's currently on. No
    # ownership beyond "you're a logged-in team" is enforced elsewhere for evidence content either.
    asset = EvidenceFile.query.get_or_404(asset_id)
    if not asset.data:
        abort(404)
    return Response(
        asset.data,
        mimetype=asset.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{asset.filename or asset.label}"'},
    )


@missions_bp.route("/knowledge-check/<int:question_id>/answer", methods=["POST"])
@team_required
def answer_knowledge_question(question_id):
    team = current_team()
    state = event_service.get_state()
    if state.status != "running":
        return jsonify({"error": "Event is not currently running."}), 409

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    team_mission = mission_service.get_or_create_team_mission(team, mission)
    assigned_questions = mission_service.assign_knowledge_subset(team_mission, mission)
    question = next((q for q in assigned_questions if q.id == question_id), None)
    if question is None:
        return jsonify({"error": "That question does not belong to your current mission."}), 404

    existing = TeamKnowledgeAnswer.query.filter_by(
        team_mission_id=team_mission.id, question_id=question.id
    ).first()
    if existing:
        return jsonify(
            {
                "correct": existing.is_correct,
                "message": NARRATIVE["knowledge_correct"] if existing.is_correct else NARRATIVE["knowledge_wrong"],
                "already_answered": True,
            }
        )

    data = request.get_json(silent=True) or {}
    raw_option_id = data.get("option_id", request.form.get("option_id"))
    try:
        option_id = int(raw_option_id)
    except (TypeError, ValueError):
        return jsonify({"error": "option_id is required."}), 400
    option = next((o for o in question.options if o.id == option_id), None)
    if option is None:
        return jsonify({"error": "Invalid option."}), 400

    answer = TeamKnowledgeAnswer(
        team_mission_id=team_mission.id,
        question_id=question.id,
        selected_option_id=option.id,
        is_correct=option.is_correct,
    )
    db.session.add(answer)

    if option.is_correct:
        db.session.refresh(team, with_for_update=True)
        scoring_service.score_knowledge_correct(team, team_mission)

    db.session.commit()

    return jsonify(
        {
            "correct": option.is_correct,
            "message": NARRATIVE["knowledge_correct"] if option.is_correct else NARRATIVE["knowledge_wrong"],
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
    assigned_questions = mission_service.assign_knowledge_subset(team_mission, mission)
    if len(team_mission.knowledge_answers) < len(assigned_questions):
        return jsonify({"error": "Complete the Knowledge Check before submitting."}), 400
    # Captured before any grading happens below — this, not whenever the response finally gets
    # sent, is the team's official submission instant (mission_service.freeze_submission uses
    # it verbatim), so grading time can never inflate a team's recorded completion time.
    received_at = datetime.utcnow()

    if team_mission.penalty_until and team_mission.penalty_until > datetime.utcnow():
        remaining = int((team_mission.penalty_until - datetime.utcnow()).total_seconds())
        return jsonify({"error": NARRATIVE["cooldown"], "penalty_remaining": remaining}), 429

    data = request.get_json(silent=True) or {}
    answer = data.get("answer", request.form.get("answer", ""))
    # Auto-graded submissions arrive as {"code": ...}, not {"answer": ...}.
    answer = data.get("code", answer)

    if challenge.grading_mode == "auto":
        if challenge.max_attempts and team_mission.attempts >= challenge.max_attempts:
            return jsonify({"error": "No attempts remaining for this challenge."}), 403

        code = data.get("code", answer)
        logger.info("grading started team=%r mission=%r mode=submit", team.name, mission.title)
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
            mission_service.complete_mission(
                team, team_mission, mission, "passed", grading_result=grading_result, submitted_at=received_at
            )
            return jsonify(
                {
                    "correct": True,
                    "message": NARRATIVE["challenge_pass"],
                    "percent_score": grading_result.percent_score,
                    "passed_tests": grading_result.passed_tests,
                    "total_tests": grading_result.total_tests,
                }
            )

        db.session.refresh(team, with_for_update=True)
        scoring_service.score_auto_graded_partial(team, team_mission, grading_result)
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

    # Flag/cipher challenges previously had no cap at all beyond the 60s cooldown, so a team
    # could resubmit indefinitely once the cooldown passed. Same opt-in check as the auto
    # branch — max_attempts defaults to None (unlimited) unless an Agent explicitly sets one.
    if challenge.max_attempts and team_mission.attempts >= challenge.max_attempts:
        return jsonify({"error": "No attempts remaining for this challenge."}), 403

    correct = cipher_service.solve(answer, challenge.answer_key)
    logger.info("submission graded team=%r mission=%r passed=%s", team.name, mission.title, correct)
    if not correct:
        db.session.refresh(team, with_for_update=True)
        scoring_service.apply_retry_penalty(team, team_mission)
        team_mission.penalty_until = datetime.utcnow() + timedelta(seconds=60)
        db.session.commit()
        notify_team(team.id, "submission_failed")
        notify_mod("submission_failed")
        return jsonify({"correct": False, "message": NARRATIVE["challenge_fail"]})

    mission_service.complete_mission(team, team_mission, mission, "passed", submitted_at=received_at)
    message = NARRATIVE["flag_final"] if challenge.type == "flag" else NARRATIVE["challenge_pass"]
    return jsonify({"correct": True, "message": message})


@missions_bp.route("/hint", methods=["POST"])
@team_required
def request_hint():
    team = current_team()
    state = event_service.get_state()
    if state.status != "running":
        return jsonify({"error": "Event is not currently running."}), 409
    if team.hints_used >= state.hint_limit:
        return jsonify({"error": "No hints remaining for this event."}), 403

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    team_mission = mission_service.get_or_create_team_mission(team, mission)
    if team_mission.hint_used:
        return jsonify({"hint": _hint_text(mission.challenge)})

    db.session.refresh(team, with_for_update=True)
    scoring_service.apply_hint_penalty(team, team_mission)
    db.session.commit()
    return jsonify({"hint": _hint_text(mission.challenge)})


@missions_bp.route("/soft-lock", methods=["POST"])
@team_required
def soft_lock():
    team = current_team()
    state = event_service.get_state()
    if state.status != "running":
        return jsonify({"error": "Event is not currently running."}), 409

    missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
    mission, _ = mission_service.current_mission_for(team, missions)
    if mission is None:
        return jsonify({"error": "No active mission."}), 400

    team_mission = mission_service.get_or_create_team_mission(team, mission)
    if team_mission.status in ("passed", "overridden", "soft_locked"):
        return jsonify({"error": "This mission is already resolved."}), 409
    if team_mission.attempts < state.soft_lock_min_attempts:
        return jsonify(
            {
                "error": f"Soft Lock unlocks after {state.soft_lock_min_attempts} failed "
                "attempt(s) at this booth."
            }
        ), 403

    ok = mission_service.soft_lock_mission(team, team_mission, mission, state.soft_lock_min_attempts)
    if not ok:
        return jsonify({"error": "This mission is already resolved."}), 409
    return jsonify({"ok": True, "message": "Booth soft-locked. Moving on to the next assignment."})


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

    team_mission = mission_service.get_or_create_team_mission(team, mission)
    assigned_questions = mission_service.assign_knowledge_subset(team_mission, mission)
    if len(team_mission.knowledge_answers) < len(assigned_questions):
        return jsonify({"error": "Complete the Knowledge Check before running tests."}), 400
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    logger.info("grading started team=%r mission=%r mode=run_visible", team.name, mission.title)
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


@missions_bp.route("/final-flag/requirements")
@team_required
def final_flag_requirements():
    # Tells the frontend which missions to render an entry field for, and confirms the gate
    # (every required mission actually passed) without revealing anything about fragment
    # values themselves — those are only ever checked, never returned, by the POST below.
    required_mission_ids = current_app.config.get("FINAL_FLAG_MISSION_IDS") or []
    if not required_mission_ids:
        return jsonify({"error": "Final flag is not configured for this event yet."}), 404

    team = current_team()
    passed_ids = {
        tm.mission_id
        for tm in TeamMission.query.filter_by(team_id=team.id).all()
        if tm.status in ("passed", "overridden") and tm.mission_id in required_mission_ids
    }
    if passed_ids != set(required_mission_ids):
        return jsonify({"error": "Not all required vaults have been secured yet."}), 403

    missions = Mission.query.filter(Mission.id.in_(required_mission_ids)).order_by(Mission.order_index).all()
    return jsonify({"vaults": [{"mission_id": m.id, "title": m.title} for m in missions]})


@missions_bp.route("/final-flag", methods=["POST"])
@team_required
def final_flag():
    # Server-side gate, never trusts anything the client claims about its own progress. Two
    # independent checks, both required: (1) every required mission actually passed — queried
    # from this team's own TeamMission rows, not asserted by the client — and (2) the fragment
    # value the player typed in for each vault matches that team's real, already-recorded
    # Fragment.cipher_value row for it exactly (the same code already shown to them on their own
    # cryptogram board/fragment rail — this is a "did you actually collect and transcribe them"
    # step, not a secret the player has to guess).
    required_mission_ids = current_app.config.get("FINAL_FLAG_MISSION_IDS") or []
    if not required_mission_ids:
        return jsonify({"error": "Final flag is not configured for this event yet."}), 404

    team = current_team()
    passed_ids = {
        tm.mission_id
        for tm in TeamMission.query.filter_by(team_id=team.id).all()
        if tm.status in ("passed", "overridden") and tm.mission_id in required_mission_ids
    }
    if passed_ids != set(required_mission_ids):
        return jsonify({"error": "Not all required vaults have been secured yet."}), 403

    data = request.get_json(silent=True) or {}
    submitted = data.get("fragments") or {}
    real_fragments = {
        f.mission_id: f.cipher_value
        for f in Fragment.query.filter(
            Fragment.team_id == team.id, Fragment.mission_id.in_(required_mission_ids)
        ).all()
    }

    wrong = []
    for mission_id in required_mission_ids:
        entered = str(submitted.get(str(mission_id), submitted.get(mission_id, ""))).strip().lower()
        expected = (real_fragments.get(mission_id) or "").strip().lower()
        if not expected or entered != expected:
            wrong.append(mission_id)

    if wrong:
        return jsonify({"error": "One or more fragments don't match.", "incorrect_mission_ids": wrong}), 400

    # Fragments are correct, but the flag itself is never reconstructed/returned here — a Game
    # Master must confirm at the Command Centre first (see /mod/final-flag/<team_id>/confirm in
    # app/blueprints/mod.py). This route only opens or reports on that pending gate.
    confirmation = FinalFlagConfirmation.query.filter_by(team_id=team.id).first()
    if confirmation is None:
        confirmation = FinalFlagConfirmation(team_id=team.id)
        db.session.add(confirmation)
        audit_service.log(None, "team", "final_flag_requested", "team", team.id, metadata=team.name)
        db.session.commit()
        notify_mod("final_flag_requested")

    if confirmation.confirmed_at is None:
        return jsonify({"status": "pending"})

    try:
        flag = _reconstruct_final_flag(team, required_mission_ids)
    except FinalFlagReconstructionError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    return jsonify({"status": "confirmed", "flag": flag})


@missions_bp.route("/final-flag/status")
@team_required
def final_flag_status():
    # Lightweight poll target for a team waiting on Game Master confirmation — avoids re-POSTing
    # (and re-validating) the same already-accepted fragments on every refresh while pending.
    team = current_team()
    confirmation = FinalFlagConfirmation.query.filter_by(team_id=team.id).first()
    if confirmation is None:
        return jsonify({"status": "none"})
    if confirmation.confirmed_at is None:
        return jsonify({"status": "pending"})
    required_mission_ids = current_app.config.get("FINAL_FLAG_MISSION_IDS") or []
    try:
        flag = _reconstruct_final_flag(team, required_mission_ids)
    except FinalFlagReconstructionError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    return jsonify({"status": "confirmed", "flag": flag})


class FinalFlagReconstructionError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def _reconstruct_final_flag(team, required_mission_ids):
    ciphertext = current_app.config.get("FINAL_FLAG_CIPHERTEXT")
    service = FinalFlagService(current_app.config["EVENT_SALT"], ciphertext)
    flag = service.reconstruct(required_mission_ids)
    if flag is None:
        if ciphertext:
            # Configured but didn't decrypt to valid text — an EVENT_SALT that doesn't match
            # what derive_final_flag.py was run with (rotated since, or never matched), not a
            # missing-config situation. Logged loudly since this is an operator problem, not a
            # team one — the team-facing message stays generic on purpose (no internals).
            logger.error(
                "final_flag reconstruction produced invalid UTF-8 for team=%r mission_ids=%s -- "
                "EVENT_SALT likely doesn't match the one derive_final_flag.py was run with.",
                team.name,
                required_mission_ids,
            )
            raise FinalFlagReconstructionError("Final flag could not be verified — notify a Game Master.", 500)
        raise FinalFlagReconstructionError("Final flag is not configured for this event yet.", 404)
    audit_service.log(None, "team", "final_flag_reconstructed", "team", team.id, metadata=team.name)
    db.session.commit()
    return flag
