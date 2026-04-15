from PySide6 import QtWidgets
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.spin_box import MSpinBox
from ..dayu_widgets.divider import MDivider

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

        layout.addWidget(batch_label)
        layout.addWidget(batch_note)
        layout.addWidget(self.raw_text_checkbox)
        layout.addWidget(self.translated_text_checkbox)
        layout.addWidget(self.inpainted_image_checkbox)

        # ── Output Sizing ──────────────────────────────────────────
        layout.addSpacing(10)
        layout.addWidget(MDivider())

        output_sizing_label = MLabel(self.tr("Output Sizing")).h4()
        output_sizing_note = MLabel(
            self.tr(
                "Scale exported images so their width matches the specified value.\n"
                "Height adjusts proportionally to maintain the aspect ratio."
            )
        ).secondary()
        output_sizing_note.setWordWrap(True)

        self.limit_width_checkbox = MCheckBox(self.tr("Limit Output Width"))

        width_input_layout = QtWidgets.QHBoxLayout()
        width_label = MLabel(self.tr("Width:"))
        self.output_width_spinbox = MSpinBox().small()
        self.output_width_spinbox.setFixedWidth(80)
        self.output_width_spinbox.setMinimum(100)
        self.output_width_spinbox.setMaximum(5000)
        self.output_width_spinbox.setValue(960)
        self.output_width_spinbox.setEnabled(False)
        width_px_label = MLabel("px")
        width_input_layout.addWidget(width_label)
        width_input_layout.addWidget(self.output_width_spinbox)
        width_input_layout.addWidget(width_px_label)
        width_input_layout.addStretch()

        # Enable/disable spinbox based on checkbox state
        self.limit_width_checkbox.toggled.connect(self.output_width_spinbox.setEnabled)

        layout.addWidget(output_sizing_label)
        layout.addWidget(output_sizing_note)
        layout.addWidget(self.limit_width_checkbox)
        layout.addLayout(width_input_layout)

        layout.addStretch(1)
