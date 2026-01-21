from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QDoubleValidator
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.text_edit import MTextEdit
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.slider import MSlider
from ..dayu_widgets.line_edit import MLineEdit
from ..dayu_widgets.collapse import MCollapse

class LlmsPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        v = QtWidgets.QVBoxLayout(self)
        main_layout = QtWidgets.QHBoxLayout()

        self.image_checkbox = MCheckBox(self.tr("Provide Image as input to multimodal LLMs"))
        self.image_checkbox.setChecked(False)

        # Left
        left_layout = QtWidgets.QVBoxLayout()
        prompt_label = MLabel(self.tr("Extra Context:"))
        self.extra_context = MTextEdit()
        self.extra_context.setMinimumHeight(200)
        left_layout.addWidget(prompt_label)
        left_layout.addWidget(self.extra_context)
        left_layout.addWidget(self.image_checkbox)
        left_layout.addStretch(1)

        # Right
        right_layout = QtWidgets.QVBoxLayout()

        # Temperature
        temp_layout = QtWidgets.QVBoxLayout()
        temp_header = MLabel(self.tr("Temperature")).h4()
        temp_controls = QtWidgets.QHBoxLayout()
        self.temp_slider = MSlider(QtCore.Qt.Horizontal)
        self.temp_slider.setRange(0, 200)
        self.temp_slider.setValue(100)
        self.temp_slider.disable_show_text()
        self.temp_edit = MLineEdit().small()
        self.temp_edit.setFixedWidth(50)
        self.temp_edit.setValidator(QDoubleValidator(0.0, 2.0, 2))
        self.temp_edit.setText("1")
        temp_controls.addWidget(self.temp_slider)
        temp_controls.addWidget(self.temp_edit)
        temp_layout.addWidget(temp_header)
        temp_layout.addLayout(temp_controls)

        # Advanced settings

        right_layout.addLayout(temp_layout)
        right_layout.addSpacing(10)
        right_layout.addStretch(1)

        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 1)

        v.addLayout(main_layout)
        v.addStretch(1)

        # Signals
        self.temp_slider.valueChanged.connect(self._update_temp_edit)
        self.temp_edit.textChanged.connect(self._update_temp_slider)

    def _update_temp_edit(self):
        self.temp_edit.setText(str(self.temp_slider.value() / 100.0))

    def _update_temp_slider(self):
        try:
            if self.temp_edit.text():
                self.temp_slider.setValue(int(float(self.temp_edit.text()) * 100))
        except ValueError:
            pass

