def test_full_flow(auth_client, auth_setup):
    token = auth_setup["admin_token"]
    r = auth_client.post("/rooms", json={"name": "Dragon#1"})
    room_id = r.json()["id"]

    with auth_client.websocket_connect(f"/ws/{room_id}?token={token}") as ws1:
        ws1.receive_json()
        ws1.send_json({"type": "place_token", "payload": {"token_id": "t1", "x": 5, "y": 5}})
        ws1.receive_json()

        ws1.send_json({"type": "set_turn_order", "payload": {"order": ["t1"]}})
        ws1.receive_json()

        ws1.send_json({"type": "start_game", "payload": {}})
        ws1.receive_json()

        ws1.send_json({"type": "move", "payload": {"token_id": "t1", "path": [[6, 5], [7, 5]]}})
        ws1.receive_json()

        ws1.send_json({"type": "dice_roll", "payload": {"sides": 20, "modifier": 0}})
        ws1.receive_json()

        ws1.send_json({"type": "chat", "payload": {"channel": "hall", "text": "hello"}})
        ws1.receive_json()

        ws1.send_json({"type": "end_turn", "payload": {}})
        ws1.receive_json()
