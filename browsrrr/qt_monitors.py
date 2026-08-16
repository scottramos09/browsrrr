from PySide6.QtGui import QGuiApplication

from .domain import Rect, Screen
from .monitor_spanner import combined_rect


def _to_screen(index: int, qscreen) -> Screen:
    geometry = qscreen.geometry()
    return Screen(
        name=f"Screen {index}",
        rect=Rect(geometry.x(), geometry.y(), geometry.width(), geometry.height()),
    )


def domain_screens() -> list[Screen]:
    return [
        _to_screen(index, screen)
        for index, screen in enumerate(QGuiApplication.screens(), start=1)
    ]


def virtual_bounds() -> Rect:
    """Logical bounds of the connected monitor layout."""
    screens = domain_screens()
    if not screens:
        return Rect(0, 0, 1280, 800)
    return combined_rect(screens)