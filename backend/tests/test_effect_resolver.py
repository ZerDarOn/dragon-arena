"""通用 effect resolver 测试：验证数据驱动的状态应用/移除/tick。

核心验证：
- apply_state：根据 mode（add/override/multiply）修改属性并记录原值
- remove_state：根据 original_value 恢复属性
- tick_states：通用处理周期伤害（dot_damage）+ TTL 衰减 + 过期恢复
- 多状态叠加正确
"""
import pytest
from app.schemas.room import Room, Token, StateTag
from app.config import RoomConfig
from app.services.effect_resolver import EffectResolver


@pytest.fixture
def token():
    return Token(id="t1", character_name="test", hp=100, max_hp=100, armor=5, ap=2)


@pytest.fixture
def resolver():
    # EffectResolver 不依赖 Room，只操作 Token
    return EffectResolver()


def test_apply_add_state_modifies_field_and_stores_original(token, resolver):
    """add 模式：护甲-2，记录原值。"""
    s = StateTag(
        id="s1", name="撕裂", description="护甲-2",
        ttl=3, mode="add", target_field="armor", value=-2,
    )
    resolver.apply_state(token, s)
    assert token.armor == 3  # 5 - 2
    assert s.original_value == 5  # 记录原值


def test_remove_add_state_restores_original(token, resolver):
    """移除 add 状态：恢复原值。"""
    s = StateTag(
        id="s1", name="撕裂", description="护甲-2",
        ttl=3, mode="add", target_field="armor", value=-2,
    )
    resolver.apply_state(token, s)
    assert token.armor == 3
    resolver.remove_state(token, s)
    assert token.armor == 5  # 恢复原值


def test_multiple_add_states_stack(token, resolver):
    """多个 add 状态叠加正确（撕裂-2 + 护甲降低-3 = -5）。"""
    s1 = StateTag(id="s1", name="撕裂", description="护甲-2",
                  ttl=3, mode="add", target_field="armor", value=-2)
    s2 = StateTag(id="s2", name="护甲降低", description="护甲-3",
                  ttl=3, mode="add", target_field="armor", value=-3)
    resolver.apply_state(token, s1)
    resolver.apply_state(token, s2)
    assert token.armor == 0  # 5 - 2 - 3
    # 移除一个，另一个仍生效
    resolver.remove_state(token, s1)
    assert token.armor == 2  # 恢复 s1 的 -2，但 s2 的 -3 仍生效：5 - 3 = 2


def test_override_state_sets_value(token, resolver):
    """override 模式：强制设值。"""
    s = StateTag(
        id="s1", name="强制护甲", description="护甲=10",
        ttl=2, mode="override", target_field="armor", value=10,
    )
    resolver.apply_state(token, s)
    assert token.armor == 10
    resolver.remove_state(token, s)
    assert token.armor == 5  # 恢复原值


def test_tick_dot_damage(token, resolver):
    """tick 时 dot_damage 扣 HP。"""
    s = StateTag(
        id="s1", name="点燃", description="每回合2伤害",
        ttl=3, dot_damage=2,
    )
    token.states.append(s)
    resolver.tick_states(token)
    assert token.hp == 98  # 100 - 2
    assert s.ttl == 2  # 衰减


def test_tick_expiry_restores_attribute(token, resolver):
    """状态过期时恢复属性。"""
    s = StateTag(
        id="s1", name="撕裂", description="护甲-2",
        ttl=1, mode="add", target_field="armor", value=-2,
    )
    resolver.apply_state(token, s)
    assert token.armor == 3
    resolver.tick_states(token)
    # ttl 从 1 减到 0，过期移除，恢复属性
    assert len(token.states) == 0
    assert token.armor == 5


def test_tick_multiple_dot_sources(token, resolver):
    """多个周期伤害同时 tick（点燃2 + 中毒3 = 5）。"""
    token.states.append(StateTag(
        id="s1", name="点燃", description="", ttl=2, dot_damage=2,
    ))
    token.states.append(StateTag(
        id="s2", name="中毒", description="", ttl=2, dot_damage=3,
    ))
    resolver.tick_states(token)
    assert token.hp == 95  # 100 - 2 - 3


def test_tick_lethal_marks_dead(token, resolver):
    """周期伤害致死时标记死亡。"""
    token.hp = 3
    token.states.append(StateTag(
        id="s1", name="点燃", description="", ttl=2, dot_damage=5,
    ))
    resolver.tick_states(token)
    assert token.hp == 0
    assert token.is_dead is True


def test_pure_marker_state_no_attribute_change(token, resolver):
    """纯标记状态（mode=None）不改属性，只占状态位。"""
    s = StateTag(id="s1", name="隐身", description="隐身", ttl=2)
    resolver.apply_state(token, s)
    assert token.armor == 5  # 不变
    assert token.is_hidden  # 特殊处理：隐身设 is_hidden


def test_silence_sets_ap_zero(token, resolver):
    """沉默/定身：AP 置 0。"""
    s = StateTag(id="s1", name="沉默", description="AP=0", ttl=2)
    resolver.apply_state(token, s)
    assert token.ap == 0


def test_pin_sets_ap_zero(token, resolver):
    """定身：AP 置 0。"""
    s = StateTag(id="s1", name="定身", description="AP=0", ttl=2)
    resolver.apply_state(token, s)
    assert token.ap == 0
