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
