from app.services.map_service import MapService
from app.schemas.map import GameMap, TerrainCell
import json


# ─── 旧测试更新（检查三维字段而非 type） ───

def test_set_terrain():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_terrain(3, 4, "wall")
    cell = m.terrain[4][3]
    assert cell.terrain_type == "stone"
    assert cell.blocks_movement is True
    assert cell.blocks_vision is True
    assert cell.wall_render == "solid"


def test_set_terrain_out_of_bounds():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_terrain(99, 99, "wall")
    assert m.terrain[0][0].terrain_type == "flat"


def test_fill_area():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.fill_area(2, 2, 4, 4, "grass")
    for y in range(2, 5):
        for x in range(2, 5):
            assert m.terrain[y][x].terrain_type == "grass"


def test_clear_terrain():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_terrain(3, 3, "wall")
    svc.clear_terrain(3, 3)
    assert m.terrain[3][3].terrain_type == "flat"
    assert m.terrain[3][3].blocks_movement is False


def test_set_height():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_height(2, 2, 1)
    assert m.terrain[2][2].height == 1


def test_set_smoke():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_smoke(2, 2, ttl=3)
    assert m.terrain[2][2].is_smoke is True
    assert m.terrain[2][2].smoke_ttl == 3


def test_decrement_smoke():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_smoke(2, 2, ttl=2)
    svc.tick_smoke()
    assert m.terrain[2][2].smoke_ttl == 1
    assert m.terrain[2][2].is_smoke is True
    svc.tick_smoke()
    assert m.terrain[2][2].smoke_ttl is None
    assert m.terrain[2][2].is_smoke is False


# ─── 三谓词测试（ADR-2：互不调用） ───

def test_is_passable():
    """移动碰撞：blocks_movement 控制。"""
    m = GameMap(width=5, height=5)
    svc = MapService(m)
    # 默认平地可走
    assert svc.is_passable(0, 0) is True
    # 实体墙不可走
    svc.paint_cell(1, 1, preset="wall")
    assert svc.is_passable(1, 1) is False
    # 玻璃墙可走（blocks_movement=false）
    svc.paint_cell(2, 2, preset="glass_wall")
    assert svc.is_passable(2, 2) is True
    # 门关着不可走
    svc.paint_cell(3, 3, preset="door")
    assert svc.is_passable(3, 3) is False
    # 门开着可走
    svc.paint_cell(3, 3, preset="door", door_open=True)
    assert svc.is_passable(3, 3) is True


def test_is_vision_blocking():
    """视野阻挡：blocks_vision + is_smoke 控制。"""
    m = GameMap(width=5, height=5)
    svc = MapService(m)
    # 平地不挡视野
    assert svc.is_vision_blocking(0, 0) is False
    # 实体墙挡视野
    svc.paint_cell(1, 1, preset="wall")
    assert svc.is_vision_blocking(1, 1) is True
    # 玻璃墙挡视野（blocks_vision=true）
    svc.paint_cell(2, 2, preset="glass_wall")
    assert svc.is_vision_blocking(2, 2) is True
    # 烟雾挡视野（ADR-4：由 is_smoke 派生）
    svc.set_smoke(0, 1, ttl=5)
    assert svc.is_vision_blocking(0, 1) is True
    # 门关着挡视野
    svc.paint_cell(3, 3, preset="door")
    assert svc.is_vision_blocking(3, 3) is True
    # 门开着不挡视野
    svc.paint_cell(3, 3, door_open=True)
    assert svc.is_vision_blocking(3, 3) is False


def test_is_sound_blocking():
    """声音/光照阻挡：实体墙（两布尔都 true）控制。
    声音穿玻璃、穿烟雾、穿水。"""
    m = GameMap(width=5, height=5)
    svc = MapService(m)
    # 平地不挡声音
    assert svc.is_sound_blocking(0, 0) is False
    # 实体墙挡声音
    svc.paint_cell(1, 1, preset="wall")
    assert svc.is_sound_blocking(1, 1) is True
    # 玻璃墙不挡声音（blocks_movement=false）
    svc.paint_cell(2, 2, preset="glass_wall")
    assert svc.is_sound_blocking(2, 2) is False
    # 烟雾不挡声音
    svc.set_smoke(0, 1, ttl=5)
    assert svc.is_sound_blocking(0, 1) is False
    # 移动墙（blocks_movement=true, blocks_vision=false）不挡声音
    svc.paint_cell(4, 4, blocks_movement=True, blocks_vision=False)
    assert svc.is_sound_blocking(4, 4) is False


# ─── 快照迁移测试（红线 #2） ───

def test_snapshot_migration_wall():
    """旧快照只有 type:'wall'，迁移后必须有 blocks_movement+vision=True。"""
    old_json = json.dumps({
        "width": 3, "height": 3,
        "terrain": [[{"x": 0, "y": 0, "type": "wall"},
                      {"x": 1, "y": 0, "type": "flat"},
                      {"x": 2, "y": 0, "type": "grass"}]],
        "safe_zone": {"center": {"x": 1, "y": 1}, "radius": 1}
    })
    m = GameMap.model_validate_json(old_json)
    wall_cell = m.terrain[0][0]
    assert wall_cell.blocks_movement is True
    assert wall_cell.blocks_vision is True
    assert wall_cell.wall_render == "solid"
    assert wall_cell.terrain_type == "stone"
    # type 字段被清除
    assert wall_cell.type is None

    # flat 和 grass 正常
    assert m.terrain[0][1].terrain_type == "flat"
    assert m.terrain[0][2].terrain_type == "grass"


def test_snapshot_migration_water():
    """旧水格迁移后不挡移动（向后兼容）。"""
    old_json = json.dumps({
        "width": 2, "height": 1,
        "terrain": [[{"x": 0, "y": 0, "type": "water"},
                      {"x": 1, "y": 0, "type": "flat"}]],
        "safe_zone": {"center": {"x": 0, "y": 0}, "radius": 1}
    })
    m = GameMap.model_validate_json(old_json)
    water_cell = m.terrain[0][0]
    assert water_cell.terrain_type == "water"
    assert water_cell.blocks_movement is False  # 旧水不挡移动


def test_is_wall_compat_shim():
    """旧 is_wall 保留为兼容垫片（= is_sound_blocking 语义）。"""
    m = GameMap(width=3, height=3)
    svc = MapService(m)
    svc.paint_cell(1, 1, preset="wall")
    # is_wall 等价于 is_sound_blocking
    assert svc.is_wall(1, 1) is True
    assert svc.is_wall(0, 0) is False


# ─── preset 画笔测试 ───

def test_paint_cell_preset():
    """preset 模式正确展开三维字段。"""
    m = GameMap(width=5, height=5)
    svc = MapService(m)
    svc.paint_cell(0, 0, preset="door")
    cell = m.terrain[0][0]
    assert cell.blocks_movement is True
    assert cell.blocks_vision is True
    assert cell.wall_render == "door"
    assert cell.terrain_type == "wood"


def test_paint_cell_direct_fields():
    """直接字段模式覆盖 preset。"""
    m = GameMap(width=5, height=5)
    svc = MapService(m)
    svc.paint_cell(0, 0, preset="wall", door_open=True)
    assert m.terrain[0][0].door_open is True
    assert m.terrain[0][0].blocks_movement is True  # preset 给的
