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


def test_host_nickname_is_set_on_connect(auth_client, auth_setup, ws_room):
    """房主的 Player 记录是在建房时创建的（早于 WS 连接），nickname 应该照样能填上，
    不应该永远显示成一串 user id。"""
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        msg = ws.receive_json()
        host_player = msg["payload"]["players"][auth_setup["admin_id"]]
        assert host_player["nickname"] == "admin_test"


def test_place_token_cannot_steal_others_token(client, auth_setup, ws_room):
    """非管理员不能顶替别人已经落子的 token。"""
    admin_token = auth_setup["admin_token"]
    user_token = auth_setup["user_token"]
    with client.websocket_connect(f"/ws/{ws_room}?token={admin_token}") as ws_admin:
        ws_admin.receive_json()
        ws_admin.send_json({"type": "place_token", "payload": {"token_id": "tok_admin", "x": 1, "y": 1}})
        ws_admin.receive_json()

        with client.websocket_connect(f"/ws/{ws_room}?token={user_token}") as ws_user:
            ws_user.receive_json()
            ws_user.send_json({"type": "place_token", "payload": {"token_id": "tok_admin", "x": 2, "y": 2}})
            msg = ws_user.receive_json()
            assert msg["type"] == "error"


def test_place_token_non_admin_cannot_spoof_owner(client, auth_setup, ws_room):
    """非管理员伪造 character.owner_id 也没用，token 归属永远是发消息的人自己。"""
    user_token = auth_setup["user_token"]
    admin_id = auth_setup["admin_id"]
    user_id = auth_setup["user_id"]
    with client.websocket_connect(f"/ws/{ws_room}?token={user_token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "place_token", "payload": {
            "token_id": "tok_x", "x": 3, "y": 3,
            "character": {"name": "冒充", "owner_id": admin_id},
        }})
        msg = ws.receive_json()
        token = msg["payload"]["tokens"]["tok_x"]
        assert token["owner_id"] == user_id


def test_admin_can_place_token_on_behalf_of_player(client, auth_setup, ws_room):
    """管理员从角色卡列表拖别人的卡到地图时，归属应该是那个玩家本人，不是管理员。"""
    admin_token = auth_setup["admin_token"]
    user_token = auth_setup["user_token"]
    user_id = auth_setup["user_id"]
    # 玩家先连进房间（才会有 Player 记录），然后管理员代他摆放/挪动 token
    with client.websocket_connect(f"/ws/{ws_room}?token={user_token}") as ws_user:
        ws_user.receive_json()
        with client.websocket_connect(f"/ws/{ws_room}?token={admin_token}") as ws_admin:
            ws_admin.receive_json()
            ws_admin.send_json({"type": "place_token", "payload": {
                "token_id": "tok_proxy", "x": 4, "y": 4,
                "character": {"name": "代摆放", "owner_id": user_id},
            }})
            msg = ws_admin.receive_json()
            token = msg["payload"]["tokens"]["tok_proxy"]
            assert token["owner_id"] == user_id
            assert token["character_name"] == "代摆放"
            assert msg["payload"]["players"][user_id]["token_id"] == "tok_proxy"
