DRAW_HOLD_MS = 300
WORKSPACE_MARGIN = 24


def stretched_size(
    current_width: int,
    current_height: int,
    sub_x: int,
    sub_y: int,
    sub_width: int,
    sub_height: int,
    margin: int = WORKSPACE_MARGIN,
) -> tuple[int, int]:
    needed_width = max(current_width, sub_x + sub_width + margin)
    needed_height = max(current_height, sub_y + sub_height + margin)
    return needed_width, needed_height