import os
from PySide6 import QtWidgets
from PySide6.QtGui import QFontDatabase, QFontMetrics
from PySide6.QtCore import QSettings
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.spin_box import MSpinBox
from ..dayu_widgets.browser import MClickBrowserFileToolButton
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.combo_box import MComboBox

class TextRenderingPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Font section
        font_layout = QtWidgets.QVBoxLayout()
        min_font_layout = QtWidgets.QHBoxLayout()
        max_font_layout = QtWidgets.QHBoxLayout()
        min_font_label = MLabel(self.tr("Minimum Font Size:"))
        max_font_label = MLabel(self.tr("Maximum Font Size:"))

        self.min_font_spinbox = MSpinBox().small()
        self.min_font_spinbox.setFixedWidth(60)
        self.min_font_spinbox.setMaximum(100)
        self.min_font_spinbox.setValue(9)

        self.max_font_spinbox = MSpinBox().small()
        self.max_font_spinbox.setFixedWidth(60)
        self.max_font_spinbox.setMaximum(100)
        self.max_font_spinbox.setValue(40)

        min_font_layout.addWidget(min_font_label)
        min_font_layout.addWidget(self.min_font_spinbox)
        min_font_layout.addStretch()

        max_font_layout.addWidget(max_font_label)
        max_font_layout.addWidget(self.max_font_spinbox)
        max_font_layout.addStretch()

        font_label = MLabel(self.tr("Font:")).h4()

        # Added Font Combo Box from broken project
        self.font_combo_box = MComboBox().small()
        font_folder_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'fonts')
        if not os.path.exists(font_folder_path):
            os.makedirs(font_folder_path, exist_ok=True)
        
        font_files = [f for f in os.listdir(font_folder_path) if f.endswith(('.ttf', '.ttc', '.otf'))]
        font_families = set()
        for font_file in font_files:
            font_path = os.path.join(font_folder_path, font_file)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                font_families.update(families)
        # Add common system fonts
        font_families.update(QFontDatabase().families())
        self.font_combo_box.addItems(sorted(font_families))
        self.font_combo_box.setFixedWidth(180)
        self.font_combo_box.setToolTip(self.tr("Choisissez une police parmi celles disponibles dans le dossier fonts/ ou sur le système."))
        self.font_combo_box.currentTextChanged.connect(self.on_font_selected)

        font_browser_layout = QtWidgets.QHBoxLayout()
        import_font_label = MLabel(self.tr("Import Font:"))
        self.font_browser = MClickBrowserFileToolButton(multiple=True)
        self.font_browser.set_dayu_filters([".ttf", ".ttc", ".otf", ".woff", ".woff2"])
        self.font_browser.setToolTip(self.tr("Import the Font to use for Rendering Text on Images"))

        font_browser_layout.addWidget(import_font_label)
        font_browser_layout.addWidget(self.font_browser)
        font_browser_layout.addStretch()

        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_combo_box)
        font_layout.addLayout(font_browser_layout)
        font_layout.addLayout(min_font_layout)
        font_layout.addLayout(max_font_layout)

        # Uppercase and Margin
        self.uppercase_checkbox = MCheckBox(self.tr("Render Text in UpperCase"))
        
        margin_layout = QtWidgets.QHBoxLayout()
        margin_label = MLabel(self.tr("Marge intérieure (px):"))
        self.margin_spinbox = MSpinBox().small()
        self.margin_spinbox.setFixedWidth(60)
        self.margin_spinbox.setMaximum(50)
        self.margin_spinbox.setValue(10)
        margin_layout.addWidget(margin_label)
        margin_layout.addWidget(self.margin_spinbox)
        margin_layout.addStretch()

        layout.addWidget(self.uppercase_checkbox)
        layout.addLayout(margin_layout)
        layout.addSpacing(10)
        layout.addLayout(font_layout)
        layout.addSpacing(10)
        layout.addStretch(1)

    def on_font_selected(self, font_family):
        # Save font to settings
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup('text_rendering')
        settings.setValue('font_family', font_family)
        settings.endGroup()

