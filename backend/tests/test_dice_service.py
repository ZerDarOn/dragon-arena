import pytest
from app.services.dice_service import roll_dice, DiceResult, roll_expression


def test_d20_in_range():
    r = roll_dice(sides=20)
    assert 1 <= r.value <= 20
    assert isinstance(r.crit_success, bool)
    assert isinstance(r.crit_fail, bool)


def test_d20_crit_success():
    from app.services import dice_service
    orig = dice_service._rand_int
    dice_service._rand_int = lambda a, b: 20
    try:
        r = roll_dice(sides=20, crit_success_threshold=20, crit_fail_threshold=1)
        assert r.value == 20
        assert r.crit_success is True
        assert r.crit_fail is False
    finally:
        dice_service._rand_int = orig


def test_d20_crit_fail():
    from app.services import dice_service
    orig = dice_service._rand_int
    dice_service._rand_int = lambda a, b: 1
    try:
        r = roll_dice(sides=20, crit_success_threshold=20, crit_fail_threshold=1)
        assert r.value == 1
        assert r.crit_fail is True
        assert r.crit_success is False
    finally:
        dice_service._rand_int = orig


def test_modifier_applied():
    from app.services import dice_service
    orig = dice_service._rand_int
    dice_service._rand_int = lambda a, b: 14
    try:
        r = roll_dice(sides=20, modifier=3)
        assert r.value == 14
        assert r.total == 17
    finally:
        dice_service._rand_int = orig


def test_d4_custom():
    from app.services import dice_service
    dice_service._rand_int = lambda a, b: 3
    r = roll_dice(sides=4)
    assert r.value == 3


# ---- roll_expression ----

def test_expr_simple_d20_plus_modifier():
    from app.services import dice_service
    orig = dice_service._rand_int
    dice_service._rand_int = lambda a, b: 14
    try:
        r = roll_expression("1d20+5")
        assert r.value == 14
        assert r.modifier == 5
        assert r.total == 19
        assert len(r.groups) == 1
        assert r.groups[0].rolls[0].value == 14
    finally:
        dice_service._rand_int = orig


def test_expr_advantage_keep_highest():
    from app.services import dice_service
    orig = dice_service._rand_int
    seq = iter([5, 18])
    dice_service._rand_int = lambda a, b: next(seq)
    try:
        r = roll_expression("2d20kh1+3")
        kept = [x.value for x in r.groups[0].rolls if x.kept]
        dropped = [x.value for x in r.groups[0].rolls if not x.kept]
        assert kept == [18]
        assert dropped == [5]
        assert r.total == 18 + 3
        # 优势/劣势不算"大成功"（只有单纯 1d20 才算）
        assert r.crit_success is False
    finally:
        dice_service._rand_int = orig


def test_expr_disadvantage_keep_lowest():
    from app.services import dice_service
    orig = dice_service._rand_int
    seq = iter([5, 18])
    dice_service._rand_int = lambda a, b: next(seq)
    try:
        r = roll_expression("2d20kl1")
        kept = [x.value for x in r.groups[0].rolls if x.kept]
        assert kept == [5]
        assert r.total == 5
    finally:
        dice_service._rand_int = orig


def test_expr_ability_score_4d6_keep_highest_3():
    from app.services import dice_service
    orig = dice_service._rand_int
    seq = iter([1, 4, 5, 6])
    dice_service._rand_int = lambda a, b: next(seq)
    try:
        r = roll_expression("4d6kh3")
        kept = sorted(x.value for x in r.groups[0].rolls if x.kept)
        assert kept == [4, 5, 6]
        assert r.total == 15
    finally:
        dice_service._rand_int = orig


def test_expr_multiple_groups():
    from app.services import dice_service
    orig = dice_service._rand_int
    seq = iter([3, 2])  # 1d6 -> 3, 1d4 -> 2
    dice_service._rand_int = lambda a, b: next(seq)
    try:
        r = roll_expression("1d6+1d4+2")
        assert r.total == 3 + 2 + 2
        assert len(r.groups) == 2
    finally:
        dice_service._rand_int = orig


def test_expr_crit_only_for_lone_d20():
    from app.services import dice_service
    orig = dice_service._rand_int
    dice_service._rand_int = lambda a, b: 20
    try:
        r = roll_expression("1d20")
        assert r.crit_success is True
        r2 = roll_expression("1d20+1d4")
        assert r2.crit_success is False
    finally:
        dice_service._rand_int = orig


def test_expr_invalid_raises():
    with pytest.raises(ValueError):
        roll_expression("")
    with pytest.raises(ValueError):
        roll_expression("2d20kh5")  # keep more than rolled
    with pytest.raises(ValueError):
        roll_expression("not a dice expr")
    with pytest.raises(ValueError):
        roll_expression("9999d6")  # too many dice
    with pytest.raises(ValueError):
        roll_expression("1d2000")  # too many sides


# ---- forced_values: 客户端本地 3D 物理骰子结果作为权威结果 ----

def test_expr_forced_values_used_instead_of_random():
    from app.services import dice_service
    # 故意让 _rand_int 返回明显不同的值，证明真正用的是 forced_values 而不是随机数
    orig = dice_service._rand_int
    dice_service._rand_int = lambda a, b: 999
    try:
        r = roll_expression("1d20+5", forced_values=[12])
        assert r.value == 12
        assert r.total == 17
        assert r.groups[0].rolls[0].value == 12
    finally:
        dice_service._rand_int = orig


def test_expr_forced_values_advantage():
    r = roll_expression("2d20kh1+3", forced_values=[5, 18])
    kept = [x.value for x in r.groups[0].rolls if x.kept]
    assert kept == [18]
    assert r.total == 21


def test_expr_forced_values_count_mismatch_raises():
    with pytest.raises(ValueError):
        roll_expression("2d20", forced_values=[10])  # 少一个
    with pytest.raises(ValueError):
        roll_expression("1d20", forced_values=[10, 5])  # 多一个


def test_expr_forced_values_out_of_range_raises():
    with pytest.raises(ValueError):
        roll_expression("1d6", forced_values=[7])  # d6 摇不出 7
    with pytest.raises(ValueError):
        roll_expression("1d20", forced_values=[0])
