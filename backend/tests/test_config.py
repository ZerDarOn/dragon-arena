from app.config import RoomConfig


def test_default_config():
    cfg = RoomConfig()
    assert cfg.map_width == 30
    assert cfg.map_height == 30
    assert cfg.vision_range == 6
    assert cfg.move_ap_cost == 1
    assert cfg.sprint_ap_cost == 2
    assert cfg.sprint_distance == 4
    assert cfg.start_hp == 100
    assert cfg.start_armor == 5
    assert cfg.start_ap == 2
    assert cfg.creation_points == 30
    assert cfg.dc_melee == 8
    assert cfg.dc_mid == 12
    assert cfg.dc_ranged == 16
    assert cfg.crit_success == 20
    assert cfg.crit_fail == 1
    assert cfg.defend_ap_cost == 1
    assert cfg.speak_radius == 6
    assert cfg.shout_multiplier == 2
    assert cfg.sound_through_wall is False
    assert cfg.turn_time_limit_sec == 10


def test_custom_config_overrides():
    cfg = RoomConfig(map_width=20, map_height=20, vision_range=4)
    assert cfg.map_width == 20
    assert cfg.vision_range == 4
    assert cfg.map_height == 20
