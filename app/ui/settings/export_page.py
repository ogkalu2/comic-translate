from PySide6 import QtWidgets
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.combo_box import MComboBox
from .utils import set_combo_box_width

class ExportPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        batch_label = MLabel(self.tr("Automatic Mode")).h4()

        self.auto_save_checkbox = MCheckBox(self.tr("Auto-Save Batch Translations"))
        self.auto_save_note = MLabel(
            self.tr("Saves to a new comic_translate_<timestamp> folder in the same directory as the input file/archive.")
        ).secondary()
        self.raw_text_checkbox = MCheckBox(self.tr("Export Raw Text"))
        self.translated_text_checkbox = MCheckBox(self.tr("Export Translated text"))
        self.inpainted_image_checkbox = MCheckBox(self.tr("Export Inpainted Image"))

        layout.addWidget(batch_label)
        layout.addWidget(self.auto_save_note)
        layout.addWidget(self.auto_save_checkbox)
        layout.addWidget(self.raw_text_checkbox)
        layout.addWidget(self.translated_text_checkbox)
        layout.addWidget(self.inpainted_image_checkbox)

        # File format conversion
        layout.addSpacing(20)
        self.file_conversion_container = QtWidgets.QWidget(self)
        file_conversion_layout = QtWidgets.QVBoxLayout(self.file_conversion_container)
        file_conversion_layout.setContentsMargins(0, 0, 0, 0)

        file_conversion_label = MLabel(self.tr("File Format Conversion")).h4()
        file_conversion_note = MLabel(
            self.tr("Applies only when auto-save is enabled and the input is an archive (PDF/CBZ/CBR/EPUB/etc).")
        ).secondary()

        file_conversion_layout.addWidget(file_conversion_label)
        file_conversion_layout.addWidget(file_conversion_note)

        save_layout = QtWidgets.QHBoxLayout()
        save_label = MLabel(self.tr("Save archives as:"))
        self.archive_save_as_combo = MComboBox().small()

        available_file_types = ['pdf', 'cbz', 'cb7', 'zip']
        self.archive_save_as_combo.addItems(available_file_types)
        set_combo_box_width(self.archive_save_as_combo, available_file_types)
        self.archive_save_as_combo.setCurrentText('zip')

        save_layout.addWidget(save_label)
        save_layout.addWidget(self.archive_save_as_combo)
        save_layout.addStretch(1)
        file_conversion_layout.addLayout(save_layout)

        layout.addWidget(self.file_conversion_container)
        layout.addStretch(1)

        self.auto_save_checkbox.toggled.connect(self._update_file_format_conversion_state)
        self._update_file_format_conversion_state(self.auto_save_checkbox.isChecked())

    def _update_file_format_conversion_state(self, auto_save_enabled: bool):
        # Conversion options only apply when we actually write translated archives to disk.
        self.file_conversion_container.setEnabled(bool(auto_save_enabled))
