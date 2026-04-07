"""Custom frameless title bar for Comic Translate."""

from __future__ import annotations

import os
import platform
import sys

if sys.platform == "win32":
    import ctypes

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from .dayu_widgets import dayu_theme
from .dayu_widgets.qt import MIcon
from .dayu_widgets.switch import MSwitch


# Height of the title bar in pixels
TITLE_BAR_HEIGHT = 36
# Width of each window-control button (min / max / close)
BUTTON_WIDTH = 46
MAC_BUTTON_SIZE = 12
MAC_BUTTON_HITBOX = 16
# Edge hotspot thickness used by the frameless resize handler.
RESIZE_MARGIN = 6
TITLE_SAFE_GAP = 12
PROJECT_CHIP_HEIGHT = 28
IS_MACOS = platform.system() == "Darwin"
USE_MAC_STYLE_CONTROLS = IS_MACOS

# Icon kinds for _CtrlButton
_MINIMIZE = "minimize"
_MAXIMIZE = "maximize"
_RESTORE  = "restore"
_CLOSE    = "close"
if sys.platform == "win32":
    WM_NCLBUTTONDOWN = 0x00A1
    HTCAPTION = 2


class _CtrlButton(QtWidgets.QPushButton):
    """Window-control button that paints its own icon via QPainter.

    This avoids any reliance on unicode glyph rendering (which varies
    wildly across fonts and platforms).
    """

    def __init__(self, kind: str, name: str, tooltip: str) -> None:
        super().__init__()
        self._kind   = kind
        self._fg     = QtGui.QColor("#e8e8e8")
        self._hover_bg: QtGui.QColor | None = None
        self._hovered = False
        self.setObjectName(name)
        self.setFixedSize(BUTTON_WIDTH, TITLE_BAR_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setToolTip(tooltip)
        self.setText("")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self.update()

    def set_colors(self, fg: QtGui.QColor, hover_bg: QtGui.QColor) -> None:
        self._fg = fg
        self._hover_bg = hover_bg
        self.update()

    # Paint icon
    
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Combine tracked state with runtime mouse hit-testing for reliability.
        hovered = self._hovered or self.underMouse()

        # Background
        if hovered:
            if self._kind == _CLOSE:
                p.fillRect(self.rect(), QtGui.QColor("#c42b1c"))
            elif self._hover_bg:
                p.fillRect(self.rect(), self._hover_bg)

        # Icon colour: white on close-hover, normal fg otherwise
        color = QtGui.QColor("#ffffff") if (hovered and self._kind == _CLOSE) else self._fg

        cx = self.width()  // 2
        cy = self.height() // 2
        s  = 5  # half-size of the icon bounding box (~10 px wide)

        pen = QtGui.QPen(color, 1.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        if self._kind == _MINIMIZE:
            y = cy + 1
            p.drawLine(cx - s, y, cx + s, y)

        elif self._kind == _MAXIMIZE:
            r = QtCore.QRect(cx - s, cy - s, s * 2, s * 2)
            p.drawRect(r)

        elif self._kind == _RESTORE:
            # Two offset squares (back square first, then front)
            off = 2
            back  = QtCore.QRect(cx - s + off, cy - s,       s * 2 - off, s * 2 - off)
            front = QtCore.QRect(cx - s,        cy - s + off, s * 2 - off, s * 2 - off)
            p.drawRect(back)
            # Clear the overlap so back doesn't bleed through front
            bg = self.palette().color(self.backgroundRole())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRect(front.adjusted(1, 1, 0, 0))
            p.setPen(QtGui.QPen(color, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(front)

        elif self._kind == _CLOSE:
            p.setPen(QtGui.QPen(color, 1.0, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            p.drawLine(cx - s, cy - s, cx + s, cy + s)
            p.drawLine(cx + s, cy - s, cx - s, cy + s)

        p.end()

    def _set_hovered(self, hovered: bool) -> None:
        if self._hovered == hovered:
            return
        self._hovered = hovered
        self.update()

    def event(self, event: QtCore.QEvent) -> bool:
        etype = event.type()
        if etype in (
            QtCore.QEvent.Type.HoverEnter,
            QtCore.QEvent.Type.HoverMove,
            QtCore.QEvent.Type.Enter,
        ):
            self._set_hovered(True)
        elif etype in (
            QtCore.QEvent.Type.HoverLeave,
            QtCore.QEvent.Type.Leave,
            QtCore.QEvent.Type.WindowDeactivate,
            QtCore.QEvent.Type.Hide,
        ):
            self._set_hovered(False)
        return super().event(event)

    def enterEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._set_hovered(False)
        super().leaveEvent(event)


class _MacCtrlButton(QtWidgets.QPushButton):
    """macOS traffic-light window control button."""

    _COLOR_MAP = {
        _CLOSE: QtGui.QColor("#ff5f57"),
        _MINIMIZE: QtGui.QColor("#febc2e"),
        _MAXIMIZE: QtGui.QColor("#28c840"),
        _RESTORE: QtGui.QColor("#28c840"),
    }

    def __init__(self, kind: str, name: str, tooltip: str) -> None:
        super().__init__()
        self._kind = kind
        self._hovered = False
        self._fg = QtGui.QColor("#2e2e2e")
        self.setObjectName(name)
        self.setFixedSize(MAC_BUTTON_HITBOX, MAC_BUTTON_HITBOX)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setToolTip(tooltip)
        self.setText("")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self.update()

    def set_colors(self, fg: QtGui.QColor, hover_bg: QtGui.QColor) -> None:
        # Keep interface parity with _CtrlButton. Only icon foreground is relevant here.
        self._fg = fg
        self.update()

    def _set_hovered(self, hovered: bool) -> None:
        if self._hovered == hovered:
            return
        self._hovered = hovered
        self.update()

    def event(self, event: QtCore.QEvent) -> bool:
        etype = event.type()
        if etype in (
            QtCore.QEvent.Type.HoverEnter,
            QtCore.QEvent.Type.HoverMove,
            QtCore.QEvent.Type.Enter,
        ):
            self._set_hovered(True)
        elif etype in (
            QtCore.QEvent.Type.HoverLeave,
            QtCore.QEvent.Type.Leave,
            QtCore.QEvent.Type.WindowDeactivate,
            QtCore.QEvent.Type.Hide,
        ):
            self._set_hovered(False)
        return super().event(event)

    def enterEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._set_hovered(False)
        super().leaveEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        color = self._COLOR_MAP.get(self._kind, self._COLOR_MAP[_MAXIMIZE])
        diameter = min(MAC_BUTTON_SIZE, self.width() - 2, self.height() - 2)
        circle = QtCore.QRectF(
            (self.width() - diameter) / 2.0,
            (self.height() - diameter) / 2.0,
            diameter,
            diameter,
        )
        center = circle.center()

        p.setPen(QtGui.QPen(color.darker(115), 0.9))
        p.setBrush(color)
        p.drawEllipse(circle)

        if self._hovered or self.underMouse():
            icon_pen = QtGui.QPen(QtGui.QColor(45, 45, 45), 1.1)
            icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(icon_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            cx = int(center.x())
            cy = int(center.y())
            s = 3

            if self._kind == _CLOSE:
                p.drawLine(cx - s, cy - s, cx + s, cy + s)
                p.drawLine(cx + s, cy - s, cx - s, cy + s)
            elif self._kind == _MINIMIZE:
                p.drawLine(cx - s, cy, cx + s, cy)
            elif self._kind == _RESTORE:
                p.drawRect(QtCore.QRect(cx - s + 1, cy - s, 4, 4))
                p.drawRect(QtCore.QRect(cx - s, cy - s + 1, 4, 4))
            else:
                p.drawLine(cx - s, cy, cx + s, cy)
                p.drawLine(cx, cy - s, cx, cy + s)

        p.end()


class _ProjectChip(QtWidgets.QAbstractButton):
    """Clickable title chip that shows the current project name."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self._display_text = ""
        self._fg = QtGui.QColor("#e8e8e8")
        self._hover_bg = QtGui.QColor(255, 255, 255, 28)
        self._border = QtGui.QColor(255, 255, 255, 36)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(PROJECT_CHIP_HEIGHT)

    def set_text(self, text: str) -> None:
        self._full_text = text
        self._display_text = text
        self.update()

    def set_display_text(self, text: str) -> None:
        self._display_text = text
        self.update()

    def full_text(self) -> str:
        return self._full_text

    def set_colors(self, fg: QtGui.QColor, hover_bg: QtGui.QColor) -> None:
        self._fg = QtGui.QColor(fg)
        self._hover_bg = QtGui.QColor(hover_bg)
        if self._fg.lightness() >= 128:
            self._border = QtGui.QColor(255, 255, 255, 38)
        else:
            self._border = QtGui.QColor(0, 0, 0, 36)
        self.update()

    def sizeHint(self) -> QtCore.QSize:
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self._full_text or "Project1.ctpr")
        return QtCore.QSize(text_width + 40, PROJECT_CHIP_HEIGHT)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        del event
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)
        hovered = self.underMouse() or self.isChecked()
        if hovered:
            p.setPen(QtGui.QPen(self._border, 1))
            p.setBrush(self._hover_bg)
            p.drawRoundedRect(rect, 8, 8)

        p.setPen(self._fg)
        text_rect = rect.adjusted(12, 0, -28, 0)
        p.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._display_text,
        )

        icon = MIcon("titlebar-project-chevron.svg", self._fg.name())
        icon_rect = QtCore.QRect(rect.right() - 18, rect.center().y() - 7, 14, 14)
        icon.paint(p, icon_rect)
        p.end()


class _ProjectDetailsPopup(QtWidgets.QFrame):
    """Anchored popup used to rename or relocate the current project file."""

    project_target_requested = QtCore.Signal(str)
    visibilityChanged = QtCore.Signal(bool)

    _NOTCH_HEIGHT = 10
    _NOTCH_HALF_WIDTH = 12

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setObjectName("projectDetailsPopup")
        self._bg = QtGui.QColor("#ffffff")
        self._border = QtGui.QColor(0, 0, 0, 34)
        self._fg = QtGui.QColor("#1a1a1a")
        self._muted = QtGui.QColor("#666666")
        self._current_project_path: str | None = None
        self._anchor_widget: QtWidgets.QWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, self._NOTCH_HEIGHT + 16, 18, 18)
        layout.setSpacing(10)

        file_label = QtWidgets.QLabel(self.tr("File name"), self)
        file_label.setObjectName("projectPopupSectionLabel")
        layout.addWidget(file_label)

        file_row = QtWidgets.QHBoxLayout()
        file_row.setSpacing(8)
        self.name_edit = QtWidgets.QLineEdit(self)
        self.name_edit.setObjectName("projectPopupLineEdit")
        self.name_edit.setClearButtonEnabled(True)
        self.name_edit.returnPressed.connect(self._emit_apply)
        file_row.addWidget(self.name_edit, 1)

        self.extension_label = QtWidgets.QLabel(".ctpr", self)
        self.extension_label.setObjectName("projectPopupSuffix")
        self.extension_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        file_row.addWidget(self.extension_label, 0)
        layout.addLayout(file_row)

        location_label = QtWidgets.QLabel(self.tr("Location"), self)
        location_label.setObjectName("projectPopupSectionLabel")
        layout.addWidget(location_label)

        location_row = QtWidgets.QHBoxLayout()
        location_row.setSpacing(8)
        self.location_edit = QtWidgets.QLineEdit(self)
        self.location_edit.setObjectName("projectPopupLineEdit")
        self.location_edit.setClearButtonEnabled(True)
        self.location_edit.returnPressed.connect(self._emit_apply)
        location_row.addWidget(self.location_edit, 1)

        self.browse_button = QtWidgets.QPushButton(self.tr("Browse"), self)
        self.browse_button.setObjectName("projectPopupBrowseButton")
        self.browse_button.clicked.connect(self._browse_for_location)
        location_row.addWidget(self.browse_button, 0)
        layout.addLayout(location_row)

        self.hint_label = QtWidgets.QLabel(self)
        self.hint_label.setObjectName("projectPopupHint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.addStretch(1)
        self.apply_button = QtWidgets.QPushButton(self.tr("Apply"), self)
        self.apply_button.setObjectName("projectPopupApplyButton")
        self.apply_button.clicked.connect(self._emit_apply)
        actions_row.addWidget(self.apply_button, 0)
        layout.addLayout(actions_row)

        self.setFixedWidth(392)

    def apply_colors(self, bg: str, fg: str) -> None:
        self._bg = QtGui.QColor(bg)
        self._fg = QtGui.QColor(fg)
        is_light_theme = self._fg.lightness() < 128
        if is_light_theme:
            panel_bg = "#ffffff"
            input_bg = "#ffffff"
            border = "rgba(0,0,0,28)"
            border_color = QtGui.QColor(0, 0, 0, 28)
            muted = "#5f6368"
            browse_bg = "#f5f6f7"
        else:
            panel_bg = "#313131"
            input_bg = "#262626"
            border = "rgba(255,255,255,34)"
            border_color = QtGui.QColor(255, 255, 255, 34)
            muted = "#b7b7b7"
            browse_bg = "#3a3a3a"

        self._bg = QtGui.QColor(panel_bg)
        self._border = border_color
        self._muted = QtGui.QColor(muted)

        self.setStyleSheet(f"""
            QLabel#projectPopupSectionLabel {{
                color: {fg};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }}
            QLabel#projectPopupSuffix {{
                color: {muted};
                font-size: 12px;
                background: transparent;
                min-width: 34px;
            }}
            QLabel#projectPopupHint {{
                color: {muted};
                font-size: 11px;
                background: transparent;
            }}
            QLineEdit#projectPopupLineEdit {{
                min-height: 34px;
                padding: 0 10px;
                border-radius: 10px;
                border: 1px solid {border};
                background: {input_bg};
                color: {fg};
                selection-background-color: rgba(24, 144, 255, 90);
            }}
            QLineEdit#projectPopupLineEdit:focus {{
                border: 1px solid #1677ff;
            }}
            QPushButton#projectPopupBrowseButton {{
                min-height: 34px;
                padding: 0 12px;
                border-radius: 10px;
                border: 1px solid {border};
                background: {browse_bg};
                color: {fg};
            }}
            QPushButton#projectPopupBrowseButton:hover {{
                border: 1px solid #1677ff;
            }}
            QPushButton#projectPopupApplyButton {{
                min-width: 88px;
                min-height: 34px;
                padding: 0 12px;
                border: none;
                border-radius: 10px;
                background: #1677ff;
                color: white;
                font-weight: 600;
            }}
            QPushButton#projectPopupApplyButton:hover {{
                background: #2a85ff;
            }}
        """)
        self.update()

    def prepare_for_window(self, window: QtWidgets.QWidget | None) -> None:
        project_path = getattr(window, "project_file", None) if window is not None else None
        self._current_project_path = (
            os.path.normpath(os.path.abspath(project_path))
            if isinstance(project_path, str) and project_path
            else None
        )

        if self._current_project_path:
            stem = os.path.splitext(os.path.basename(self._current_project_path))[0]
            directory = os.path.dirname(self._current_project_path)
            hint = self.tr("Apply to rename or move the current project file.")
        else:
            clean_title = ""
            if window is not None:
                clean_title = _clean_title(
                    window.windowTitle(),
                    bool(window.isWindowModified()),
                )
            stem = _project_stem_from_title(clean_title) or "Project1"
            directory = _default_project_directory(window)
            hint = self.tr("Apply to save the current project file with a new name or location.")

        self.name_edit.setText(stem)
        self.location_edit.setText(directory)
        self.hint_label.setText(hint)

    def show_anchored(self, anchor: QtWidgets.QWidget) -> None:
        self._anchor_widget = anchor
        parent_window = anchor.window()
        if self.parentWidget() is not parent_window:
            self.setParent(parent_window, self.windowFlags())

        self.adjustSize()
        screen = anchor.screen() or QtWidgets.QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QtCore.QRect()

        anchor_center = anchor.mapToGlobal(anchor.rect().center())
        anchor_bottom = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height())).y()
        x = anchor_center.x() - int(self.width() / 2)
        y = anchor_bottom + 8

        if available.isValid():
            x = max(available.left() + 8, min(x, available.right() - self.width() - 8))
            y = min(y, available.bottom() - self.height() - 8)

        self._update_popup_mask()
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.name_edit.setFocus(Qt.FocusReason.PopupFocusReason)
        self.name_edit.selectAll()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_popup_mask()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        del event
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        path = self._popup_path(inset=0.5)
        p.setPen(QtGui.QPen(self._border, 1))
        p.setBrush(self._bg)
        p.drawPath(path)
        p.end()

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.visibilityChanged.emit(True)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self.visibilityChanged.emit(False)

    def _popup_path(self, inset: float = 0.0) -> QtGui.QPainterPath:
        rect = QtCore.QRectF(
            inset,
            self._NOTCH_HEIGHT + inset,
            max(0.0, self.width() - (inset * 2)),
            max(0.0, self.height() - self._NOTCH_HEIGHT - (inset * 2)),
        )
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        center_x = self.width() / 2.0
        notch = QtGui.QPainterPath()
        notch.moveTo(center_x - self._NOTCH_HALF_WIDTH, self._NOTCH_HEIGHT + inset)
        notch.lineTo(center_x, inset)
        notch.lineTo(center_x + self._NOTCH_HALF_WIDTH, self._NOTCH_HEIGHT + inset)
        notch.closeSubpath()
        return path.united(notch)

    def _update_popup_mask(self) -> None:
        region = QtGui.QRegion(self._popup_path().toFillPolygon().toPolygon())
        self.setMask(region)

    def _browse_for_location(self) -> None:
        current_dir = self.location_edit.text().strip() or os.path.expanduser("~")
        anchor = self._anchor_widget
        current_name = self.name_edit.text()
        self.hide()
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self.window(),
            self.tr("Choose Project Folder"),
            current_dir,
        )
        if selected:
            self.location_edit.setText(selected)
        self.name_edit.setText(current_name)
        if anchor is not None and anchor.isVisible():
            self.show_anchored(anchor)
            self.location_edit.setFocus(Qt.FocusReason.PopupFocusReason)
            self.location_edit.deselect()
            self.location_edit.end(False)

    def _emit_apply(self) -> None:
        stem = self.name_edit.text().strip()
        directory = os.path.expanduser(self.location_edit.text().strip())
        if stem.lower().endswith(".ctpr"):
            stem = stem[:-5]

        if not stem:
            QtWidgets.QMessageBox.warning(
                self.window(),
                self.tr("Project File"),
                self.tr("Enter a file name."),
            )
            self.name_edit.setFocus(Qt.FocusReason.PopupFocusReason)
            return

        if not directory:
            QtWidgets.QMessageBox.warning(
                self.window(),
                self.tr("Project File"),
                self.tr("Choose a folder location."),
            )
            self.location_edit.setFocus(Qt.FocusReason.PopupFocusReason)
            return

        self.project_target_requested.emit(os.path.join(directory, f"{stem}.ctpr"))
        self.hide()


class CustomTitleBar(QtWidgets.QWidget):
    """Thin title-bar replacement used with Qt.FramelessWindowHint."""

    project_target_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._ignore_next_project_chip_click = False
        self._init_ui()

    # Build UI

    def _init_ui(self) -> None:
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(10, 0, 0, 0)
        self._layout.setSpacing(0)

        # App icon
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        win = self.window()
        if win is not None:
            icon = win.windowIcon()
            if icon and not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(20, 20))

        # Title label 
        win_title = win.windowTitle() if win is not None else ""
        is_modified = bool(win.isWindowModified()) if win is not None else False
        self._title_text = _clean_title(win_title, is_modified)
        self.project_chip = _ProjectChip(self)
        self.project_chip.setObjectName("titleBarProjectChip")
        self.project_chip.set_text(self._title_text)
        self.project_chip.clicked.connect(self._toggle_project_popup)

        self._project_popup = _ProjectDetailsPopup(self)
        self._project_popup.project_target_requested.connect(self.project_target_requested)
        self._project_popup.visibilityChanged.connect(self._sync_project_popup_state)

        # Title-bar tools 
        self.autosave_label = QtWidgets.QLabel(self.tr("Auto-Save"))
        self.autosave_label.setObjectName("autosaveLabel")
        self.autosave_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.autosave_switch = MSwitch().small()
        self.autosave_switch.setObjectName("titleBarAutosaveSwitch")
        self.autosave_switch.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.autosave_switch.setToolTip(self.tr("Auto-Save Project"))
        self._configure_autosave_switch_geometry()

        self._tools_host = QtWidgets.QWidget(self)
        self._tools_host.setObjectName("titleBarToolsHost")
        self._tools_layout = QtWidgets.QHBoxLayout(self._tools_host)
        self._tools_layout.setContentsMargins(0, 0, 0, 0)
        self._tools_layout.setSpacing(1)
        self._undo_redo_widget: QtWidgets.QWidget | None = None

        self._left_host = QtWidgets.QWidget(self)
        self._left_host.setObjectName("titleBarLeftHost")
        self._left_layout = QtWidgets.QHBoxLayout(self._left_host)
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setSpacing(0)

        self._center_host = QtWidgets.QWidget(self)
        self._center_host.setObjectName("titleBarCenterHost")
        self._center_layout = QtWidgets.QHBoxLayout(self._center_host)
        self._center_layout.setContentsMargins(0, 0, 0, 0)
        self._center_layout.setSpacing(0)

        self._right_host = QtWidgets.QWidget(self)
        self._right_host.setObjectName("titleBarRightHost")
        self._right_layout = QtWidgets.QHBoxLayout(self._right_host)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.setSpacing(0)

        # Window-control buttons 
        btn_cls = _MacCtrlButton if USE_MAC_STYLE_CONTROLS else _CtrlButton
        self.minimize_btn = btn_cls(_MINIMIZE, "minimizeBtn", "Minimize")
        self.maximize_btn = btn_cls(_MAXIMIZE, "maximizeBtn", "Maximize")
        self.close_btn = btn_cls(_CLOSE, "closeBtn", "Close")

        self.minimize_btn.clicked.connect(lambda: self.window().showMinimized())
        self.maximize_btn.clicked.connect(self._toggle_maximize)
        self.close_btn.clicked.connect(lambda: self.window().close())

        self._window_controls_host = QtWidgets.QWidget(self)
        self._window_controls_host.setObjectName("titleBarWindowControls")
        self._window_controls_layout = QtWidgets.QHBoxLayout(self._window_controls_host)
        self._window_controls_layout.setContentsMargins(0, 0, 0, 0)
        self._window_controls_layout.setSpacing(6 if USE_MAC_STYLE_CONTROLS else 0)
        if USE_MAC_STYLE_CONTROLS:
            # macOS order: close, minimize, maximize (left to right)
            self._window_controls_layout.addWidget(self.close_btn)
            self._window_controls_layout.addWidget(self.minimize_btn)
            self._window_controls_layout.addWidget(self.maximize_btn)
        else:
            self._window_controls_layout.addWidget(self.minimize_btn)
            self._window_controls_layout.addWidget(self.maximize_btn)
            self._window_controls_layout.addWidget(self.close_btn)

        # Assembly 
        if USE_MAC_STYLE_CONTROLS:
            self._left_layout.addWidget(self._window_controls_host)
            self._left_layout.addSpacing(10)

        if not USE_MAC_STYLE_CONTROLS:
            self._left_layout.addWidget(self.icon_label)
            self._left_layout.addSpacing(8)
        self._left_layout.addWidget(self.autosave_label)
        self._left_layout.addSpacing(6)
        self._left_layout.addWidget(self.autosave_switch)
        self._left_layout.addSpacing(8)
        self._left_layout.addWidget(self._tools_host)

        # Keep a flexible middle spacer. Title text itself is overlay-positioned
        # to remain centered against full bar width, then clamped to avoid overlap.
        self._center_layout.addStretch()

        if not USE_MAC_STYLE_CONTROLS:
            self._right_layout.addWidget(self._window_controls_host)

        self._layout.addWidget(self._left_host, 0)
        self._layout.addWidget(self._center_host, 1)
        self._layout.addWidget(self._right_host, 0)
        self.project_chip.raise_()
        self._layout_title_chip()

    # Public update helpers

    def update_title(self, title: str) -> None:
        win = self.window()
        is_modified = bool(win.isWindowModified()) if win is not None else False
        self._title_text = _clean_title(title, is_modified)
        self.project_chip.set_text(self._title_text)
        self._layout_title_chip()

    def set_autosave_checked(self, checked: bool) -> None:
        with QtCore.QSignalBlocker(self.autosave_switch):
            self.autosave_switch.setChecked(bool(checked))

    def set_undo_redo_widget(self, widget: QtWidgets.QWidget | None) -> None:
        if self._undo_redo_widget is widget:
            return
        if self._undo_redo_widget is not None:
            self._tools_layout.removeWidget(self._undo_redo_widget)
            self._undo_redo_widget.hide()

        self._undo_redo_widget = widget
        if widget is None:
            return

        for btn in widget.findChildren(QtWidgets.QAbstractButton):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        widget.setParent(self._tools_host)
        self._tools_layout.addWidget(widget)
        widget.show()
        self._layout_title_chip()

    def set_undo_redo_visible(self, visible: bool) -> None:
        """Show or hide the undo/redo tool group."""
        if self._undo_redo_widget:
            self._undo_redo_widget.setVisible(visible)
            self._layout_title_chip()

    def set_autosave_visible(self, visible: bool) -> None:
        """Show or hide the auto-save label and toggle switch."""
        self.autosave_label.setVisible(visible)
        self.autosave_switch.setVisible(visible)
        if visible:
            self._configure_autosave_switch_geometry()
        self._layout_title_chip()

    def update_maximize_icon(self, is_maximized: bool) -> None:
        self.maximize_btn.set_kind(_RESTORE if is_maximized else _MAXIMIZE)
        if USE_MAC_STYLE_CONTROLS:
            self.maximize_btn.setToolTip("Zoom")
        else:
            self.maximize_btn.setToolTip("Restore" if is_maximized else "Maximize")

    def set_icon(self, icon: QtGui.QIcon) -> None:
        if icon and not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(20, 20))

    def apply_style(self, bg: str, fg: str, hover: str) -> None:
        """Apply theme-aware colours.  Call from ``apply_theme``."""
        fg_color = QtGui.QColor(fg)
        hover_color = _parse_qcolor(hover)
        switch_width = int(getattr(dayu_theme, "switch_width_small", 28))
        switch_height = int(getattr(dayu_theme, "switch_height_small", 14))
        # Keep the unchecked switch visible against both light and dark bars.
        if fg_color.lightness() >= 128:
            switch_off_bg = "#6a6a6a"
            switch_off_border = "rgba(255,255,255,45)"
        else:
            switch_off_bg = "#d0d0d0"
            switch_off_border = "rgba(0,0,0,25)"

        for btn in (self.minimize_btn, self.maximize_btn, self.close_btn):
            btn.set_colors(fg_color, hover_color)
        self.project_chip.set_colors(fg_color, hover_color)
        self._project_popup.apply_colors(bg, fg)

        self.setStyleSheet(f"""
            CustomTitleBar {{
                background-color: {bg};
            }}
            QWidget#titleBarToolsHost {{
                background: transparent;
                border: none;
            }}
            QWidget#titleBarWindowControls {{
                background: transparent;
                border: none;
            }}
            QWidget#titleBarLeftHost,
            QWidget#titleBarCenterHost,
            QWidget#titleBarRightHost {{
                background: transparent;
                border: none;
            }}
            QLabel#autosaveLabel {{
                color: {fg};
                font-size: 12px;
                background: transparent;
            }}
            MSwitch#titleBarAutosaveSwitch {{
                background: transparent;
                border: none;
                spacing: 0px;
                min-width: {switch_width + 4}px;
                max-width: {switch_width + 4}px;
                min-height: {switch_height + 4}px;
                max-height: {switch_height + 4}px;
            }}
            MSwitch#titleBarAutosaveSwitch::indicator,
            MSwitch#titleBarAutosaveSwitch::indicator:unchecked,
            MSwitch#titleBarAutosaveSwitch::indicator:checked {{
                border: none;
                width: {switch_width}px;
                height: {switch_height}px;
            }}
            MSwitch#titleBarAutosaveSwitch::indicator:unchecked {{
                background-color: {switch_off_bg};
                border: 1px solid {switch_off_border};
            }}
            MSwitch#titleBarAutosaveSwitch::indicator:checked {{
                background-color: #1890ff;
            }}
            MToolButton,
            MToolButton:hover,
            MToolButton:pressed,
            MToolButton:checked,
            MToolButton:focus {{
                background: transparent;
                border: none;
            }}
            QPushButton#minimizeBtn,
            QPushButton#maximizeBtn,
            QPushButton#closeBtn {{
                background: transparent;
                border: none;
            }}
        """)
        self._layout_title_chip()

    def _layout_title_chip(self) -> None:
        """Center the project chip in full bar width, clamped by side widgets."""
        if not self._title_text:
            self.project_chip.hide()
            self._project_popup.hide()
            return

        left_bound = self._left_host.geometry().right() + 1 + TITLE_SAFE_GAP
        right_bound = self._right_host.geometry().x() - TITLE_SAFE_GAP
        available_width = right_bound - left_bound
        if available_width <= 0:
            self.project_chip.hide()
            self._project_popup.hide()
            return

        fm = self.project_chip.fontMetrics()
        desired_width = min(max(120, fm.horizontalAdvance(self._title_text) + 40), available_width)
        centered_x = int((self.width() - desired_width) / 2)
        x = max(left_bound, min(centered_x, right_bound - desired_width))
        y = int((self.height() - PROJECT_CHIP_HEIGHT) / 2)
        self.project_chip.setGeometry(x, y, desired_width, PROJECT_CHIP_HEIGHT)
        self.project_chip.set_display_text(
            _elide_title_preserving_dirty_marker(
                self._title_text,
                fm,
                max(0, desired_width - 40),
            )
        )
        self.project_chip.show()

    def _configure_autosave_switch_geometry(self) -> None:
        """Keep a stable paint area so switch indicator never clips after relayout."""
        switch_width = int(getattr(dayu_theme, "switch_width_small", 28))
        switch_height = int(getattr(dayu_theme, "switch_height_small", 14))
        self.autosave_switch.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.autosave_switch.setFixedSize(switch_width + 4, switch_height + 4)
        self.autosave_switch.updateGeometry()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_title_chip()
        if self._project_popup.isVisible():
            self._project_popup.hide()

    def event(self, event: QtCore.QEvent) -> bool:
        result = super().event(event)
        if event.type() in (
            QtCore.QEvent.Type.LayoutRequest,
            QtCore.QEvent.Type.Show,
        ):
            QtCore.QTimer.singleShot(0, self._layout_title_chip)
        return result

    def _toggle_project_popup(self) -> None:
        if self._ignore_next_project_chip_click:
            self._ignore_next_project_chip_click = False
            return
        if self._project_popup.isVisible():
            self._project_popup.hide()
            return
        self._project_popup.prepare_for_window(self.window())
        self._project_popup.show_anchored(self.project_chip)

    def _sync_project_popup_state(self, visible: bool) -> None:
        with QtCore.QSignalBlocker(self.project_chip):
            self.project_chip.setChecked(bool(visible))
        if not visible:
            chip_rect = QtCore.QRect(
                self.project_chip.mapToGlobal(QtCore.QPoint(0, 0)),
                self.project_chip.size(),
            )
            if chip_rect.contains(QtGui.QCursor.pos()):
                self._ignore_next_project_chip_click = True

    # Window controls
    def _toggle_maximize(self) -> None:
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    def is_caption_draggable(self, local_pos: QtCore.QPoint) -> bool:
        """Return whether *local_pos* is a safe caption drag region."""
        if not self.rect().contains(local_pos):
            return False

        child = self.childAt(local_pos)
        while child is not None and child is not self:
            if child.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents):
                child = child.parentWidget()
                continue
            if isinstance(
                child,
                (
                    QtWidgets.QAbstractButton,
                    QtWidgets.QAbstractSlider,
                    QtWidgets.QAbstractSpinBox,
                    QtWidgets.QComboBox,
                    QtWidgets.QLineEdit,
                    QtWidgets.QTextEdit,
                    QtWidgets.QPlainTextEdit,
                    QtWidgets.QAbstractItemView,
                ),
            ):
                return False
            child = child.parentWidget()
        return True

    # Dragging / double-click
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Delegate window move to the OS via QWindow.startSystemMove()."""
        if event.button() == Qt.MouseButton.LeftButton:
            local = event.position().toPoint()
            near_top = local.y() <= RESIZE_MARGIN
            near_left = local.x() <= RESIZE_MARGIN
            near_right = local.x() >= (self.width() - RESIZE_MARGIN)
            if self.is_caption_draggable(local) and not (near_top or near_left or near_right):
                if sys.platform == "win32":
                    hwnd = int(self.window().winId())
                    if hwnd:
                        user32 = ctypes.windll.user32
                        user32.ReleaseCapture()
                        user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
                        event.accept()
                        return
                else:
                    handle = self.window().windowHandle()
                    if handle:
                        handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_caption_draggable(event.position().toPoint()):
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)


