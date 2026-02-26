"""Custom frameless title bar for Comic Translate."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from .dayu_widgets.switch import MSwitch


# Height of the title bar in pixels
TITLE_BAR_HEIGHT = 36
# Width of each window-control button (min / max / close)
BUTTON_WIDTH = 46
# Edge hotspot thickness used by the frameless resize handler.
RESIZE_MARGIN = 6

# Icon kinds for _CtrlButton
_MINIMIZE = "minimize"
_MAXIMIZE = "maximize"
_RESTORE  = "restore"
_CLOSE    = "close"


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

        hovered = self._hovered

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

    def enterEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)


class CustomTitleBar(QtWidgets.QWidget):
    """Thin title-bar replacement used with Qt.FramelessWindowHint."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui()

    # Build UI

    def _init_ui(self) -> None:
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(10, 0, 0, 0)
        self._layout.setSpacing(0)

        # ----- App icon -----
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
        self.title_label = QtWidgets.QLabel(_clean_title(win_title, is_modified))
        self.title_label.setObjectName("titleBarLabel")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Title-bar tools 
        self.autosave_label = QtWidgets.QLabel(self.tr("Auto-Save"))
        self.autosave_label.setObjectName("autosaveLabel")
        self.autosave_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.autosave_switch = MSwitch().small()
        self.autosave_switch.setObjectName("titleBarAutosaveSwitch")
        self.autosave_switch.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.autosave_switch.setToolTip(self.tr("Auto-Save Project"))

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
        self.minimize_btn = _CtrlButton(_MINIMIZE, "minimizeBtn", "Minimize")
        self.maximize_btn = _CtrlButton(_MAXIMIZE, "maximizeBtn", "Maximize")
        self.close_btn    = _CtrlButton(_CLOSE,    "closeBtn",    "Close")

        self.minimize_btn.clicked.connect(lambda: self.window().showMinimized())
        self.maximize_btn.clicked.connect(self._toggle_maximize)
        self.close_btn.clicked.connect(lambda: self.window().close())

        # Assembly 
        self._left_layout.addWidget(self.icon_label)
        self._left_layout.addSpacing(8)
        self._left_layout.addWidget(self.autosave_label)
        self._left_layout.addSpacing(6)
        self._left_layout.addWidget(self.autosave_switch)
        self._left_layout.addSpacing(8)
        self._left_layout.addWidget(self._tools_host)

        self._center_layout.addStretch()
        self._center_layout.addWidget(self.title_label)
        self._center_layout.addStretch()

        self._right_layout.addWidget(self.minimize_btn)
        self._right_layout.addWidget(self.maximize_btn)
        self._right_layout.addWidget(self.close_btn)

        self._layout.addWidget(self._left_host, 0)
        self._layout.addWidget(self._center_host, 1)
        self._layout.addWidget(self._right_host, 0)

    # Public update helpers

    def update_title(self, title: str) -> None:
        win = self.window()
        is_modified = bool(win.isWindowModified()) if win is not None else False
        self.title_label.setText(_clean_title(title, is_modified))

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

    def update_maximize_icon(self, is_maximized: bool) -> None:
        self.maximize_btn.set_kind(_RESTORE if is_maximized else _MAXIMIZE)
        self.maximize_btn.setToolTip("Restore" if is_maximized else "Maximize")

    def set_icon(self, icon: QtGui.QIcon) -> None:
        if icon and not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(20, 20))

    def apply_style(self, bg: str, fg: str, hover: str) -> None:
        """Apply theme-aware colours.  Call from ``apply_theme``."""
        fg_color    = QtGui.QColor(fg)
        hover_color = QtGui.QColor(hover)
        # Keep the unchecked switch visible against both light and dark bars.
        if fg_color.lightness() >= 128:
            switch_off_bg = "#6a6a6a"
            switch_off_border = "rgba(255,255,255,45)"
        else:
            switch_off_bg = "#d0d0d0"
            switch_off_border = "rgba(0,0,0,25)"

        for btn in (self.minimize_btn, self.maximize_btn, self.close_btn):
            btn.set_colors(fg_color, hover_color)

        self.setStyleSheet(f"""
            CustomTitleBar {{
                background-color: {bg};
            }}
            QWidget#titleBarToolsHost {{
                background: transparent;
                border: none;
            }}
            QWidget#titleBarLeftHost,
            QWidget#titleBarCenterHost,
            QWidget#titleBarRightHost {{
                background: transparent;
                border: none;
            }}
            QLabel#titleBarLabel {{
                color: {fg};
                font-size: 13px;
                background: transparent;
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
            }}
            MSwitch#titleBarAutosaveSwitch::indicator,
            MSwitch#titleBarAutosaveSwitch::indicator:unchecked,
            MSwitch#titleBarAutosaveSwitch::indicator:checked {{
                border: none;
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

    # Window controls
    def _toggle_maximize(self) -> None:
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    # Dragging / double-click
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Delegate window move to the OS via QWindow.startSystemMove()."""
        if event.button() == Qt.MouseButton.LeftButton:
            local = event.position().toPoint()
            near_top = local.y() <= RESIZE_MARGIN
            near_left = local.x() <= RESIZE_MARGIN
            near_right = local.x() >= (self.width() - RESIZE_MARGIN)
            if not (near_top or near_left or near_right):
                handle = self.window().windowHandle()
                if handle:
                    handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)


# Helpers

def _clean_title(title: str, is_modified: bool = False) -> str:
    """Render Qt's [*] marker as * only while the window is modified."""
    marker = "*" if is_modified else ""
    return title.replace("[*]", marker).strip()
