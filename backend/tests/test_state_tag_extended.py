"""StateTag 扩展测试：验证 FVTT 风格的数据驱动状态模型。

Phase 3（状态三合一）：StateTag 从纯描述升级为自描述效果对象。
"""
import pytest
from app.schemas.room import StateTag, Token


def test_state_tag_new_fields():
    """StateTag 支持 mode/target_field/value/dot_damage/source。"""
    s = StateTag(
        id="s1", name="撕裂", description="护甲-2",
        ttl=3, intensity=2,
        mode="add", target_field="armor", value=-2,
    )
    assert s.mode == "add"
    assert s.target_field == "armor"
    assert s.value == -2


def test_state_tag_dot_damage():
    """周期伤害状态：dot_damage 每回合扣 HP。"""
    s = StateTag(
        id="s2", name="点燃", description="每回合2伤害",
        ttl=3, intensity=2,
        dot_damage=2,
    )
    assert s.dot_damage == 2


def test_state_tag_backward_compatible():
    """旧数据（无新字段）能正常创建，新字段有默认值。"""
    s = StateTag(id="s3", name="隐身", description="隐身", ttl=2)
    assert s.mode is None  # 默认 None = 纯标记状态（无属性修改）
    assert s.target_field is None
    assert s.value is None
    assert s.dot_damage == 0  # 默认无周期伤害


def test_state_tag_stored_original_value():
    """状态记录应用前的原值，过期时能恢复。"""
    s = StateTag(
        id="s4", name="护甲降低", description="护甲-3",
        ttl=2, intensity=3,
        mode="add", target_field="armor", value=-3,
    )
    # 模拟应用后记录原值
    s.original_value = 5
    assert s.original_value == 5


def test_token_serialization_with_extended_states():
    """Token 带扩展 StateTag 能正确序列化往返。"""
    t = Token(id="t1", character_name="test", hp=100, max_hp=100)
    t.states.append(StateTag(
        id="s1", name="撕裂", description="护甲-2",
        ttl=3, mode="add", target_field="armor", value=-2, original_value=5,
    ))
    t.states.append(StateTag(
        id="s2", name="点燃", description="每回合2伤害",
        ttl=2, dot_damage=2,
    ))
    # 序列化往返
    data = t.model_dump_json()
    restored = Token.model_validate_json(data)
    assert len(restored.states) == 2
    assert restored.states[0].mode == "add"
    assert restored.states[0].target_field == "armor"
    assert restored.states[0].original_value == 5
    assert restored.states[1].dot_damage == 2
