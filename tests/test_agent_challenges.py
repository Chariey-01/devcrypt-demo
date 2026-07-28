def login(client, email):
    return client.post("/auth/login", data={"email": email, "password": "pw"})


def test_agent_can_create_and_manage_own_mission(client, app, two_agents):
    agent_a_id, _ = two_agents
    login(client, "agent-a@test.local")

    res = client.post(
        "/agent/missions",
        json={"title": "Gateway Node", "narrative": "narrative", "cipher_word": "GATEWAY"},
    )
    assert res.status_code == 201
    mission_id = res.get_json()["id"]

    res = client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={"prompt": "Double the input.", "starter_code": "pass"},
    )
    assert res.status_code == 200
    assert res.get_json()["challenge"]["grading_mode"] == "auto"


def test_upsert_challenge_preserves_an_existing_pytest_grading_mode(client, app, two_agents):
    # scripts/import_challenge_content.py sets grading_mode="pytest" for function/pytest-style
    # challenges. An Agent later editing something unrelated (a hint, bonus points) via this
    # same PUT route must not silently downgrade that back to "auto" -- see the fix in
    # app/blueprints/agent.py's upsert_challenge.
    from app.extensions import db
    from app.models import Challenge

    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={"prompt": "Detect the issue.", "starter_code": "def solve(): ..."},
    )
    with app.app_context():
        challenge = Challenge.query.filter_by(mission_id=mission_id).first()
        challenge.grading_mode = "pytest"
        challenge.test_code = "from submission import solve\n\n\ndef test_solve():\n    assert solve()\n"
        db.session.commit()

    res = client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={"prompt": "Detect the issue.", "starter_code": "def solve(): ...", "bonus_points": 5},
    )
    assert res.status_code == 200
    assert res.get_json()["challenge"]["grading_mode"] == "pytest"
    with app.app_context():
        challenge = Challenge.query.filter_by(mission_id=mission_id).first()
        assert challenge.grading_mode == "pytest"
        assert challenge.test_code is not None


def test_agent_cannot_read_or_edit_another_agents_mission(client, app, two_agents):
    agent_a_id, agent_b_id = two_agents
    login(client, "agent-a@test.local")
    res = client.post(
        "/agent/missions",
        json={"title": "Gateway Node", "narrative": "narrative", "cipher_word": "GATEWAY"},
    )
    mission_id = res.get_json()["id"]

    client.post("/auth/logout")
    login(client, "agent-b@test.local")

    assert client.get(f"/agent/missions/{mission_id}").status_code == 404
    assert client.put(f"/agent/missions/{mission_id}", json={"title": "hijacked"}).status_code == 404
    assert client.delete(f"/agent/missions/{mission_id}").status_code == 404
    assert client.get("/agent/missions").get_json()["missions"] == []


def test_solution_code_never_reaches_unowned_agent(client, app, two_agents):
    login(client, "agent-a@test.local")
    res = client.post(
        "/agent/missions",
        json={"title": "Gateway Node", "narrative": "narrative", "cipher_word": "GATEWAY"},
    )
    mission_id = res.get_json()["id"]
    client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={"prompt": "Double the input.", "solution_code": "print('secret')"},
    )

    client.post("/auth/logout")
    login(client, "agent-b@test.local")
    assert client.get(f"/agent/missions/{mission_id}").status_code == 404


def _create_mission(client):
    res = client.post(
        "/agent/missions",
        json={"title": "Gateway Node", "narrative": "narrative", "cipher_word": "GATEWAY"},
    )
    return res.get_json()["id"]


