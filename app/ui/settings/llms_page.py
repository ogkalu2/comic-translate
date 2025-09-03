from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QIntValidator, QDoubleValidator
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
        advanced_widget = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(advanced_widget)
        advanced_layout.setContentsMargins(0, 5, 0, 5)

        # Top P
        top_p_layout = QtWidgets.QVBoxLayout()
        top_p_header = MLabel(self.tr("Top P")).h4()
        top_p_controls = QtWidgets.QHBoxLayout()
        self.top_p_slider = MSlider(QtCore.Qt.Horizontal)
        self.top_p_slider.setRange(0, 100)
        self.top_p_slider.setValue(95)
        self.top_p_slider.disable_show_text()
        self.top_p_edit = MLineEdit().small()
        self.top_p_edit.setFixedWidth(50)
        self.top_p_edit.setValidator(QDoubleValidator(0.0, 1.0, 2))
        self.top_p_edit.setText("0.95")
        top_p_controls.addWidget(self.top_p_slider)
        top_p_controls.addWidget(self.top_p_edit)
        top_p_layout.addWidget(top_p_header)
        top_p_layout.addLayout(top_p_controls)

        # Max Tokens
        max_tokens_layout = QtWidgets.QVBoxLayout()
        max_tokens_header = MLabel(self.tr("Max Tokens")).h4()
        max_tokens_controls = QtWidgets.QHBoxLayout()
        self.max_tokens_slider = MSlider(QtCore.Qt.Horizontal)
        self.max_tokens_slider.setRange(1, 16384)
        self.max_tokens_slider.setValue(4096)
        self.max_tokens_slider.disable_show_text()
        self.max_tokens_edit = MLineEdit().small()
        self.max_tokens_edit.setFixedWidth(70)
        self.max_tokens_edit.setValidator(QIntValidator(1, 16384))
        self.max_tokens_edit.setText("4096")
        max_tokens_controls.addWidget(self.max_tokens_slider)
        max_tokens_controls.addWidget(self.max_tokens_edit)
        max_tokens_layout.addWidget(max_tokens_header)
        max_tokens_layout.addLayout(max_tokens_controls)

        advanced_layout.addLayout(top_p_layout)
        advanced_layout.addSpacing(10)
        advanced_layout.addLayout(max_tokens_layout)

        self.advanced_collapse = MCollapse()
        section_data = {"title": "Advanced Settings", "widget": advanced_widget, "expand": False}
        self.advanced_collapse.add_section(section_data)

        right_layout.addLayout(temp_layout)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.advanced_collapse)
        right_layout.addStretch(1)

        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 1)

        v.addLayout(main_layout)
        v.addStretch(1)

        # Signals
        self.temp_slider.valueChanged.connect(self._update_temp_edit)
        self.temp_edit.textChanged.connect(self._update_temp_slider)
        self.top_p_slider.valueChanged.connect(self._update_top_p_edit)
        self.top_p_edit.textChanged.connect(self._update_top_p_slider)
        self.max_tokens_slider.valueChanged.connect(self._update_max_tokens_edit)
        self.max_tokens_edit.textChanged.connect(self._update_max_tokens_slider)

    def _update_temp_edit(self):
        self.temp_edit.setText(str(self.temp_slider.value() / 100.0))

    def _update_temp_slider(self):
        try:
            if self.temp_edit.text():
                self.temp_slider.setValue(int(float(self.temp_edit.text()) * 100))
        except ValueError:
            pass

    def _update_top_p_edit(self):
        self.top_p_edit.setText(str(self.top_p_slider.value() / 100.0))

    def _update_top_p_slider(self):
        try:
            if self.top_p_edit.text():
                self.top_p_slider.setValue(int(float(self.top_p_edit.text()) * 100))
        except ValueError:
            pass

    def _update_max_tokens_edit(self):
        self.max_tokens_edit.setText(str(self.max_tokens_slider.value()))

    def _update_max_tokens_slider(self):
        try:
            if self.max_tokens_edit.text():
                value = max(1, min(int(self.max_tokens_edit.text()), 16384))
                self.max_tokens_slider.setValue(value)
        except ValueError:
            pass
