from PySide6 import QtCore, QtWidgets

from ..dayu_widgets.label import MLabel
from ..dayu_widgets.spin_box import MSpinBox
from modules.utils.paths import get_default_project_autosave_dir


class ProjectPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        auto_recover_label = MLabel(self.tr("Auto-Recover")).h4()
        auto_recover_note = MLabel(
            self.tr(
                "Auto-Recover saves recovery snapshots in the background so work can be restored after a crash.\n"
                "These snapshots are not your main project file; use Save/Auto-Save for normal project saves."
            )
        ).secondary()
        auto_recover_note.setTextFormat(QtCore.Qt.PlainText)
        auto_recover_note.setWordWrap(True)

        interval_layout = QtWidgets.QHBoxLayout()
        interval_label = MLabel(self.tr("Create recovery snapshot every (minutes):"))
        self.project_autosave_interval_spinbox = MSpinBox().small()
        self.project_autosave_interval_spinbox.setMinimum(1)
        self.project_autosave_interval_spinbox.setMaximum(120)
        self.project_autosave_interval_spinbox.setValue(3)
        self.project_autosave_interval_spinbox.setFixedWidth(70)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.project_autosave_interval_spinbox)
        interval_layout.addStretch(1)

        autosave_label = MLabel(self.tr("Auto-Save Project Files")).h4()
        autosave_note = MLabel(
            self.tr(
                "These are normal .ctpr project files saved while Auto-Save is enabled.\n"
                "This folder is separate from Auto-Recover snapshots."
            )
        ).secondary()
        autosave_note.setTextFormat(QtCore.Qt.PlainText)
        autosave_note.setWordWrap(True)

        autosave_folder_layout = QtWidgets.QHBoxLayout()
        autosave_folder_label = MLabel(self.tr("Auto-Save folder:"))
        self.project_autosave_folder_input = QtWidgets.QLineEdit()
        self.project_autosave_folder_input.setMinimumWidth(280)
        self.project_autosave_folder_input.setMaximumWidth(460)
        self.project_autosave_folder_input.setPlaceholderText(
            self.tr("Select a folder for auto-saved project files")
        )
        self.project_autosave_folder_input.setText(get_default_project_autosave_dir())
        browse_button = QtWidgets.QPushButton(self.tr("Browse"))
        browse_button.clicked.connect(self._choose_autosave_folder)
        reset_button = QtWidgets.QPushButton(self.tr("Reset"))
        reset_button.clicked.connect(self._reset_autosave_folder_to_default)
        autosave_folder_layout.addWidget(autosave_folder_label)
        autosave_folder_layout.addWidget(self.project_autosave_folder_input, 1)
        autosave_folder_layout.addWidget(browse_button)
        autosave_folder_layout.addWidget(reset_button)
        autosave_folder_layout.addStretch(1)

        layout.addWidget(autosave_label)
        layout.addWidget(autosave_note)
        layout.addLayout(autosave_folder_layout)
        layout.addSpacing(12)
        layout.addWidget(auto_recover_label)
        layout.addWidget(auto_recover_note)
        layout.addLayout(interval_layout)
        layout.addStretch(1)

    def _choose_autosave_folder(self):
        current_value = self.project_autosave_folder_input.text().strip()
        initial_dir = current_value or get_default_project_autosave_dir()
        selected_folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Choose Auto-Save Folder"),
            initial_dir,
        )
        if selected_folder:
            self.project_autosave_folder_input.setText(selected_folder)

    def _reset_autosave_folder_to_default(self):
        self.project_autosave_folder_input.setText(get_default_project_autosave_dir())
