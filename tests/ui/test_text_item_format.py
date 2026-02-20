import pytest
import sys

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not available in test environment")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a

def test_insert_translation_leaves_clean_cursor_format(app):
    from app.ui.canvas.text_item import TextBlockItem
    item = TextBlockItem()
    item.set_plain_text("original text")

    item.insert_translation("<p style='background-color:white'>翻譯文字</p>")

    cursor = item.textCursor()
    char_fmt = cursor.charFormat()
    bg = char_fmt.background().color()
    assert bg.alpha() == 0 or not bg.isValid(), \
        f"Cursor has rogue background: {bg.name()}"
