import json

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db
from ..models import Challenge, EvidenceFile, Hint, Mission, TestCase
from ..sockets import notify_global

agent_bp = Blueprint("agent", __name__, url_prefix="/agent")


def _owned_mission_or_404(mission_id):
    mission = Mission.query.get_or_404(mission_id)
    if mission.owner_agent_id != current_user.id:
        # 404, not 403 — an agent should not be able to tell whether a booth they don't
        # own exists at all.
        abort(404)
    return mission


def _owned_testcase_or_404(test_case_id):
    tc = TestCase.query.get_or_404(test_case_id)
    if tc.challenge.mission.owner_agent_id != current_user.id:
        abort(404)
    return tc


def _owned_hint_or_404(hint_id):
    hint = Hint.query.get_or_404(hint_id)
    if hint.challenge.mission.owner_agent_id != current_user.id:
        abort(404)
    return hint


def _owned_asset_or_404(asset_id):
    asset = EvidenceFile.query.get_or_404(asset_id)
    if asset.mission.owner_agent_id != current_user.id:
        abort(404)
    return asset


def _serialize_mission_summary(mission):
    return {
        "id": mission.id,
        "title": mission.title,
        "narrative": mission.narrative,
        "cipher_word": mission.cipher_word,
        "booth_id": mission.booth_id,
        "time_limit": mission.time_limit,
        "has_challenge": mission.challenge is not None,
        "grading_mode": mission.challenge.grading_mode if mission.challenge else None,
        "status": mission.status,
    }


def _serialize_testcase(tc):
    return {
        "id": tc.id,
        "name": tc.name,
        "input_data": tc.input_data,
        "expected_output": tc.expected_output,
        "weight": tc.weight,
        "visibility": tc.visibility,
        "failure_message": tc.failure_message,
        "order_index": tc.order_index,
    }


def _serialize_hint(hint):
    return {"id": hint.id, "text": hint.text, "point_cost": hint.point_cost, "order_index": hint.order_index}


def _serialize_asset(asset):
    return {"id": asset.id, "label": asset.label, "file_type": asset.file_type, "content": asset.content}


def _serialize_mission_detail(mission):
    challenge = mission.challenge
    payload = _serialize_mission_summary(mission)
    payload["challenge"] = None
    payload["test_cases"] = []
    payload["hints"] = []
    payload["assets"] = [_serialize_asset(a) for a in mission.evidence_files]
    if challenge:
        payload["challenge"] = {
            "title": challenge.title,
            "prompt": challenge.prompt,
            "language": challenge.language,
            "function_signature": challenge.function_signature,
            "starter_code": challenge.starter_code,
            # Private — this endpoint is owner-scoped only, never surfaced to players.
            "solution_code": challenge.solution_code,
            "grading_mode": challenge.grading_mode,
            "pass_threshold": challenge.pass_threshold,
            "max_attempts": challenge.max_attempts,
            "bonus_points": challenge.bonus_points,
            "time_limit_seconds": challenge.time_limit_seconds,
            "difficulty": challenge.difficulty,
        }
        payload["test_cases"] = [_serialize_testcase(tc) for tc in challenge.test_cases]
        payload["hints"] = [_serialize_hint(h) for h in challenge.hints]
    return payload


@agent_bp.route("/dashboard")
@login_required
@roles_required("booth_agent")
def dashboard():
    return render_template("agent/dashboard.html")


@agent_bp.route("/missions")
@login_required
@roles_required("booth_agent")
def list_missions():
    missions = Mission.query.filter_by(owner_agent_id=current_user.id).order_by(Mission.id).all()
    return jsonify({"missions": [_serialize_mission_summary(m) for m in missions]})


@agent_bp.route("/missions", methods=["POST"])
@login_required
@roles_required("booth_agent")
def create_mission():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    narrative = (data.get("narrative") or "").strip()
    cipher_word = (data.get("cipher_word") or "").strip().upper()
    if not title or not narrative or not cipher_word:
        return jsonify({"error": "title, narrative, and cipher_word are required."}), 400

    next_order = (db.session.query(db.func.max(Mission.order_index)).scalar() or 0) + 1
    next_booth = (db.session.query(db.func.max(Mission.booth_id)).scalar() or 0) + 1
    mission = Mission(
        title=title,
        type="code",
        narrative=narrative,
        cipher_word=cipher_word,
        booth_id=next_booth,
        order_index=next_order,
        time_limit=data.get("time_limit"),
        owner_agent_id=current_user.id,
        # New missions start as drafts — a mission with no challenge yet was previously
        # already visible to players (broken/empty panel) the instant it was created.
        status="draft",
    )
    db.session.add(mission)
    db.session.commit()
    return jsonify(_serialize_mission_detail(mission)), 201


