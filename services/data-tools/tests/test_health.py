def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_tools_returns_tools(client):
    response = client.get("/tools")

    assert response.status_code == 200
    body = response.json()
    assert "tools" in body
    assert {tool["name"] for tool in body["tools"]} >= {"load_dataset", "safe_sql_query"}
