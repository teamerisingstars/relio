def test_query_endpoint_filters_by_metadata(client):
    client.post(
        "/api/memory",
        json={"content": "task one", "type": "fact", "metadata": {"category": "task"}},
    )
    client.post(
        "/api/memory",
        json={"content": "idea one", "type": "semantic", "metadata": {"category": "idea"}},
    )
    resp = client.post("/api/memory/query", json={"where": {"category": "task"}})
    assert resp.status_code == 200
    assert [r["content"] for r in resp.json()["results"]] == ["task one"]


def test_query_endpoint_filters_by_type(client):
    client.post("/api/memory", json={"content": "f", "type": "fact"})
    client.post("/api/memory", json={"content": "s", "type": "semantic"})
    resp = client.post("/api/memory/query", json={"type": "fact"})
    assert [r["content"] for r in resp.json()["results"]] == ["f"]