@agent_bp.route("/missions/<int:mission_id>")
@login_required
@roles_required("booth_agent")
def get_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    return jsonify(_serialize_mission_detail(mission))


@agent_bp.route("/missions/<int:mission_id>", methods=["PUT"])
@login_required
@roles_required("booth_agent")
def update_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    data = request.get_json(silent=True) or {}
    if "title" in data:
        mission.title = (data["title"] or "").strip() or mission.title
    if "narrative" in data:
        mission.narrative = (data["narrative"] or "").strip() or mission.narrative
    if "cipher_word" in data:
        mission.cipher_word = (data["cipher_word"] or "").strip().upper() or mission.cipher_word
    if "time_limit" in data:
        mission.time_limit = data["time_limit"]
    db.session.commit()
    return jsonify(_serialize_mission_detail(mission))


@agent_bp.route("/missions/<int:mission_id>", methods=["DELETE"])
@login_required
@roles_required("booth_agent")
def delete_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    db.session.delete(mission)
    db.session.commit()
    return jsonify({"ok": True})


@agent_bp.route("/missions/<int:mission_id>/publish", methods=["POST"])
@login_required
@roles_required("booth_agent")
def publish_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    if mission.challenge is None:
        return jsonify({"error": "Add a challenge before publishing this booth."}), 400
    mission.status = "published"
    db.session.commit()
    return jsonify(_serialize_mission_detail(mission))


@agent_bp.route("/missions/<int:mission_id>/unpublish", methods=["POST"])
@login_required
@roles_required("booth_agent")
def unpublish_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    mission.status = "draft"
    db.session.commit()
    return jsonify(_serialize_mission_detail(mission))


@agent_bp.route("/missions/<int:mission_id>/archive", methods=["POST"])
@login_required
@roles_required("booth_agent")
def archive_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    mission.status = "archived"
    db.session.commit()
    return jsonify(_serialize_mission_detail(mission))


@agent_bp.route("/missions/<int:mission_id>/duplicate", methods=["POST"])
@login_required
@roles_required("booth_agent")
def duplicate_mission(mission_id):
    mission = _owned_mission_or_404(mission_id)
    next_order = (db.session.query(db.func.max(Mission.order_index)).scalar() or 0) + 1
    next_booth = (db.session.query(db.func.max(Mission.booth_id)).scalar() or 0) + 1
    copy = Mission(
        title=f"{mission.title} (copy)",
        type=mission.type,
        narrative=mission.narrative,
        # Not a hard requirement (each mission's cryptogram tile is keyed by its own
        # order_index/shift, not by cipher_word uniqueness) — just a nudge so a freshly
        # duplicated, still-draft mission doesn't silently produce a visually duplicate
        # cryptogram board if published without editing first.
        cipher_word=f"{mission.cipher_word}COPY"[:20],
        booth_id=next_booth,
        order_index=next_order,
        time_limit=mission.time_limit,
        owner_agent_id=current_user.id,
        status="draft",
    )
    db.session.add(copy)
    db.session.flush()

    if mission.challenge:
        src = mission.challenge
        challenge = Challenge(
            mission_id=copy.id,
            type=src.type,
            title=src.title,
            prompt=src.prompt,
            language=src.language,
            function_signature=src.function_signature,
            starter_code=src.starter_code,
            solution_code=src.solution_code,
            grading_mode=src.grading_mode,
            pass_threshold=src.pass_threshold,
            max_attempts=src.max_attempts,
            bonus_points=src.bonus_points,
            time_limit_seconds=src.time_limit_seconds,
            difficulty=src.difficulty,
        )
        db.session.add(challenge)
        db.session.flush()
        for tc in src.test_cases:
            db.session.add(
                TestCase(
                    challenge_id=challenge.id,
                    name=tc.name,
                    input_data=tc.input_data,
                    expected_output=tc.expected_output,
                    weight=tc.weight,
                    visibility=tc.visibility,
                    failure_message=tc.failure_message,
                    order_index=tc.order_index,
                )
            )
        for hint in src.hints:
            db.session.add(
                Hint(
                    challenge_id=challenge.id,
                    text=hint.text,
                    point_cost=hint.point_cost,
                    order_index=hint.order_index,
                )
            )

    for asset in mission.evidence_files:
        db.session.add(
            EvidenceFile(
                mission_id=copy.id,
                label=asset.label,
                file_type=asset.file_type,
                content=asset.content,
            )
        )

    db.session.commit()
    return jsonify(_serialize_mission_detail(copy)), 201


