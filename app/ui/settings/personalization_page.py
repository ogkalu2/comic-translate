from typing import List
from PySide6 import QtWidgets
from PySide6.QtGui import QFontMetrics
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.combo_box import MComboBox

class PersonalizationPage(QtWidgets.QWidget):
    def __init__(self, languages: List[str], themes: List[str], parent=None):
        super().__init__(parent)
        self.languages = languages
        self.themes = themes

        layout = QtWidgets.QVBoxLayout(self)

        language_widget, self.lang_combo = self._create_title_and_combo(self.tr("Language"), self.languages)
        self._set_combo_box_width(self.lang_combo, self.languages)
        theme_widget, self.theme_combo = self._create_title_and_combo(self.tr("Theme"), self.themes)
        self._set_combo_box_width(self.theme_combo, self.themes)

        layout.addWidget(language_widget)
        layout.addWidget(theme_widget)
        layout.addStretch()

    def _create_title_and_combo(self, title: str, options: List[str]):
        combo_widget = QtWidgets.QWidget()
        combo_layout = QtWidgets.QVBoxLayout(combo_widget)
        label = MLabel(title).h4()
        combo = MComboBox().small()
        combo.addItems(options)
        combo_layout.addWidget(label)
        combo_layout.addWidget(combo)
        return combo_widget, combo

    def _set_combo_box_width(self, combo_box: MComboBox, items: List[str], padding: int = 40):
        metrics = QFontMetrics(combo_box.font())
        max_width = max(metrics.horizontalAdvance(i) for i in items) if items else 100
        combo_box.setFixedWidth(max_width + padding)
