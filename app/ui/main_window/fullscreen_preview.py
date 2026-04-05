from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.ui.canvas.image_viewer import ImageViewer


class FullscreenResultPreview(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edited Page Preview"))
        self.setModal(False)
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)

        self._navigate_callback = None
        self._pending_image_array = None

        self.title_label = QtWidgets.QLabel(self.tr("Edited Preview"))
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "color: #f4f4f4; font-size: 16px; font-weight: 600; padding: 12px;"
        )

        self.image_viewer = ImageViewer(self, read_only=True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_viewer, 1)

    def set_navigation_callback(self, callback):
        self._navigate_callback = callback

    def _apply_pending_preview(self):
        if self._pending_image_array is None:
            return
        self.image_viewer.display_image_array(self._pending_image_array, fit=True)
        self._pending_image_array = None
        self.image_viewer.setFocus()

    def show_preview(self, image_array, page_name: str = ""):
        title = self.tr("Edited Preview")
        if page_name:
            title = f"{title} - {page_name}"
        self.title_label.setText(title)
        self._pending_image_array = image_array
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        QtCore.QTimer.singleShot(0, self._apply_pending_preview)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._apply_pending_preview)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_viewer.hasPhoto():
            QtCore.QTimer.singleShot(0, self.image_viewer.fitInView)

    def keyPressEvent(self, event):
        if event.key() in (
            QtCore.Qt.Key.Key_Escape,
            QtCore.Qt.Key.Key_F5,
            QtCore.Qt.Key.Key_F11,
        ):
            self.close()
            return
        if self._navigate_callback and event.key() == QtCore.Qt.Key.Key_Left:
            self._navigate_callback(-1)
            return
        if self._navigate_callback and event.key() == QtCore.Qt.Key.Key_Right:
            self._navigate_callback(1)
            return
        super().keyPressEvent(event)
