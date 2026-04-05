from PySide6 import QtWidgets
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.spin_box import MSpinBox

class ExportPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        batch_label = MLabel(self.tr("Automatic Mode")).h4()
        batch_note = MLabel(
            self.tr(
                "Selected exports are saved to comic_translate_<timestamp> in the same directory as the input file/archive."
            )
        ).secondary()
        batch_note.setWordWrap(True)
        self.raw_text_checkbox = MCheckBox(self.tr("Export Raw Text"))
        self.translated_text_checkbox = MCheckBox(self.tr("Export Translated text"))
        self.inpainted_image_checkbox = MCheckBox(self.tr("Export Inpainted Image"))

        batching_label = MLabel(self.tr("Batch Processing")).h4()
        batching_note = MLabel(
            self.tr(
                "Control how many pages are kept in a processing chunk and how many OCR crops are"
                " sent to recognition at once."
            )
        ).secondary()
        batching_note.setWordWrap(True)

        batch_size_layout = QtWidgets.QHBoxLayout()
        batch_size_label = MLabel(self.tr("Page Batch Size:"))
        self.batch_size_spinbox = MSpinBox().small()
        self.batch_size_spinbox.setMinimum(1)
        self.batch_size_spinbox.setMaximum(128)
        self.batch_size_spinbox.setValue(32)
        self.batch_size_spinbox.setFixedWidth(70)
        batch_size_layout.addWidget(batch_size_label)
        batch_size_layout.addWidget(self.batch_size_spinbox)
        batch_size_layout.addStretch(1)

        ocr_batch_size_layout = QtWidgets.QHBoxLayout()
        ocr_batch_size_label = MLabel(self.tr("OCR Batch Size:"))
        self.ocr_batch_size_spinbox = MSpinBox().small()
        self.ocr_batch_size_spinbox.setMinimum(1)
        self.ocr_batch_size_spinbox.setMaximum(256)
        self.ocr_batch_size_spinbox.setValue(8)
        self.ocr_batch_size_spinbox.setFixedWidth(70)
        ocr_batch_size_layout.addWidget(ocr_batch_size_label)
        ocr_batch_size_layout.addWidget(self.ocr_batch_size_spinbox)
        ocr_batch_size_layout.addStretch(1)

        layout.addWidget(batch_label)
        layout.addWidget(batch_note)
        layout.addSpacing(8)
        layout.addWidget(batching_label)
        layout.addWidget(batching_note)
        layout.addLayout(batch_size_layout)
        layout.addLayout(ocr_batch_size_layout)
        layout.addSpacing(8)
        layout.addWidget(self.raw_text_checkbox)
        layout.addWidget(self.translated_text_checkbox)
        layout.addWidget(self.inpainted_image_checkbox)

        layout.addStretch(1)
