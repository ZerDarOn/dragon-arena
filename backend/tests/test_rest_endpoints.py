def test_create_room(auth_client):
    r = auth_client.post("/rooms", json={"name": "Dragon#1"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Dragon#1"


def test_list_rooms(auth_client):
    r = auth_client.get("/rooms")
    before = len(r.json())
    auth_client.post("/rooms", json={"name": "r1"})
    auth_client.post("/rooms", json={"name": "r2"})
    r = auth_client.get("/rooms")
    assert len(r.json()) == before + 2


def test_get_room(auth_client):
    r = auth_client.post("/rooms", json={"name": "r1"})
    room_id = r.json()["id"]
    r = auth_client.get(f"/rooms/{room_id}")
    assert r.json()["id"] == room_id


def test_get_nonexistent_room(auth_client):
    r = auth_client.get("/rooms/nonexistent")
    assert r.status_code == 404


def test_update_room_config(auth_client):
    r = auth_client.post("/rooms", json={"name": "r1"})
    room_id = r.json()["id"]
    r = auth_client.patch(f"/rooms/{room_id}/config", json={"vision_range": 8, "map_width": 20})
    assert r.json()["config"]["vision_range"] == 8
    assert r.json()["config"]["map_width"] == 20


# ---- Auth-gating regressions ----

def test_unauth_create_room_rejected(client):
    r = client.post("/rooms", json={"name": "should_fail"})
    assert r.status_code == 401


def test_unauth_list_rooms_rejected(client):
    r = client.get("/rooms")
    assert r.status_code == 401
