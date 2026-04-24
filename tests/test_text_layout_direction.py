from PySide6.QtCore import Qt
from types import SimpleNamespace

from modules.rendering.policy import is_vertical_block, is_vertical_language_code
from modules.utils.language_utils import get_layout_direction, is_rtl_language_code


def test_layout_direction_uses_rtl_for_supported_rtl_languages():
    assert get_layout_direction("Arabic") == Qt.LayoutDirection.RightToLeft
    assert get_layout_direction("Persian") == Qt.LayoutDirection.RightToLeft
    assert get_layout_direction("fa-IR") == Qt.LayoutDirection.RightToLeft


def test_layout_direction_uses_ltr_for_supported_ltr_languages():
    assert get_layout_direction("English") == Qt.LayoutDirection.LeftToRight
    assert get_layout_direction("Japanese") == Qt.LayoutDirection.LeftToRight


def test_is_rtl_language_code_accepts_regional_codes():
    assert is_rtl_language_code("ar-SA") is True
    assert is_rtl_language_code("fa") is True
    assert is_rtl_language_code("en-US") is False


def test_vertical_language_policy_accepts_generic_cjk_codes():
    assert is_vertical_language_code("zh") is True
    assert is_vertical_language_code("zh-CN") is True
    assert is_vertical_language_code("Japanese") is True
    assert is_vertical_language_code("en") is False


def test_vertical_block_policy_uses_target_language_by_default():
    explicit_vertical = SimpleNamespace(direction="vertical", xyxy=(0, 0, 100, 40))
    explicit_horizontal = SimpleNamespace(direction="horizontal", xyxy=(0, 0, 20, 100))
    horizontal_unspecified = SimpleNamespace(direction="", xyxy=(0, 0, 100, 40))

    assert is_vertical_block(explicit_vertical, "zh") is True
    assert is_vertical_block(explicit_horizontal, "ja") is True
    assert is_vertical_block(horizontal_unspecified, "ja") is True
    assert is_vertical_block(explicit_vertical, "en") is False
