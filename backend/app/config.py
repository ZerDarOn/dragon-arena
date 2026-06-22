from pydantic import BaseModel
from typing import List


class RoomConfig(BaseModel):
    # Map
    map_width: int = 30
    map_height: int = 30
    vision_range: int = 6
    move_ap_cost: int = 1
    sprint_ap_cost: int = 2
    sprint_distance: int = 4
    height_diff_enabled: bool = True

    # Combat
    start_hp: int = 100
    start_armor: int = 5
    start_ap: int = 2
    creation_points: int = 30
    dc_melee: int = 8
    dc_mid: int = 12
    dc_ranged: int = 16
    crit_success: int = 20
    crit_fail: int = 1
    defend_ap_cost: int = 1

    # Economy
    creation_to_gold: int = 20
    kill_drop_gold: int = 50

    # Score
    score_kill: int = 30
    score_survive_per_turn: int = 2
    score_boss_kill: int = 30
    assist_ratio: float = 0.3
    ranking_table_8p: List[int] = [40, 28, 20, 15, 10, 6, 3, 3]

    # Chat
    speak_radius: int = 6
    shout_multiplier: int = 2
    sound_through_wall: bool = False
    eavesdrop_bonus: int = 5

    # Turn
    turn_time_limit_sec: int = 10
    ap_regen: int = 2
