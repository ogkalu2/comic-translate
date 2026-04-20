from PySide6.QtCore import Qt

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
