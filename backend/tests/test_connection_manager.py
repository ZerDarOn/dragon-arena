import pytest
from app.ws.connection_manager import ConnectionManager


class FakeWS:
    def __init__(self):
        self.sent = []
    async def send_json(self, data):
        self.sent.append(data)
    async def accept(self):
        pass


@pytest.mark.asyncio
async def test_connect():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect("room1", "p1", ws)
    assert "p1" in mgr.rooms["room1"]


@pytest.mark.asyncio
async def test_disconnect():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect("room1", "p1", ws)
    mgr.disconnect("room1", "p1")
    assert "p1" not in mgr.rooms.get("room1", {})


@pytest.mark.asyncio
async def test_send_to_player():
    mgr = ConnectionManager()
    ws1, ws2 = FakeWS(), FakeWS()
    await mgr.connect("room1", "p1", ws1)
    await mgr.connect("room1", "p2", ws2)
    await mgr.send_to_player("room1", "p1", {"type": "ping"})
    assert ws1.sent == [{"type": "ping"}]
    assert ws2.sent == []


@pytest.mark.asyncio
async def test_broadcast():
    mgr = ConnectionManager()
    ws1, ws2 = FakeWS(), FakeWS()
    await mgr.connect("room1", "p1", ws1)
    await mgr.connect("room1", "p2", ws2)
    await mgr.broadcast("room1", {"type": "ping"})
    assert ws1.sent == [{"type": "ping"}]
    assert ws2.sent == [{"type": "ping"}]


@pytest.mark.asyncio
async def test_send_to_many():
    mgr = ConnectionManager()
    ws1, ws2, ws3 = FakeWS(), FakeWS(), FakeWS()
    await mgr.connect("room1", "p1", ws1)
    await mgr.connect("room1", "p2", ws2)
    await mgr.connect("room1", "p3", ws3)
    await mgr.send_to_players("room1", ["p1", "p3"], {"type": "x"})
    assert ws1.sent == [{"type": "x"}]
    assert ws2.sent == []
    assert ws3.sent == [{"type": "x"}]
