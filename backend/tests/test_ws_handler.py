import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def room_setup(client):
    r = client.post("/rooms", json={"name": "test", "host_id": "host1"})
    return r.json()["id"]


def test_ws_connect(client, room_setup):
    with client.websocket_connect(f"/ws/{room_setup}?player_id=p1&nickname=P1") as ws:
        msg = ws.receive_json()
        assert msg["type"] in ("connected", "state_sync")


def test_ws_send_hall_message(client, room_setup):
    with client.websocket_connect(f"/ws/{room_setup}?player_id=p1&nickname=P1") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "payload": {"channel": "hall", "text": "hello"}})
        msg = ws.receive_json()
        assert msg["type"] == "chat"


def test_ws_dice_roll(client, room_setup):
    with client.websocket_connect(f"/ws/{room_setup}?player_id=p1&nickname=P1") as ws:
        ws.receive_json()
        ws.send_json({"type": "dice_roll", "payload": {"sides": 20, "modifier": 2}})
        msg = ws.receive_json()
        assert msg["type"] == "dice_result"
        assert msg["payload"]["total"] == msg["payload"]["value"] + 2
