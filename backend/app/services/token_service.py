from typing import List, Tuple, Optional
from pydantic import BaseModel
from app.schemas.room import Room, Token, StateTag
from app.schemas.map import GameMap
from app.services.geometry_service import angle_to_direction
from app.services.map_service import MapService


class MoveResult(BaseModel):
    success: bool
    reason: str = ""
    new_position: Optional[dict] = None
    new_facing: Optional[int] = None
    ap_consumed: int = 0
    triggered_entities: List[str] = []


class TokenService:
    def __init__(self, room: Room, game_map: GameMap):
        self.room = room
        self.map = game_map
        self.map_svc = MapService(game_map)
        self.cfg = room.config

    def place_token(self, token_id: str, x: int, y: int) -> bool:
        for t in self.room.tokens.values():
            if t.position == {"x": x, "y": y} and not t.is_dead:
                return False
        if token_id not in self.room.tokens:
            self.room.tokens[token_id] = Token(id=token_id)
        self.room.tokens[token_id].position = {"x": x, "y": y}
        return True

    def move_along_path(self, token_id: str, path: List[Tuple[int, int]]) -> MoveResult:
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return MoveResult(success=False, reason="token has no position")
        if token.is_dead:
            return MoveResult(success=False, reason="token is dead")

        original = (token.position["x"], token.position["y"])
        triggered = []
        ap_needed = 0
        cur = original

        for step in path:
            dx = abs(step[0] - cur[0])
            dy = abs(step[1] - cur[1])
            if max(dx, dy) != 1:
                return MoveResult(success=False, reason=f"non-adjacent step: {cur}->{step}")
            if self.map_svc.is_wall(step[0], step[1]):
                return MoveResult(success=False, reason=f"wall at {step}")
            for other_id, other in self.room.tokens.items():
                if other_id == token_id or other.is_dead:
                    continue
                if other.position == {"x": step[0], "y": step[1]}:
                    return MoveResult(success=False, reason=f"occupied by {other_id}")
            ap_needed += self.cfg.move_ap_cost
            cur = step

        if token.ap < ap_needed:
            return MoveResult(success=False, reason=f"insufficient AP: need {ap_needed}, have {token.ap}")

        token.ap -= ap_needed
        if path:
            last = path[-1]
            token.position = {"x": last[0], "y": last[1]}
            if len(path) >= 2:
                fx = path[-1][0] - path[-2][0]
                fy = path[-1][1] - path[-2][1]
            else:
                fx = path[0][0] - original[0]
                fy = path[0][1] - original[1]
            token.facing = angle_to_direction(fx, fy)

        return MoveResult(
            success=True,
            new_position=token.position,
            new_facing=token.facing,
            ap_consumed=ap_needed,
            triggered_entities=triggered,
        )

    def modify_value(self, token_id: str, field: str, delta: int) -> None:
        token = self.room.tokens.get(token_id)
        if not token or not hasattr(token, field):
            return
        new_val = getattr(token, field) + delta
        if field == "hp":
            new_val = max(0, min(new_val, token.max_hp))
            if new_val == 0:
                token.is_dead = True
        setattr(token, field, new_val)

    def add_state(self, token_id: str, state_id: str, name: str, description: str,
                  ttl: int, intensity: Optional[int] = None) -> None:
        token = self.room.tokens.get(token_id)
        if not token:
            return
        token.states.append(StateTag(
            id=state_id, name=name, description=description,
            ttl=ttl, intensity=intensity,
        ))

    def remove_state(self, token_id: str, state_id: str) -> None:
        token = self.room.tokens.get(token_id)
        if not token:
            return
        token.states = [s for s in token.states if s.id != state_id]

    def tick_states(self) -> None:
        for token in self.room.tokens.values():
            kept = []
            for s in token.states:
                s.ttl -= 1
                if s.ttl > 0:
                    kept.append(s)
            token.states = kept
