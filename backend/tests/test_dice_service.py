import pytest
from app.services.dice_service import roll_dice, DiceResult


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
