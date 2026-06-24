"""Test that _send_state_to_player hides backpack/skill_slots/item_charges
from other players' visible tokens.

Per design doc §7.1:
- equipment_slots: visible to others (worn items)
- backpack: completely hidden from others
- skill_slots: completely hidden from others
- item_charges: hidden (reveals backpack contents)
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.room import Room, Token, Player, StateTag
from app.config import RoomConfig


def _make_token(tid, x=5, y=5, **kw):
    """Helper: create a token with sensible defaults."""
    defaults = dict(
        id=tid, type="player", position={"x": x, "y": y},
        hp=100, max_hp=100, armor=5, ap=2, max_ap=2,
        equipment_slots=[None]*6, skill_slots=[None, None],
        backpack=["secret_item"], item_charges={"secret_item": 3},
        character_name=kw.pop("name", "TestChar"),
    )
    defaults.update(kw)
    return Token(**defaults)


def _make_room(*tokens):
    """Helper: create a room with given tokens."""
    tids = [t.id for t in tokens]
    players = {
        f"player_{t.id}": Player(
            id=f"player_{t.id}", name=t.character_name or t.id,
            token_id=t.id, nickname=t.character_name or t.id,
        )
        for t in tokens
    }
    return Room(
        id="test_room", name="test",
        config=RoomConfig(fog_of_war_enabled=False),
        players=players,
        tokens={t.id: t for t in tokens},
        turn_order=tids,
    )


@pytest.mark.asyncio
async def test_backpack_hidden_for_other_visible_token():
    """When fog_of_war is OFF (all visible), other player's backpack must still be hidden."""
    from app.ws.handler import RoomGameState, _send_state_to_player
    from app.ws.connection_manager import ConnectionManager

    p1 = _make_token("tok_p1", name="Hero", backpack=["secret_potion", "hidden_blade"],
                     skill_slots=["stealth_strike", None],
                     item_charges={"secret_potion": 2})
    p2 = _make_token("tok_p2", x=6, name="Rogue", backpack=["lockpick"])
    room = _make_room(p1, p2)

    gs = RoomGameState(room)

    # Mock connection manager
    captured = {}
    mgr = ConnectionManager()

    # Register p2 as a connected non-admin player
    mgr.rooms["test_room"] = {"player_tok_p2": AsyncMock()}
    mgr.admins["test_room"] = set()  # p2 is NOT admin

    async def fake_send(rid, pid, msg):
        captured["msg"] = msg

    mgr.send_to_player = fake_send

    import app.ws.handler as h
    orig_mgr = h.connection_mgr
    h.connection_mgr = mgr
    try:
        await _send_state_to_player(gs, "test_room", "player_tok_p2")
    finally:
        h.connection_mgr = orig_mgr

    msg = captured.get("msg")
    assert msg is not None, "No state_sync sent"
    assert msg["type"] == "state_sync"

    p1_in_view = msg["payload"]["tokens"].get("tok_p1")
    assert p1_in_view is not None, "P1 token should be visible to P2"

    # backpack must be empty for other players
    assert p1_in_view.get("backpack") == [], \
        f"backpack should be hidden, got: {p1_in_view.get('backpack')}"

    # skill_slots must be empty for other players
    assert p1_in_view.get("skill_slots") == [None, None], \
        f"skill_slots should be hidden, got: {p1_in_view.get('skill_slots')}"

    # item_charges must be empty for other players
    assert p1_in_view.get("item_charges") == {}, \
        f"item_charges should be hidden, got: {p1_in_view.get('item_charges')}"

    # equipment_slots SHOULD be visible (worn items)
    assert p1_in_view.get("equipment_slots") is not None, \
        "equipment_slots should be visible for worn items"


@pytest.mark.asyncio
async def test_own_token_not_filtered():
    """Player's own token should NOT be filtered (they see their own backpack)."""
    from app.ws.handler import RoomGameState, _send_state_to_player
    from app.ws.connection_manager import ConnectionManager

    p1 = _make_token("tok_p1", name="Hero", backpack=["my_item"],
                     skill_slots=["my_skill", None],
                     item_charges={"my_item": 5})
    room = _make_room(p1)

    gs = RoomGameState(room)

    captured = {}
    mgr = ConnectionManager()
    mgr.rooms["test_room"] = {"player_tok_p1": AsyncMock()}
    mgr.admins["test_room"] = set()

    async def fake_send(rid, pid, msg):
        captured["msg"] = msg

    mgr.send_to_player = fake_send

    import app.ws.handler as h
    orig_mgr = h.connection_mgr
    h.connection_mgr = mgr
    try:
        await _send_state_to_player(gs, "test_room", "player_tok_p1")
    finally:
        h.connection_mgr = orig_mgr

    msg = captured.get("msg")
    own = msg["payload"]["tokens"]["tok_p1"]
    assert own["backpack"] == ["my_item"], "Own backpack should be visible"
    assert own["skill_slots"] == ["my_skill", None], "Own skills should be visible"
    assert own["item_charges"] == {"my_item": 5}, "Own charges should be visible"
