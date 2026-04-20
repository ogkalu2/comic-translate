from __future__ import annotations

from PySide6.QtWidgets import QApplication


def _pixels_to_qfont_points(size_px: float) -> float:
    """Convert image pixel sizing to QFont point sizing."""
    dpi = 96.0
    try:
        screen = QApplication.primaryScreen()
        if screen is not None:
            dpi = float(screen.logicalDotsPerInch() or dpi)
    except Exception:
        pass
    return float(size_px) * 72.0 / max(dpi, 1.0)


def resolve_init_font_size(
    blk,
    default_max_font_size: int,
    min_font_size: int,
    target: str = "qt",
) -> int:
    """Pick a per-block initial font size for wrapping."""
    geometric_cap = 0.0
    candidate = 0
    candidate_is_px = False

    render_state = blk.render_state() if blk is not None and hasattr(blk, "render_state") else None

    if render_state is not None:
        candidate = render_state.font_size_px or render_state.max_font_size or 0
        font_size_px = render_state.font_size_px or 0
        max_font_size_px = render_state.max_font_size or 0
        max_chars = render_state.max_chars

        if font_size_px > 0:
            candidate = font_size_px
            candidate_is_px = True
        elif max_font_size_px > 0:
            candidate = max_font_size_px
            candidate_is_px = True
        try:
            geometric_cap = max(1.0, 200.0 / (max_chars + 1)) if max_chars is not None else 0.0
            if geometric_cap > 0:
                candidate = min(candidate, geometric_cap)
                candidate_is_px = True
        except Exception:
            geometric_cap = 0.0

        if candidate <= 0:
            candidate = geometric_cap
            candidate_is_px = geometric_cap > 0

    if candidate <= 0:
        candidate = default_max_font_size
        candidate_is_px = False

    if str(target).lower() != "pil" and candidate_is_px:
        candidate = _pixels_to_qfont_points(candidate)

    return int(round(max(min_font_size, candidate)))
