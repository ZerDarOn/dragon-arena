"""E2E smoke test against running backend (port 8000).
Usage: python e2e_smoke.py <room_id>
Will: connect 2 WS clients (host + guest), host places token,
guest places token, host moves, both chat, host rolls dice.
Prints every received message.
"""
import asyncio
import json
import sys

import websockets


async def client(name: str, room_id: str, pid: str, nick: str):
    uri = f"ws://127.0.0.1:8000/ws/{room_id}?player_id={pid}&nickname={nick}"
    async with websockets.connect(uri) as ws:
        # first message should be state_sync
        first = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"[{name}] initial state_sync keys:", list(json.loads(first)["payload"].keys()))

        if name == "host":
            # place own token
            await ws.send(json.dumps({
                "type": "place_token",
                "payload": {"token_id": "host_tok", "x": 5, "y": 5},
            }))
            # wait broadcast
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "state_sync"
            assert data["payload"]["tokens"]["host_tok"]["position"] == {"x": 5, "y": 5}
            print(f"[{name}] place_token OK -> pos (5,5)")

        if name == "guest":
            # give host a moment to place first
            await asyncio.sleep(0.5)
            await ws.send(json.dumps({
                "type": "place_token",
                "payload": {"token_id": "guest_tok", "x": 10, "y": 10},
            }))
            # drop the initial host's state_sync if any
            try:
                while True:
                    await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                pass

        # host rolls dice
        if name == "host":
            await asyncio.sleep(0.8)
            await ws.send(json.dumps({"type": "dice_roll", "payload": {"sides": 20, "modifier": 2}}))
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "dice_result"
            assert "value" in data["payload"]
            print(f"[{name}] dice_result OK -> payload:", data["payload"])

        # host sends chat to hall
        if name == "host":
            await ws.send(json.dumps({"type": "chat", "payload": {"channel": "hall", "text": "hi all"}}))
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "chat"
            assert data["payload"]["text"] == "hi all"
            print(f"[{name}] hall chat OK ->", data["payload"]["text"])

        # host sends spatial chat
        if name == "host":
            await ws.send(json.dumps({"type": "chat", "payload": {"channel": "spatial_normal", "text": "nearby?"}}))
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "chat"
            print(f"[{name}] spatial chat OK -> recipients={data['payload'].get('recipients')}")

        # host moves own token
        if name == "host":
            await ws.send(json.dumps({
                "type": "move",
                "payload": {"token_id": "host_tok", "path": [[6, 5], [7, 5]]},
            }))
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "state_sync"
            pos = data["payload"]["tokens"]["host_tok"]["position"]
            assert pos == {"x": 7, "y": 5}, pos
            print(f"[{name}] move OK -> new pos {pos}")

        await asyncio.sleep(0.3)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python e2e_smoke.py <room_id>")
        sys.exit(1)
    room_id = sys.argv[1]
    print(f"=== E2E smoke test against room {room_id} ===")

    # host first (so room has a host)
    host_task = asyncio.create_task(client("host", room_id, "host1", "DM"))
    # guest 0.2s later
    await asyncio.sleep(0.2)
    guest_task = asyncio.create_task(client("guest", room_id, "guest1", "Player2"))

    await host_task
    await guest_task
    print("=== ALL E2E CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
