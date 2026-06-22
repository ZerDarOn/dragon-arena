import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ws_room(auth_client):
    """Create a room as admin, return (client_with_admin_header, room_id, admin_token)."""
    r = auth_client.post("/rooms", json={"name": "ws-test"})
    return r.json()["id"]


def test_ws_connect(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state_sync"


def test_ws_send_hall_message(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "payload": {"channel": "hall", "text": "hello"}})
        msg = ws.receive_json()
        assert msg["type"] == "chat"


def test_ws_dice_roll(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "dice_roll", "payload": {"sides": 20, "modifier": 2}})
        msg = ws.receive_json()
        assert msg["type"] == "dice_result"
        assert msg["payload"]["total"] == msg["payload"]["value"] + 2


def test_ws_unauth_rejected(client, auth_client):
    """WS without token should be rejected."""
    r = auth_client.post("/rooms", json={"name": "x"})
    room_id = r.json()["id"]
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/{room_id}") as ws:
            ws.receive_json()
