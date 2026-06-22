from pydantic import BaseModel
from typing import Any, Optional


class GameEvent(BaseModel):
    timestamp: int
    big_turn: int
    sub_turn: int
    actor: str
    action: str  # move/attack/dice/modify_value/add_state/send_message
                 # equip/trigger_entity/apply_modifier/end_turn/revive/death
    target: Optional[str] = None
    params: dict = {}
    result: Optional[Any] = None
