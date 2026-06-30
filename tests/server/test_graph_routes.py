def test_graph_neighbors_endpoint_returns_out_neighbors(client):
    m = client.app.state.relio_memory
    alice = m.add_node("Alice")
    acme = m.add_node("Acme")
    m.add_edge(alice.id, "works_at", acme.id)

    resp = client.get("/api/graph/neighbors", params={"id": alice.id})
    assert resp.status_code == 200
    nbrs = resp.json()["neighbors"]
    assert [n["content"] for n in nbrs] == ["Acme"]
    assert nbrs[0]["type"] == "node"


def test_graph_neighbors_endpoint_reverse_direction(client):
    m = client.app.state.relio_memory
    alice = m.add_node("Alice")
    acme = m.add_node("Acme")
    m.add_edge(alice.id, "works_at", acme.id)

    resp = client.get(
        "/api/graph/neighbors", params={"id": acme.id, "direction": "in"}
    )
    assert [n["content"] for n in resp.json()["neighbors"]] == ["Alice"]
