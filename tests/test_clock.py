from ts.clock import FixtureClock, WallClock, minutes_ms, seconds_ms
import pytest


def test_fixture_clock_is_virtual():
    c = FixtureClock(start_ms=1_000)
    assert c.now_ms() == 1_000
    c.advance_to(5_000)
    assert c.now_ms() == 5_000
    c.advance_by(500)
    assert c.now_ms() == 5_500


def test_clock_cannot_move_backwards():
    c = FixtureClock(start_ms=1_000)
    with pytest.raises(ValueError):
        c.advance_to(999)


def test_ticks_are_deterministic():
    a = list(FixtureClock(0).ticks(end_ms=300, step_ms=100))
    b = list(FixtureClock(0).ticks(end_ms=300, step_ms=100))
    assert a == b == [0, 100, 200, 300]


def test_wall_clock_is_sane():
    assert WallClock().now_ms() > 1_700_000_000_000


def test_helpers():
    assert minutes_ms(2) == 120_000
    assert seconds_ms(1.5) == 1500