@agent_bp.route("/missions/<int:mission_id>/challenge", methods=["PUT"])
@login_required
@roles_required("booth_agent")
def upsert_challenge(mission_id):
    mission = _owned_mission_or_404(mission_id)
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt (problem statement) is required."}), 400

    challenge = mission.challenge
    if challenge is None:
        challenge = Challenge(mission_id=mission.id, type="code")
        db.session.add(challenge)

    challenge.title = (data.get("title") or "").strip() or None
    challenge.prompt = prompt
    challenge.language = data.get("language") or "python"
    challenge.function_signature = data.get("function_signature")
    challenge.starter_code = data.get("starter_code")
    challenge.solution_code = data.get("solution_code")
    challenge.grading_mode = "auto"
    challenge.pass_threshold = int(data.get("pass_threshold") or 100)
    challenge.max_attempts = data.get("max_attempts") or None
    challenge.bonus_points = int(data.get("bonus_points") or 0)
    challenge.time_limit_seconds = int(data.get("time_limit_seconds") or 5)
    difficulty = data.get("difficulty")
    challenge.difficulty = difficulty if difficulty in ("easy", "medium", "hard") else None
    db.session.commit()
    # Push-triggers-refresh, same as every other live-data change in this app (missions.py,
    # security.py) — never carries the new prompt itself, just tells any connected player to
    # re-fetch /missions/status. Global rather than notify_team(team_id, ...) because an Agent
    # editing a challenge doesn't know which teams are currently on this mission.
    notify_global("mission_updated")
    return jsonify(_serialize_mission_detail(mission))


@agent_bp.route("/missions/<int:mission_id>/testcases", methods=["POST"])
@login_required
@roles_required("booth_agent")
def create_testcase(mission_id):
    mission = _owned_mission_or_404(mission_id)
    if mission.challenge is None:
        return jsonify({"error": "Save the challenge before adding test cases."}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    expected_output = data.get("expected_output")
    if not name or expected_output is None:
        return jsonify({"error": "name and expected_output are required."}), 400

    next_order = (
        db.session.query(db.func.max(TestCase.order_index))
        .filter_by(challenge_id=mission.challenge.id)
        .scalar()
        or 0
    ) + 1
    tc = TestCase(
        challenge_id=mission.challenge.id,
        name=name,
        input_data=data.get("input_data"),
        expected_output=expected_output,
        weight=int(data.get("weight") or 1),
        visibility="hidden" if data.get("visibility") == "hidden" else "visible",
        failure_message=data.get("failure_message"),
        order_index=next_order,
    )
    db.session.add(tc)
    db.session.commit()
    return jsonify(_serialize_testcase(tc)), 201


@agent_bp.route("/testcases/<int:test_case_id>", methods=["PUT"])
@login_required
@roles_required("booth_agent")
def update_testcase(test_case_id):
    tc = _owned_testcase_or_404(test_case_id)
    data = request.get_json(silent=True) or {}
    for field in ("name", "input_data", "expected_output", "failure_message"):
        if field in data:
            setattr(tc, field, data[field])
    if "weight" in data:
        tc.weight = int(data["weight"] or 1)
    if "visibility" in data:
        tc.visibility = "hidden" if data["visibility"] == "hidden" else "visible"
    db.session.commit()
    return jsonify(_serialize_testcase(tc))


@agent_bp.route("/testcases/<int:test_case_id>", methods=["DELETE"])
@login_required
@roles_required("booth_agent")
def delete_testcase(test_case_id):
    tc = _owned_testcase_or_404(test_case_id)
    db.session.delete(tc)
    db.session.commit()
    return jsonify({"ok": True})


@agent_bp.route("/missions/<int:mission_id>/testcases/reorder", methods=["POST"])
@login_required
@roles_required("booth_agent")
def reorder_testcases(mission_id):
    mission = _owned_mission_or_404(mission_id)
    if mission.challenge is None:
        abort(404)
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("order") or []
    tc_by_id = {tc.id: tc for tc in mission.challenge.test_cases}
    for index, tc_id in enumerate(ordered_ids):
        tc = tc_by_id.get(tc_id)
        if tc is not None:
            tc.order_index = index
    db.session.commit()
    return jsonify({"ok": True})


@agent_bp.route("/missions/<int:mission_id>/testcases/export")
@login_required
@roles_required("booth_agent")
def export_testcases(mission_id):
    mission = _owned_mission_or_404(mission_id)
    test_cases = mission.challenge.test_cases if mission.challenge else []
    payload = [
        {
            "name": tc.name,
            "input_data": tc.input_data,
            "expected_output": tc.expected_output,
            "weight": tc.weight,
            "visibility": tc.visibility,
            "failure_message": tc.failure_message,
        }
        for tc in test_cases
    ]
    return jsonify(payload)


@agent_bp.route("/missions/<int:mission_id>/testcases/import", methods=["POST"])
@login_required
@roles_required("booth_agent")
def import_testcases(mission_id):
    mission = _owned_mission_or_404(mission_id)
    if mission.challenge is None:
        return jsonify({"error": "Save the challenge before importing test cases."}), 400
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        try:
            data = json.loads(request.data)
        except (TypeError, ValueError):
            return jsonify({"error": "Expected a JSON array of test cases."}), 400
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array of test cases."}), 400

    next_order = (
        db.session.query(db.func.max(TestCase.order_index))
        .filter_by(challenge_id=mission.challenge.id)
        .scalar()
        or 0
    )
    created = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict) or not entry.get("name") or "expected_output" not in entry:
            continue
        tc = TestCase(
            challenge_id=mission.challenge.id,
            name=entry["name"],
            input_data=entry.get("input_data"),
            expected_output=entry["expected_output"],
            weight=int(entry.get("weight") or 1),
            visibility="hidden" if entry.get("visibility") == "hidden" else "visible",
            failure_message=entry.get("failure_message"),
            order_index=next_order + index + 1,
        )
        db.session.add(tc)
        created.append(tc)
    db.session.commit()
    return jsonify({"imported": len(created)})


