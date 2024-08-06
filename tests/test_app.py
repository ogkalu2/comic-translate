from app.ui.main_window import ComicTranslateUI

def test_comic_translate_ui_basic(qtbot):
    widget = ComicTranslateUI()
    qtbot.addWidget(widget)

    widget.show()

    assert widget.isVisible()
    assert widget.windowTitle() == "Comic Translate"
