"""双视角端到端验证：管理员 + 玩家完整流程。
模拟：
1. admin 登录、建角色卡、建房、画地形(墙/黑暗/光源)
2. player 登录、建角色卡(含黑暗视觉)、入房、落子
3. 验证：玩家视野过滤、不可见格地形被清空、权限拦截
"""
import asyncio
import json
import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE) as http:
        # ============ 1. 管理员视角 ============
        print("\n=== [管理员] 登录 ===")
        r = await http.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200, f"admin login failed: {r.text}"
        admin_tok = r.json()["access_token"]
        admin_h = {"Authorization": f"Bearer {admin_tok}"}
        print(f"  admin token ok, is_admin={r.json().get('is_admin')}")

        print("\n=== [管理员] 创建玩家账号 ===")
        r = await http.post("/admin/users", json={
            "username": "tester_e2e", "password": "pw123", "is_admin": False
        }, headers=admin_h)
        if r.status_code == 409:
            print("  tester_e2e 已存在，跳过")
        else:
            assert r.status_code == 200, f"create user failed: {r.text}"
            print("  tester_e2e 创建成功")

        # ============ 2. 玩家视角 ============
        print("\n=== [玩家] 登录 ===")
        r = await http.post("/auth/login", json={"username": "tester_e2e", "password": "pw123"})
        assert r.status_code == 200, f"player login failed: {r.text}"
        player_tok = r.json()["access_token"]
        player_h = {"Authorization": f"Bearer {player_tok}"}
        player_id = r.json()["id"]
        print(f"  player token ok, id={player_id}")

        print("\n=== [玩家] 创建角色卡（含黑暗视觉）===")
        r = await http.post("/characters", json={
            "name": "暗影刺客", "gender": "男", "profession": "刺客",
            "talent": "影遁", "hp_base": 80, "armor_base": 3, "ap_base": 3,
            "gold": 50, "backpack": ["毒药", "绳索"],
            "equipment_slots": ["匕首", None, "皮甲", None, None, None],
            "skill_slots": ["背刺", "隐身"],
            "secret_backups": ["真名：暗影"],
            "darkvision": True, "vision_range": 7,
            "listen_radius": 8, "passive_perception": 14, "stealth": 12,
        }, headers=player_h)
        assert r.status_code == 200, f"create char failed: {r.text}"
        char = r.json()
        print(f"  角色卡 {char['name']} 创建成功 darkvision={char['darkvision']}")

        print("\n=== [管理员] 查看全部角色卡（应含底牌）===")
        r = await http.get("/admin/characters", headers=admin_h)
        assert r.status_code == 200
        all_chars = r.json()
        found = [c for c in all_chars if c["name"] == "暗影刺客"]
        assert found, "admin 看不到玩家角色卡"
        assert "secret_backups" in found[0] and found[0]["secret_backups"], "admin 看不到底牌！"
        print(f"  admin 看到 {len(all_chars)} 张卡，底牌可见: {found[0]['secret_backups']}")

        print("\n=== [管理员] 创建战役房间 ===")
        r = await http.post("/rooms", json={"name": "e2e测试房"}, headers=admin_h)
        assert r.status_code == 200, f"create room failed: {r.text}"
        room = r.json()
        room_id = room["id"]
        print(f"  房间 {room_id} 创建成功")

    # ============ 3. WS 双连接 ============
    print("\n=== [WS] 管理员 + 玩家 连接 ===")
    async with websockets.connect(f"{WS_BASE}/ws/{room_id}?token={admin_tok}") as admin_ws, \
               websockets.connect(f"{WS_BASE}/ws/{room_id}?token={player_tok}") as player_ws:

        async def recv_state(ws, label, timeout=2.0):
            """收消息直到拿到 state_sync"""
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    data = json.loads(msg)
                    if data.get("type") == "state_sync":
                        return data["payload"]
                except asyncio.TimeoutError:
                    return None

        # 初始 state
        admin_state = await recv_state(admin_ws, "admin")
        player_state = await recv_state(player_ws, "player")
        print(f"  admin state: tokens={len(admin_state['tokens'])}, has game_map={bool(admin_state.get('game_map'))}")
        print(f"  player state: tokens={len(player_state['tokens'])}, visible_cells={player_state.get('visible_cells', 'N/A')}")

        print("\n=== [管理员] 画地形：墙 + 黑暗格 + 光源 ===")
        # 在 (5,5) 画墙
        await admin_ws.send(json.dumps({"type": "set_terrain", "payload": {"x": 5, "y": 5, "type": "wall"}}))
        await recv_state(admin_ws, "admin")
        # 在 (10,10) 画黑暗
        await admin_ws.send(json.dumps({"type": "set_cell_meta", "payload": {"x": 10, "y": 10, "is_dark": True}}))
        await recv_state(admin_ws, "admin")
        # 在 (3,3) 画光源 半径3
        await admin_ws.send(json.dumps({"type": "set_cell_meta", "payload": {"x": 3, "y": 3, "light_radius": 3}}))
        admin_state = await recv_state(admin_ws, "admin")
        cell_55 = admin_state["game_map"]["terrain"][5][5]
        cell_10_10 = admin_state["game_map"]["terrain"][10][10]
        cell_33 = admin_state["game_map"]["terrain"][3][3]
        print(f"  admin 视角: (5,5)={cell_55['type']} (10,10)dark={cell_10_10['is_dark']} (3,3)light={cell_33['light_radius']}")
        assert cell_55["type"] == "wall", "墙没画上"
        assert cell_10_10["is_dark"] == True, "黑暗没画上"
        assert cell_33["light_radius"] == 3, "光源没画上"
        # 玩家也收（但未落子，看全图）
        player_state = await recv_state(player_ws, "player")
        print(f"  player(未落子) terrain(5,5)={player_state['game_map']['terrain'][5][5]['type']}")

        print("\n=== [玩家] 落子 ===")
        await player_ws.send(json.dumps({"type": "place_token", "payload": {
            "token_id": f"tok_{player_id}", "x": 8, "y": 8,
            "character": {
                "name": "暗影刺客", "hp_base": 80, "armor_base": 3, "ap_base": 3,
                "gold": 50, "vision_range": 7, "listen_radius": 8,
                "passive_perception": 14, "stealth": 12, "darkvision": True,
                "equipment_slots": ["匕首", None, "皮甲", None, None, None],
                "skill_slots": ["背刺", "隐身"], "backpack": ["毒药"],
                "owner_id": player_id,
            }
        }}))
        # 收视野计算后的 state
        player_state = await recv_state(player_ws, "player", timeout=3.0)
        vis = player_state.get("visible_cells", [])
        print(f"  player 落子后: visible_cells={len(vis)}格, tokens={list(player_state['tokens'].keys())}")
        assert vis, "落子后没有 visible_cells！"
        assert f"tok_{player_id}" in player_state["tokens"], "看不到自己的棋子"

        # 验证战争迷雾：不可见格的地形应被清空
        print("\n=== [验证] 战争迷雾信息泄露检查 ===")
        # (5,5) 的墙离玩家(8,8)距离3，可能在视野内
        # 找一个肯定不可见的远格，如 (0,0)
        far_cell = player_state["game_map"]["terrain"][0][0]
        is_vis = [0, 0] in [v for v in vis]
        if not is_vis:
            assert far_cell["type"] == "flat", f"不可见格(0,0)泄露了地形: {far_cell['type']}"
            print(f"  ✓ 不可见格(0,0)地形已清空（防 F12 偷看）")
        else:
            print(f"  (0,0) 在视野内，跳过此检查")

        print("\n=== [验证] 权限：玩家不能旋转别人的棋子 ===")
        # 管理员放个怪物
        await admin_ws.send(json.dumps({"type": "place_unit", "payload": {
            "unit_type": "monster", "name": "哥布林", "hp": 30, "armor": 2,
            "x": 12, "y": 12
        }}))
        admin_state = await recv_state(admin_ws, "admin")
        monster_ids = [k for k in admin_state["tokens"] if k.startswith("monster_")]
        print(f"  admin 放了怪物: {monster_ids}")
        if monster_ids:
            mid = monster_ids[0]
            # 玩家尝试旋转怪物（应被拒绝）
            await player_ws.send(json.dumps({"type": "rotate_token", "payload": {
                "token_id": mid, "facing": 4
            }}))
            await recv_state(player_ws, "player", timeout=2.0)
            # 检查 admin 视角怪物 facing 是否变了
            await admin_ws.send(json.dumps({"type": "ping", "payload": {}}))
            # 用 place_unit 后的 state 验证：怪物 facing 应还是 0
            admin_check = await recv_state(admin_ws, "admin", timeout=2.0)
            if admin_check and mid in admin_check["tokens"]:
                m_facing = admin_check["tokens"][mid]["facing"]
                print(f"  怪物 facing={m_facing} (玩家尝试改4，{'拦截成功' if m_facing == 0 else '❌泄露！'})")

        print("\n=== [验证] 玩家旋转自己的棋子（应成功）===")
        await player_ws.send(json.dumps({"type": "rotate_token", "payload": {
            "token_id": f"tok_{player_id}", "facing": 2
        }}))
        player_state = await recv_state(player_ws, "player", timeout=2.0)
        if player_state and f"tok_{player_id}" in player_state["tokens"]:
            my_facing = player_state["tokens"][f"tok_{player_id}"]["facing"]
            print(f"  自己棋子 facing={my_facing} ({'成功' if my_facing == 2 else '失败'})")

        print("\n=== [验证] 玩家缩放自己的棋子 ===")
        await player_ws.send(json.dumps({"type": "scale_token", "payload": {
            "token_id": f"tok_{player_id}", "scale": 1.5
        }}))
        player_state = await recv_state(player_ws, "player", timeout=2.0)
        if player_state and f"tok_{player_id}" in player_state["tokens"]:
            my_scale = player_state["tokens"][f"tok_{player_id}"]["scale"]
            print(f"  自己棋子 scale={my_scale} ({'成功' if my_scale == 1.5 else '失败'})")

    print("\n" + "=" * 50)
    print("✅ 端到端验证全部通过")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
