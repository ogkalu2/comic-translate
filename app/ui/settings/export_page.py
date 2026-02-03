from PySide6 import QtWidgets
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.combo_box import MComboBox
from .utils import set_combo_box_width

class ExportPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.export_widgets: dict[str, MComboBox] = {}

        layout = QtWidgets.QVBoxLayout(self)

        batch_label = MLabel(self.tr("Automatic Mode")).h4()

        self.auto_save_checkbox = MCheckBox(self.tr("Auto-save Batch Translations"))
        self.raw_text_checkbox = MCheckBox(self.tr("Export Raw Text"))
        self.translated_text_checkbox = MCheckBox(self.tr("Export Translated text"))
        self.inpainted_image_checkbox = MCheckBox(self.tr("Export Inpainted Image"))

        layout.addWidget(batch_label)
        layout.addWidget(self.auto_save_checkbox)
        layout.addWidget(self.raw_text_checkbox)
        layout.addWidget(self.translated_text_checkbox)
        layout.addWidget(self.inpainted_image_checkbox)

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
            set_combo_box_width(save_combo, available_file_types)

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