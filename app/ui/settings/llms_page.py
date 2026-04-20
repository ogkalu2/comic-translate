from PySide6 import QtWidgets, QtCore
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.text_edit import MTextEdit
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.collapse import MCollapse
from ..dayu_widgets.spin_box import MSpinBox

class LlmsPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        v = QtWidgets.QVBoxLayout(self)
        main_layout = QtWidgets.QHBoxLayout()

        self.image_checkbox = MCheckBox(self.tr("Provide Image as Input to AI"))
        self.image_checkbox.setChecked(False)
        self.previous_page_context_checkbox = MCheckBox(self.tr("Use Previous Page Context"))
        self.scene_memory_checkbox = MCheckBox(self.tr("Carry Scene Memory Between Pages"))
        self.interpret_then_translate_checkbox = MCheckBox(self.tr("Interpret Before Translate"))

        # Left
        left_layout = QtWidgets.QVBoxLayout()
        prompt_label = MLabel(self.tr("Extra Context:"))
        self.extra_context = MTextEdit()
        self.extra_context.setMinimumHeight(200)
        previous_page_lines_layout = QtWidgets.QHBoxLayout()
        previous_page_lines_label = MLabel(self.tr("Previous Page Lines:"))
        self.previous_page_lines_spinbox = MSpinBox().small()
        self.previous_page_lines_spinbox.setMinimum(1)
        self.previous_page_lines_spinbox.setMaximum(20)
        self.previous_page_lines_spinbox.setValue(6)
        self.previous_page_lines_spinbox.setFixedWidth(70)
        previous_page_lines_layout.addWidget(previous_page_lines_label)
        previous_page_lines_layout.addWidget(self.previous_page_lines_spinbox)
        previous_page_lines_layout.addStretch(1)
        left_layout.addWidget(prompt_label)
        left_layout.addWidget(self.extra_context)
        left_layout.addLayout(previous_page_lines_layout)
        left_layout.addWidget(self.previous_page_context_checkbox)
        left_layout.addWidget(self.scene_memory_checkbox)
        left_layout.addWidget(self.interpret_then_translate_checkbox)
        left_layout.addWidget(self.image_checkbox)
        left_layout.addStretch(1)

        # Right
        right_layout = QtWidgets.QVBoxLayout()

        # Advanced settings

        right_layout.addSpacing(10)
        right_layout.addStretch(1)

        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 1)

        v.addLayout(main_layout)
        v.addStretch(1)

        self.extra_context.textChanged.connect(self._limit_extra_context)

    def _limit_extra_context(self):
        max_length = 1000
        text = self.extra_context.toPlainText()
        if len(text) > max_length:
            # Preserve cursor position
            cursor = self.extra_context.textCursor()
            position = cursor.position()
            
            # Truncate
            self.extra_context.setPlainText(text[:max_length])
            
            # Restore cursor (clamped to end)
            new_position = min(position, max_length)
            cursor.setPosition(new_position)
            self.extra_context.setTextCursor(cursor)

