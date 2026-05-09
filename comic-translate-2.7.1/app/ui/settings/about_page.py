from PySide6 import QtWidgets, QtCore
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.push_button import MPushButton
from app.version import __version__

class AboutPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title_label = MLabel(self.tr("App Information")).h3()
        layout.addWidget(title_label)
        
        # Version Info
        version_layout = QtWidgets.QHBoxLayout()
        version_title = MLabel(self.tr("Current Version:")).strong()
        self.version_value = MLabel(__version__)
        version_layout.addWidget(version_title)
        version_layout.addWidget(self.version_value)
        version_layout.addStretch()
        
        layout.addLayout(version_layout)
        
        # Update Section
        update_layout = QtWidgets.QHBoxLayout()
        self.check_update_button = MPushButton(self.tr("Check for Updates"))
        self.check_update_button.setFixedWidth(150)
        update_layout.addWidget(self.check_update_button)
        update_layout.addStretch()
        
        layout.addLayout(update_layout)
        
        layout.addStretch()
        
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Maximum)
