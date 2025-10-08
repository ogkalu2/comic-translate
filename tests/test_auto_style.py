import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt

from schemas.style_state import StyleState
from modules.rendering.decisions import decide_style, AutoStyleConfig
from modules.rendering.color_analysis import (
    ColorAnalysis,
    analyse_block_colors,
    analyse_group_colors,
)
from modules.rendering.settings import preferred_stroke_size as _preferred_stroke_size, TextRenderingSettings
from modules.layout.grouping import TextGroup
import colorsys

from modules.utils.textblock import TextBlock
from modules.utils.wcag import relative_luminance


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
        stroke_inferred=False,
    )
    defaults.update(kwargs)
    return ColorAnalysis(**defaults)


def _render_settings(outline_width: str = "0", outline: bool = False) -> TextRenderingSettings:
    return TextRenderingSettings(
        alignment_id=0,
        font_family="Test",
        min_font_size=16,
        max_font_size=24,
        color="#FFFFFF",
        upper_case=False,
        outline=outline,
        outline_color="#000000",
        outline_width=outline_width,
        bold=False,
        italic=False,
        underline=False,
        line_spacing="1.2",
        direction=Qt.LayoutDirection.LeftToRight,
    )


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


def test_block_colour_analysis_matches_expected_fill():
    text_colour = (120, 40, 200)
    background_colour = (240, 240, 240)
    image, bbox = _synthetic_text_image(text_colour, background_colour)

    block = TextBlock(text_bbox=np.array(bbox))

    analysis = analyse_block_colors(image, block)

    assert analysis is not None
    assert analysis.fill_rgb is not None
    detected = np.array(analysis.fill_rgb)
    expected = np.array(text_colour)
    assert np.linalg.norm(detected - expected) < 60


def test_block_colour_analysis_infers_stroke_when_low_contrast():
    text_colour = (180, 180, 180)
    background_colour = (200, 200, 200)
    image, bbox = _synthetic_text_image(text_colour, background_colour)

    block = TextBlock(text_bbox=np.array(bbox))

    analysis = analyse_block_colors(image, block)

    assert analysis is not None
    assert analysis.stroke_rgb is not None
    assert analysis.stroke_inferred is True
    assert analysis.fill_rgb is not None
    assert np.linalg.norm(np.array(analysis.fill_rgb) - np.array(analysis.stroke_rgb)) > 10


def test_block_colour_analysis_uses_background_hue_for_outline():
    text_colour = (250, 250, 250)
    background_colour = (40, 160, 220)
    image, bbox = _synthetic_text_image(text_colour, background_colour)

    block = TextBlock(text_bbox=np.array(bbox))

    analysis = analyse_block_colors(image, block)

    assert analysis is not None
    assert analysis.stroke_rgb is not None
    assert analysis.stroke_inferred is True
    stroke = np.array(analysis.stroke_rgb, dtype=np.float32)
    background = np.array(background_colour, dtype=np.float32)
    fill = np.array(text_colour, dtype=np.float32)
    assert np.linalg.norm(stroke - fill) > 80
    assert relative_luminance(tuple(int(v) for v in stroke)) < relative_luminance(tuple(int(v) for v in background))
    stroke_hue = colorsys.rgb_to_hsv(*(stroke / 255.0))[0]
    background_hue = colorsys.rgb_to_hsv(*(background / 255.0))[0]
    hue_diff = abs(stroke_hue - background_hue)
    hue_diff = min(hue_diff, 1.0 - hue_diff)
    assert hue_diff < 0.12


def test_colour_analysis_discards_light_halo_and_darkens_outline():
    background_colour = (70, 140, 220)
    img = np.full((180, 240, 3), background_colour, dtype=np.uint8)
    x1, y1, x2, y2 = 70, 60, 170, 120
    img[y1:y2, x1:x2] = (250, 250, 250)
    img[y1 - 2 : y2 + 2, x1 - 2 : x2 + 2] = np.where(
        np.all(img[y1 - 2 : y2 + 2, x1 - 2 : x2 + 2] == background_colour, axis=-1)[..., None],
        (230, 230, 240),
        img[y1 - 2 : y2 + 2, x1 - 2 : x2 + 2],
    )

    block = TextBlock(text_bbox=np.array([x1 - 2, y1 - 2, x2 + 2, y2 + 2]))

    analysis = analyse_block_colors(img, block)

    assert analysis is not None
    assert analysis.fill_rgb is not None
    assert np.linalg.norm(np.array(analysis.fill_rgb) - np.array([250, 250, 250])) < 10
    assert analysis.stroke_rgb is not None
    stroke_lum = relative_luminance(analysis.stroke_rgb)
    background_lum = relative_luminance(background_colour)
    assert stroke_lum < background_lum - 0.01
    stroke_hsv = colorsys.rgb_to_hsv(*((np.array(analysis.stroke_rgb) / 255.0).tolist()))
    background_hsv = colorsys.rgb_to_hsv(*((np.array(background_colour) / 255.0).tolist()))
    hue_gap = abs(stroke_hsv[0] - background_hsv[0])
    hue_gap = min(hue_gap, 1.0 - hue_gap)
    assert hue_gap < 0.12


def test_preferred_stroke_size_honours_existing_style_override():
    settings = _render_settings(outline_width="0")
    style_state = StyleState(stroke_size=3)
    assert _preferred_stroke_size(settings, style_state, stroke_inferred=False) == 3


def test_preferred_stroke_size_uses_configured_width_when_present():
    settings = _render_settings(outline_width="4")
    style_state = StyleState()
    assert _preferred_stroke_size(settings, style_state, stroke_inferred=False) == 4


def test_preferred_stroke_size_promotes_inferred_outline_when_config_zero():
    settings = _render_settings(outline_width="0")
    style_state = StyleState()
    assert _preferred_stroke_size(settings, style_state, stroke_inferred=True) == 2