def test_new_mission_starts_as_draft(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    assert client.get(f"/agent/missions/{mission_id}").get_json()["status"] == "draft"


def test_cannot_publish_without_a_challenge(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    res = client.post(f"/agent/missions/{mission_id}/publish")
    assert res.status_code == 400


def test_publish_unpublish_archive_lifecycle(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    client.put(f"/agent/missions/{mission_id}/challenge", json={"prompt": "Double the input."})

    res = client.post(f"/agent/missions/{mission_id}/publish")
    assert res.status_code == 200
    assert res.get_json()["status"] == "published"

    res = client.post(f"/agent/missions/{mission_id}/unpublish")
    assert res.get_json()["status"] == "draft"

    res = client.post(f"/agent/missions/{mission_id}/archive")
    assert res.get_json()["status"] == "archived"


def test_lifecycle_routes_are_ownership_scoped(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    client.put(f"/agent/missions/{mission_id}/challenge", json={"prompt": "Double the input."})

    client.post("/auth/logout")
    login(client, "agent-b@test.local")
    assert client.post(f"/agent/missions/{mission_id}/publish").status_code == 404
    assert client.post(f"/agent/missions/{mission_id}/unpublish").status_code == 404
    assert client.post(f"/agent/missions/{mission_id}/archive").status_code == 404
    assert client.post(f"/agent/missions/{mission_id}/duplicate").status_code == 404


def test_duplicate_copies_challenge_content_as_a_new_draft(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={"prompt": "Double the input.", "starter_code": "pass", "difficulty": "medium"},
    )
    client.post(
        f"/agent/missions/{mission_id}/testcases",
        json={"name": "case 1", "expected_output": "6", "input_data": "3", "visibility": "visible"},
    )
    client.post(f"/agent/missions/{mission_id}/hints", json={"text": "Think about multiplication.", "point_cost": 5})
    client.post(f"/agent/missions/{mission_id}/publish")

    res = client.post(f"/agent/missions/{mission_id}/duplicate")
    assert res.status_code == 201
    copy = res.get_json()
    assert copy["id"] != mission_id
    assert copy["title"] == "Gateway Node (copy)"
    # The copy is always a fresh draft, regardless of the source mission's status.
    assert copy["status"] == "draft"
    assert copy["challenge"]["prompt"] == "Double the input."
    assert copy["challenge"]["difficulty"] == "medium"
    assert len(copy["test_cases"]) == 1
    assert copy["test_cases"][0]["expected_output"] == "6"
    assert len(copy["hints"]) == 1

    # Original mission is untouched.
    original = client.get(f"/agent/missions/{mission_id}").get_json()
    assert original["status"] == "published"
    assert len(original["test_cases"]) == 1


def test_uploading_a_challenge_is_audit_logged(client, app, two_agents):
    from app.models import EventLog

    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    client.put(f"/agent/missions/{mission_id}/challenge", json={"prompt": "Double the input."})

    with app.app_context():
        actions = [log.action for log in EventLog.query.all()]
        assert "challenge_uploaded" in actions


def test_uploading_an_evidence_asset_is_audit_logged(client, app, two_agents):
    from app.models import EventLog

    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    res = client.post(
        f"/agent/missions/{mission_id}/assets",
        json={"label": "server.log", "file_type": "log", "content": "connection refused"},
    )
    assert res.status_code == 201

    with app.app_context():
        logged = EventLog.query.filter_by(action="asset_uploaded").first()
        assert logged is not None
        assert logged.event_metadata == "server.log"


# 1x1 transparent PNG, real magic bytes -- smallest valid PNG that will pass signature sniffing.
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _upload_file(client, mission_id, label, filename, raw_bytes):
    import io

    return client.post(
        f"/agent/missions/{mission_id}/assets",
        data={"label": label, "file": (io.BytesIO(raw_bytes), filename)},
        content_type="multipart/form-data",
    )


def test_uploading_a_real_image_file_stores_binary_and_is_downloadable(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)

    res = _upload_file(client, mission_id, "Crash screenshot", "crash.png", _PNG_BYTES)
    assert res.status_code == 201
    body = res.get_json()
    assert body["has_binary"] is True
    assert body["mime_type"] == "image/png"
    assert body["content"] == ""

    download = client.get(f"/agent/assets/{body['id']}/download")
    assert download.status_code == 200
    assert download.data == _PNG_BYTES
    assert download.headers["Content-Type"] == "image/png"


def test_uploading_an_oversized_file_is_rejected(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)

    from app.blueprints.agent import MAX_ASSET_BYTES

    oversized = _PNG_BYTES[:8] + b"\x00" * (MAX_ASSET_BYTES + 1)
    res = _upload_file(client, mission_id, "Too big", "huge.png", oversized)
    assert res.status_code in (400, 413)


def test_uploading_a_file_whose_bytes_dont_match_its_extension_is_rejected(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)

    res = _upload_file(client, mission_id, "Fake png", "fake.png", b"this is not a png")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_uploading_a_disallowed_extension_is_rejected(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)

    res = _upload_file(client, mission_id, "Script", "payload.exe", b"MZ\x90\x00")
    assert res.status_code == 400


def test_download_asset_404s_for_non_owned_asset(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    res = _upload_file(client, mission_id, "Crash screenshot", "crash.png", _PNG_BYTES)
    asset_id = res.get_json()["id"]

    client.post("/auth/logout")
    login(client, "agent-b@test.local")
    assert client.get(f"/agent/assets/{asset_id}/download").status_code == 404


def test_deleting_a_mission_with_a_code_submission_does_not_crash(client, app, two_agents):
    # Reproduces a real bug: CodeSubmission had no delete cascade from TeamMission, so deleting a
    # Mission with any recorded submission (Run Visible Tests or Submit) hit a NOT NULL FK
    # violation instead of a clean delete. admin_reset_service.py worked around this for the
    # team-reset path specifically with a manual bulk-delete; this proves the general DELETE
    # /agent/missions/<id> path (unprotected by that workaround) is now fixed at the model level.
    from app.extensions import db
    from app.models import Challenge, CodeSubmission, Mission, Team, TeamMission

    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    client.put(f"/agent/missions/{mission_id}/challenge", json={"prompt": "Double it."})

    with app.app_context():
        team = Team(name="Crash Test Squad", score=0, integrity=100)
        team.set_key("CRASH01")
        db.session.add(team)
        db.session.commit()
        team_mission = TeamMission(team_id=team.id, mission_id=mission_id, status="in_progress")
        db.session.add(team_mission)
        db.session.commit()
        db.session.add(
            CodeSubmission(
                team_mission_id=team_mission.id,
                code="print(1)",
                mode="run_visible",
                total_tests=1,
                passed_tests=1,
                percent_score=100,
                passed=True,
            )
        )
        db.session.commit()

    res = client.delete(f"/agent/missions/{mission_id}")
    assert res.status_code == 200, res.get_json()

    with app.app_context():
        assert Mission.query.get(mission_id) is None
        assert CodeSubmission.query.count() == 0


def test_existing_text_mode_asset_reports_no_binary(client, app, two_agents):
    login(client, "agent-a@test.local")
    mission_id = _create_mission(client)
    res = client.post(
        f"/agent/missions/{mission_id}/assets",
        json={"label": "server.log", "file_type": "log", "content": "connection refused"},
    )
    body = res.get_json()
    assert body["has_binary"] is False
    assert body["mime_type"] is None
    assert body["content"] == "connection refused"