@agent_bp.route("/missions/<int:mission_id>/hints", methods=["POST"])
@login_required
@roles_required("booth_agent")
def create_hint(mission_id):
    mission = _owned_mission_or_404(mission_id)
    if mission.challenge is None:
        return jsonify({"error": "Save the challenge before adding hints."}), 400
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required."}), 400
    next_order = (
        db.session.query(db.func.max(Hint.order_index)).filter_by(challenge_id=mission.challenge.id).scalar() or 0
    ) + 1
    hint = Hint(
        challenge_id=mission.challenge.id,
        text=text,
        point_cost=data.get("point_cost"),
        order_index=next_order,
    )
    db.session.add(hint)
    db.session.commit()
    return jsonify(_serialize_hint(hint)), 201


@agent_bp.route("/hints/<int:hint_id>", methods=["PUT"])
@login_required
@roles_required("booth_agent")
def update_hint(hint_id):
    hint = _owned_hint_or_404(hint_id)
    data = request.get_json(silent=True) or {}
    if "text" in data:
        hint.text = (data["text"] or "").strip() or hint.text
    if "point_cost" in data:
        hint.point_cost = data["point_cost"]
    db.session.commit()
    return jsonify(_serialize_hint(hint))


@agent_bp.route("/hints/<int:hint_id>", methods=["DELETE"])
@login_required
@roles_required("booth_agent")
def delete_hint(hint_id):
    hint = _owned_hint_or_404(hint_id)
    db.session.delete(hint)
    db.session.commit()
    return jsonify({"ok": True})


@agent_bp.route("/missions/<int:mission_id>/assets", methods=["POST"])
@login_required
@roles_required("booth_agent")
def create_asset(mission_id):
    mission = _owned_mission_or_404(mission_id)
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()
    content = data.get("content") or ""
    if not label or not content:
        return jsonify({"error": "label and content are required."}), 400
    asset = EvidenceFile(
        mission_id=mission.id,
        label=label,
        file_type=data.get("file_type") or "text",
        content=content,
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify(_serialize_asset(asset)), 201


@agent_bp.route("/assets/<int:asset_id>", methods=["DELETE"])
@login_required
@roles_required("booth_agent")
def delete_asset(asset_id):
    asset = _owned_asset_or_404(asset_id)
    db.session.delete(asset)
    db.session.commit()
    return jsonify({"ok": True})
