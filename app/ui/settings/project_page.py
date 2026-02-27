from PySide6 import QtCore, QtWidgets

from ..dayu_widgets.label import MLabel
from ..dayu_widgets.spin_box import MSpinBox


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

        layout.addWidget(auto_recover_label)
        layout.addWidget(auto_recover_note)
        layout.addLayout(interval_layout)
        layout.addStretch(1)
