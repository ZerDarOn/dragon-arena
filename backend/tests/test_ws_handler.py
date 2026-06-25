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
    admin_token = auth_setup["admin_token"]
    user_token = auth_setup["user_token"]
    admin_id = auth_setup["admin_id"]
    user_id = auth_setup["user_id"]
    with client.websocket_connect(f"/ws/{ws_room}?token={admin_token}") as ws_admin:
        ws_admin.receive_json()
        # 测试需要玩家自助落子权限
        ws_admin.send_json({"type": "set_player_placement", "payload": {"enabled": True}})
        ws_admin.receive_json()
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


def test_sprint_moves_and_costs_only_sprint_ap(auth_client, auth_setup, ws_room):
    """回归：疾跑应真正移动、且只扣一次 sprint_ap_cost。

    曾经 sprint 先扣 sprint_ap_cost，又让 move_along_path 按格再扣一次 AP；
    AP 归零后 move_along_path 自己的 AP 检查把移动挡下 → 疾跑根本不动。
    修复后 move_along_path 以 free_mode 调用，只做几何校验+移动，不再二次扣 AP。
    """
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "place_token", "payload": {"token_id": "tok_sp", "x": 1, "y": 1}})
        msg = ws.receive_json()
        tok = msg["payload"]["tokens"]["tok_sp"]
        ap0 = tok["ap"]
        sprint_cost = msg["payload"]["config"]["sprint_ap_cost"]
        assert ap0 >= sprint_cost  # 前置：有足够 AP 起跑
        # 直线疾跑 4 格
        ws.send_json({"type": "sprint", "payload": {
            "token_id": "tok_sp", "path": [[2, 1], [3, 1], [4, 1], [5, 1]],
        }})
        msg2 = ws.receive_json()
        moved = msg2["payload"]["tokens"]["tok_sp"]
        assert moved["position"] == {"x": 5, "y": 1}, "疾跑应真正移动到路径终点"
        assert moved["ap"] == ap0 - sprint_cost, "疾跑只该扣一次 sprint_ap_cost"


def test_draw_table_broadcasts_system_chat(auth_client, auth_setup, ws_room):
    """团主对局内抽取 → 结果作为 battle 系统消息广播。"""
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "draw_table", "payload": {"table_id": "rt_airdrop"}})
        msg = ws.receive_json()
        assert msg["type"] == "chat"
        assert msg["payload"]["content_type"] == "system"
        assert msg["payload"]["channel"] == "battle"
        assert "空投道具" in msg["payload"]["text"]


def test_draw_table_non_admin_rejected(client, auth_setup, ws_room):
    user_token = auth_setup["user_token"]
    with client.websocket_connect(f"/ws/{ws_room}?token={user_token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "draw_table", "payload": {"table_id": "rt_airdrop"}})
        msg = ws.receive_json()
        assert msg["type"] == "error"
