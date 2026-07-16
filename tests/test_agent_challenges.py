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
