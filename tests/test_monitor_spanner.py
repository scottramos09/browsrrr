from browsrrr.domain import Rect, Screen
from browsrrr.monitor_spanner import clamped_rect, combined_rect


def test_combines_adjacent_screens():
    screens = [
        Screen("left", Rect(0, 0, 100, 100)),
        Screen("right", Rect(100, 0, 100, 100)),
    ]

    assert combined_rect(screens) == Rect(0, 0, 200, 100)


def test_combines_disconnected_screens():
    screens = [
        Screen("left", Rect(0, 0, 100, 100)),
        Screen("far", Rect(300, 0, 100, 100)),
    ]

    assert combined_rect(screens) == Rect(0, 0, 400, 100)


def test_clamp_shrinks_oversized_rect():
    assert clamped_rect(Rect(50, 50, 200, 100), Rect(0, 0, 100, 100)) == Rect(0, 0, 100, 100)


def test_clamp_moves_rect_inside_bounds():
    assert clamped_rect(Rect(-20, 10, 50, 50), Rect(0, 0, 100, 100)) == Rect(0, 10, 50, 50)