def test_create_room(client):
    r = client.post("/rooms", json={"name": "Dragon#1", "host_id": "host1"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Dragon#1"
    assert "host1" in data["players"]


def test_list_rooms(client):
    r = client.get("/rooms")
    before = len(r.json())
    client.post("/rooms", json={"name": "r1", "host_id": "h1"})
    client.post("/rooms", json={"name": "r2", "host_id": "h2"})
    r = client.get("/rooms")
    assert len(r.json()) == before + 2


def test_get_room(client):
    r = client.post("/rooms", json={"name": "r1", "host_id": "h1"})
    room_id = r.json()["id"]
    r = client.get(f"/rooms/{room_id}")
    assert r.json()["id"] == room_id


def test_get_nonexistent_room(client):
    r = client.get("/rooms/nonexistent")
    assert r.status_code == 404


def test_update_room_config(client):
    r = client.post("/rooms", json={"name": "r1", "host_id": "h1"})
    room_id = r.json()["id"]
    r = client.patch(f"/rooms/{room_id}/config", json={"vision_range": 8, "map_width": 20})
    assert r.json()["config"]["vision_range"] == 8
    assert r.json()["config"]["map_width"] == 20
