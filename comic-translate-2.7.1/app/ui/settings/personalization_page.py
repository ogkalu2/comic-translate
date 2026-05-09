from PySide6 import QtWidgets
from .utils import create_title_and_combo, set_combo_box_width

class PersonalizationPage(QtWidgets.QWidget):
    def __init__(self, languages: list[str], themes: list[str], parent=None):
        super().__init__(parent)
        self.languages = languages
        self.themes = themes

        layout = QtWidgets.QVBoxLayout(self)

        language_widget, self.lang_combo = create_title_and_combo(self.tr("Language"), self.languages)
        set_combo_box_width(self.lang_combo, self.languages)
        theme_widget, self.theme_combo = create_title_and_combo(self.tr("Theme"), self.themes)
        set_combo_box_width(self.theme_combo, self.themes)

        layout.addWidget(language_widget)
        layout.addWidget(theme_widget)
        layout.addStretch()