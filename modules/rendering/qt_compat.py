from PySide6.QtCore import Qt


def coerce_alignment_flag(value, default=Qt.AlignmentFlag.AlignCenter) -> Qt.AlignmentFlag:
    if isinstance(value, Qt.AlignmentFlag):
        return value
    try:
        return Qt.AlignmentFlag(int(value))
    except (TypeError, ValueError):
        return default


def coerce_layout_direction(value, default=Qt.LayoutDirection.LeftToRight) -> Qt.LayoutDirection:
    if isinstance(value, Qt.LayoutDirection):
        return value
    try:
        return Qt.LayoutDirection(int(value))
    except (TypeError, ValueError):
        return default
