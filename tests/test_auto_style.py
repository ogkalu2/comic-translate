import numpy as np
from PIL import Image, ImageDraw, ImageFont

from schemas.style_state import StyleState
from modules.rendering.decisions import decide_style, AutoStyleConfig
from modules.rendering.color_analysis import ColorAnalysis, analyse_group_colors
from modules.layout.grouping import TextGroup
from modules.utils.textblock import TextBlock


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


def _rect_group(x1, y1, x2, y2):
    block = TextBlock(text_bbox=np.array([x1, y1, x2, y2]))
    polygon = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)
    return TextGroup(blocks=[block], polygon=polygon, bbox=(x1, y1, x2, y2))


def _synthetic_text_image(text_color, background_color):
    img = Image.new("RGB", (160, 120), background_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    position = (40, 40)
    bbox = draw.textbbox(position, "Hi", font=font)
    draw.text(position, "Hi", fill=text_color, font=font)
    return np.array(img, dtype=np.uint8), bbox


def test_colour_analysis_prefers_minority_dark_text():
    image, bbox = _synthetic_text_image((30, 160, 40), (255, 255, 255))
    group = _rect_group(*bbox)

    analysis = analyse_group_colors(image, group)

    assert analysis is not None
    fill = np.array(analysis.fill_rgb)
    expected = np.array((30, 160, 40))
    background = np.array(analysis.background_rgb)
    assert np.linalg.norm(fill - expected) < 40
    assert np.linalg.norm(fill - background) > 30
    assert analysis.background_rgb != analysis.fill_rgb


def test_colour_analysis_handles_light_text_on_dark_background():
    image, bbox = _synthetic_text_image((240, 210, 80), (10, 10, 10))
    group = _rect_group(*bbox)

    analysis = analyse_group_colors(image, group)

    assert analysis is not None
    fill = np.array(analysis.fill_rgb)
    expected = np.array((240, 210, 80))
    background = np.array(analysis.background_rgb)
    assert np.linalg.norm(fill - expected) < 80
    assert np.linalg.norm(fill - expected) < np.linalg.norm(background - expected)
    assert np.linalg.norm(fill - background) > 60
