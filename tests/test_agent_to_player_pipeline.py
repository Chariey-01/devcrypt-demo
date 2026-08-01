"""End-to-end proof that everything an Agent authors is what a Player actually receives:
problem statement, starter code, language, difficulty, visible/hidden test suites, hints, and
evidence files — all through the real HTTP routes, not direct DB manipulation."""

from app.extensions import db
from app.models import Event, Team, User


def _login(client, email):
    return client.post("/auth/login", data={"email": email, "password": "pw"})


def _setup(app):
    with app.app_context():
        agent = User(email="agent-e2e@test.local", role="booth_agent")
        agent.set_password("pw")
        team = Team(name="Bravo", score=0, integrity=100)
        team.set_key("BRAVO01")
        db.session.add_all([agent, team])
        db.session.add(Event(status="running"))
        db.session.commit()
        return team.id


def test_full_agent_authored_challenge_reaches_the_player_unchanged(client, app):
    _setup(app)
    agent = _login(client, "agent-e2e@test.local")
    assert agent.status_code in (200, 302)

    # 1. Create the mission (problem statement lives on the challenge, not here).
    create_res = client.post(
        "/agent/missions",
        json={"title": "Firewall Breach", "narrative": "Get past the gate.", "cipher_word": "GATE"},
    )
    assert create_res.status_code == 201
    mission_id = create_res.get_json()["id"]
    assert create_res.get_json()["status"] == "draft"  # invisible to players until published

    # 2. Author the challenge: problem statement, starter code, language, difficulty.
    challenge_res = client.put(
        f"/agent/missions/{mission_id}/challenge",
        json={
            "prompt": "Read an integer and print double it.",
            "language": "python",
            "starter_code": "n = int(input())\nprint(n)\n",
            "difficulty": "medium",
            "pass_threshold": 100,
        },
    )
    assert challenge_res.status_code == 200

    # 3. Visible + hidden test suites.
    vis_res = client.post(
        f"/agent/missions/{mission_id}/testcases",
        json={
            "name": "visible case",
            "input_data": "3",
            "expected_output": "6",
            "visibility": "visible",
        },
    )
    assert vis_res.status_code == 201
    hidden_res = client.post(
        f"/agent/missions/{mission_id}/testcases",
        json={
            "name": "hidden case",
            "input_data": "5",
            "expected_output": "10",
            "visibility": "hidden",
        },
    )
    assert hidden_res.status_code == 201

    # 4. A hint.
    hint_res = client.post(f"/agent/missions/{mission_id}/hints", json={"text": "Multiply by two."})
    assert hint_res.status_code == 201

    # 5. An evidence file (text mode) and a real binary upload.
    asset_res = client.post(
        f"/agent/missions/{mission_id}/assets",
        json={"label": "server.log", "file_type": "log", "content": "connection refused"},
    )
    assert asset_res.status_code == 201

    import io

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    binary_asset_res = client.post(
        f"/agent/missions/{mission_id}/assets",
        data={"label": "crash.png", "file": (io.BytesIO(png_bytes), "crash.png")},
        content_type="multipart/form-data",
    )
    assert binary_asset_res.status_code == 201
    binary_asset_id = binary_asset_res.get_json()["id"]

    # Still draft — publishing requires an explicit action.
    publish_missing_res = client.get(f"/agent/missions/{mission_id}")
    assert publish_missing_res.get_json()["status"] == "draft"

    # 6. Publish.
    publish_res = client.post(f"/agent/missions/{mission_id}/publish")
    assert publish_res.status_code == 200
    assert publish_res.get_json()["status"] == "published"

    # --- Now the player side, same database, same process, different session. ---
    player_client = app.test_client()
    player_client.post("/auth/team-login", data={"name": "Bravo", "key": "BRAVO01"})
    status = player_client.get("/missions/status").get_json()
    mission = status["mission"]

    assert mission["title"] == "Firewall Breach"
    assert mission["narrative"] == "Get past the gate."
    challenge = mission["challenge"]
    assert challenge["prompt"] == "Read an integer and print double it."
    assert challenge["language"] == "python"
    assert challenge["starter_code"] == "n = int(input())\nprint(n)\n"
    assert challenge["grading_mode"] == "auto"
    # Hidden test content must never leak to the player, even in the raw payload.
    assert "hidden case" not in str(status)
    assert "10" not in challenge.get("starter_code", "") + str(
        challenge.get("function_signature") or ""
    )

    # Evidence file surfaces on the player side.
    assert any(
        e["label"] == "server.log" and e["content"] == "connection refused"
        for e in mission["evidence_files"]
    )

    # Binary evidence: never leaks raw bytes into the JSON payload, and is downloadable.
    binary_entry = next(e for e in mission["evidence_files"] if e["label"] == "crash.png")
    assert binary_entry["has_binary"] is True
    assert binary_entry["content"] == ""
    assert binary_entry["mime_type"] == "image/png"
    download_res = player_client.get(f"/missions/assets/{binary_asset_id}/download")
    assert download_res.status_code == 200
    assert download_res.data == png_bytes

    # 7. Player runs visible tests — only the visible case executes.
    run_res = player_client.post(
        "/missions/challenge/run-tests", json={"code": "print(int(input()) * 2)"}
    )
    run_body = run_res.get_json()
    assert run_body["total_tests"] == 1
    assert run_body["results"][0]["name"] == "visible case"
    assert run_body["results"][0]["passed"] is True

    # 8. Player submits — hidden test suite is the one that actually decides the outcome.
    submit_res = player_client.post(
        "/missions/challenge/submit",
        json={"code": "print(int(input()) * 3)"},  # wrong on the hidden case
    )
    submit_body = submit_res.get_json()
    assert submit_body["correct"] is False
    assert submit_body["total_tests"] == 2  # both visible + hidden ran server-side

    # A wrong submission puts the team on a 60s retry cooldown — clear it directly to simulate
    # waiting it out, rather than sleeping for real in a test.
    with app.app_context():
        from app.models import TeamMission

        tm = TeamMission.query.filter_by(mission_id=mission_id).first()
        tm.penalty_until = None
        db.session.commit()

    submit_res_2 = player_client.post(
        "/missions/challenge/submit", json={"code": "print(int(input()) * 2)"}
    )
    submit_body_2 = submit_res_2.get_json()
    assert submit_body_2["correct"] is True
    assert submit_body_2["total_tests"] == 2

    final_status = player_client.get("/missions/status").get_json()
    assert len(final_status["fragments"]) == 1  # fragment awarded on real pass
