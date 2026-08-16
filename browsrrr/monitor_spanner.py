from functools import reduce

from .domain import Rect, Screen


def combined_rect(screens: list[Screen]) -> Rect:
    if not screens:
        raise ValueError("At least one screen is required.")
    return reduce(Rect.united, [screen.rect for screen in screens])


def clamped_rect(rect: Rect, bounds: Rect) -> Rect:
    width = min(rect.width, bounds.width)
    height = min(rect.height, bounds.height)
    x = min(max(rect.x, bounds.x), bounds.x + bounds.width - width)
    y = min(max(rect.y, bounds.y), bounds.y + bounds.height - height)
    return Rect(x, y, width, height)