# Helpers

def _clean_title(title: str, is_modified: bool = False) -> str:
    """Render Qt's [*] marker as * only while the window is modified."""
    marker = "*" if is_modified else ""
    return title.replace("[*]", marker).strip()


def _elide_title_preserving_dirty_marker(
    title: str,
    font_metrics: QtGui.QFontMetrics,
    width: int,
) -> str:
    if width <= 0:
        return ""
    if not title.endswith("*"):
        return font_metrics.elidedText(title, Qt.TextElideMode.ElideRight, width)

    base_title = title[:-1].rstrip()
    dirty_marker = "*"
    dirty_width = font_metrics.horizontalAdvance(dirty_marker)
    if width <= dirty_width:
        return dirty_marker

    elided_base = font_metrics.elidedText(
        base_title,
        Qt.TextElideMode.ElideRight,
        width - dirty_width,
    )
    return f"{elided_base}{dirty_marker}"


def _parse_qcolor(value: str) -> QtGui.QColor:
    color = QtGui.QColor(value)
    if color.isValid():
        return color

    text = str(value).strip()
    if text.startswith("rgba(") and text.endswith(")"):
        parts = [part.strip() for part in text[5:-1].split(",")]
        if len(parts) == 4:
            try:
                r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]))
                a = float(parts[3])
                if a <= 1:
                    a = int(a * 255)
                return QtGui.QColor(r, g, b, int(max(0, min(255, a))))
            except ValueError:
                pass
    return QtGui.QColor("#000000")


def _project_stem_from_title(title: str) -> str:
    clean = title.rstrip("*").strip()
    if clean.lower().endswith(".ctpr"):
        clean = clean[:-5]
    return clean.strip()


def _default_project_directory(window: QtWidgets.QWidget | None) -> str:
    project_path = getattr(window, "project_file", None) if window is not None else None
    if isinstance(project_path, str) and project_path:
        return os.path.dirname(os.path.abspath(project_path))

    project_ctrl = getattr(window, "project_ctrl", None) if window is not None else None
    if project_ctrl is not None:
        try:
            return project_ctrl._get_default_project_dialog_dir()
        except Exception:
            pass

    image_files = getattr(window, "image_files", []) if window is not None else []
    if image_files:
        return os.path.dirname(os.path.abspath(image_files[0]))
    return os.path.expanduser("~")
