"""Custom frameless title bar for Comic Translate."""

from __future__ import annotations

import platform

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from .dayu_widgets import dayu_theme
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
IS_MACOS = platform.system() == "Darwin"
USE_MAC_STYLE_CONTROLS = IS_MACOS

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
        self.title_label = QtWidgets.QLabel(self._title_text, self)
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
        self.title_label.raise_()
        self._layout_title_label()

    # Public update helpers

    def update_title(self, title: str) -> None:
        win = self.window()
        is_modified = bool(win.isWindowModified()) if win is not None else False
        self._title_text = _clean_title(title, is_modified)
        self._layout_title_label()

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
        self._layout_title_label()

    def set_undo_redo_visible(self, visible: bool) -> None:
        """Show or hide the undo/redo tool group."""
        if self._undo_redo_widget:
            self._undo_redo_widget.setVisible(visible)
            self._layout_title_label()

    def set_autosave_visible(self, visible: bool) -> None:
        """Show or hide the auto-save label and toggle switch."""
        self.autosave_label.setVisible(visible)
        self.autosave_switch.setVisible(visible)
        if visible:
            self._configure_autosave_switch_geometry()
        self._layout_title_label()

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
        fg_color    = QtGui.QColor(fg)
        hover_color = QtGui.QColor(hover)
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
        self._layout_title_label()

    def _layout_title_label(self) -> None:
        """Center title in full bar width, then clamp to avoid side-widget overlap."""
        if not self._title_text:
            self.title_label.hide()
            return

        left_bound = self._left_host.geometry().right() + 1 + TITLE_SAFE_GAP
        right_bound = self._right_host.geometry().x() - TITLE_SAFE_GAP
        available_width = right_bound - left_bound
        if available_width <= 0:
            self.title_label.hide()
            return

        fm = self.title_label.fontMetrics()
        desired_width = min(fm.horizontalAdvance(self._title_text) + 2, available_width)
        centered_x = int((self.width() - desired_width) / 2)
        x = max(left_bound, min(centered_x, right_bound - desired_width))

        self.title_label.setGeometry(x, 0, desired_width, self.height())
        self.title_label.setText(fm.elidedText(self._title_text, Qt.TextElideMode.ElideRight, desired_width))
        self.title_label.show()

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
        self._layout_title_label()

    def event(self, event: QtCore.QEvent) -> bool:
        result = super().event(event)
        if event.type() in (
            QtCore.QEvent.Type.LayoutRequest,
            QtCore.QEvent.Type.Show,
        ):
            QtCore.QTimer.singleShot(0, self._layout_title_label)
        return result

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
