import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_full_flow(client):
    r = client.post("/rooms", json={"name": "Dragon#1", "host_id": "host"})
    room_id = r.json()["id"]

    with client.websocket_connect(f"/ws/{room_id}?player_id=p1&nick=Alice") as ws1, \
         client.websocket_connect(f"/ws/{room_id}?player_id=p2&nick=Bob") as ws2:
        ws1.receive_json()
        ws2.receive_json()

        ws1.send_json({"type": "place_token", "payload": {"token_id": "t1", "x": 5, "y": 5}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "place_token", "payload": {"token_id": "t2", "x": 10, "y": 10}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "set_turn_order", "payload": {"order": ["t1", "t2"]}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "start_game", "payload": {}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "move", "payload": {"token_id": "t1", "path": [[6, 5], [7, 5]]}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "dice_roll", "payload": {"sides": 20, "modifier": 0}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "chat", "payload": {"channel": "hall", "text": "hello"}})
        ws1.receive_json(); ws2.receive_json()

        ws1.send_json({"type": "end_turn", "payload": {}})
        ws1.receive_json(); ws2.receive_json()
