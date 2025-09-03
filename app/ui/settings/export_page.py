from PySide6 import QtWidgets
from PySide6.QtGui import QFontMetrics
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.spin_box import MSpinBox
from ..dayu_widgets.combo_box import MComboBox

class ExportPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.export_widgets: dict[str, MComboBox] = {}

        layout = QtWidgets.QVBoxLayout(self)

        batch_label = MLabel(self.tr("Automatic Mode")).h4()

        self.raw_text_checkbox = MCheckBox(self.tr("Export Raw Text"))
        self.translated_text_checkbox = MCheckBox(self.tr("Export Translated text"))
        self.inpainted_image_checkbox = MCheckBox(self.tr("Export Inpainted Image"))

        layout.addWidget(batch_label)
        layout.addWidget(self.raw_text_checkbox)
        layout.addWidget(self.translated_text_checkbox)
        layout.addWidget(self.inpainted_image_checkbox)

        # JPEG Quality
        layout.addSpacing(20)
        jpeg_quality_label = MLabel(self.tr("JPEG Quality")).h4()
        layout.addWidget(jpeg_quality_label)

        jpeg_quality_layout = QtWidgets.QHBoxLayout()
        self.jpeg_quality_spinbox = MSpinBox()
        self.jpeg_quality_spinbox.setRange(1, 100)
        self.jpeg_quality_spinbox.setValue(95)
        self.jpeg_quality_spinbox.setSuffix("%")
        self.jpeg_quality_spinbox.setFixedWidth(80)

        jpeg_quality_layout.addWidget(MLabel(self.tr("Quality:")))
        jpeg_quality_layout.addWidget(self.jpeg_quality_spinbox)
        jpeg_quality_layout.addStretch(1)
        layout.addLayout(jpeg_quality_layout)

        # File format conversion
        layout.addSpacing(20)
        file_conversion_label = MLabel(self.tr("File Format Conversion")).h4()
        layout.addWidget(file_conversion_label)

        self.from_file_types = ['pdf', 'epub', 'cbr', 'cbz', 'cb7', 'cbt', 'zip', 'rar']
        available_file_types = ['pdf', 'cbz', 'cb7', 'zip']

        for file_type in self.from_file_types:
            save_layout = QtWidgets.QHBoxLayout()
            save_label = MLabel(self.tr("Save {file_type} as:").format(file_type=file_type))
            save_combo = MComboBox().small()
            save_combo.addItems(available_file_types)
            self._set_combo_box_width(save_combo, available_file_types)

            # Defaults
            if file_type in ['cbr', 'cbt']:
                save_combo.setCurrentText('cbz')
            elif file_type == 'rar':
                save_combo.setCurrentText('zip')
            elif file_type == 'epub':
                save_combo.setCurrentText('pdf')
            elif file_type in available_file_types:
                save_combo.setCurrentText(file_type)

            self.export_widgets[f'.{file_type.lower()}_save_as'] = save_combo

            save_layout.addWidget(save_label)
            save_layout.addWidget(save_combo)
            save_layout.addStretch(1)
            layout.addLayout(save_layout)

        layout.addStretch(1)

    def _set_combo_box_width(self, combo_box: MComboBox, items: list[str], padding: int = 40):
        metrics = QFontMetrics(combo_box.font())
        max_width = max(metrics.horizontalAdvance(i) for i in items) if items else 100
        combo_box.setFixedWidth(max_width + padding)