from schemas.style_state import StyleState
from modules.rendering.decisions import decide_style, AutoStyleConfig
from modules.rendering.color_analysis import ColorAnalysis


def _analysis(**kwargs):
    defaults = dict(
        fill_rgb=(50, 50, 50),
        stroke_rgb=None,
        background_rgb=(240, 240, 240),
        fill_luminance=None,
        stroke_luminance=None,
        background_luminance=None,
        plain_white=False,
        plain_black=False,
        core_pixel_count=200,
        stroke_pixel_count=120,
        background_pixel_count=400,
    )
    defaults.update(kwargs)
    return ColorAnalysis(**defaults)


def test_plain_white_prefers_black_text_without_stroke():
    base_state = StyleState(font_family="Test", font_size=24, auto_color=True)
    analysis = _analysis(plain_white=True, background_rgb=(250, 250, 250))
    result = decide_style(analysis, base_state)
    assert result.fill == (0, 0, 0)
    assert result.stroke is None


def test_plain_black_prefers_white_text():
    base_state = StyleState(font_family="Test", font_size=24, auto_color=True)
    analysis = _analysis(plain_black=True, background_rgb=(5, 5, 5))
    result = decide_style(analysis, base_state)
    assert result.fill == (255, 255, 255)
    assert result.stroke in {None, (0, 0, 0)}


def test_contrast_enforced_when_background_close():
    base_state = StyleState(font_family="Test", font_size=24, auto_color=True)
    analysis = _analysis(fill_rgb=(180, 180, 180), background_rgb=(200, 200, 200))
    result = decide_style(analysis, base_state, AutoStyleConfig(target_contrast=4.5))
    assert result.fill in ((0, 0, 0), (255, 255, 255))
    assert result.stroke is not None
    assert result.stroke_size >= 1
