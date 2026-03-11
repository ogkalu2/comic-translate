import sys
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.canvas.image_viewer import ImageViewer
from app.ui.dayu_widgets import dayu_theme
from app.ui.dayu_widgets.divider import MDivider
from app.ui.dayu_widgets.theme import MTheme
from app.ui.list_view import PageListView
from app.ui.settings.settings_page import SettingsPage
from app.ui.startup_home import StartupHomeScreen
from app.ui.title_bar import CustomTitleBar, RESIZE_MARGIN
from .builders import MainWindowBuildersMixin
from .frame import EdgeResizer
from .tools import ToolStateMixin

if sys.platform == "win32":
    WM_NCHITTEST = 0x0084
    HTCLIENT = 1
    HTCAPTION = 2
    HTLEFT = 10
    HTRIGHT = 11
    HTTOP = 12
    HTTOPLEFT = 13
    HTTOPRIGHT = 14
    HTBOTTOM = 15
    HTBOTTOMLEFT = 16
    HTBOTTOMRIGHT = 17
    GWL_STYLE = -16
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    WS_THICKFRAME = 0x00040000
    WS_SYSMENU = 0x00080000
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020

    class _WinMSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", wintypes.POINT),
            ("lPrivate", wintypes.DWORD),
        ]


class ComicTranslateUI(
    MainWindowBuildersMixin, 
    ToolStateMixin, 
    QtWidgets.QMainWindow
):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowSystemMenuHint
            | QtCore.Qt.WindowType.WindowMinMaxButtonsHint
        )

        if sys.platform == "win32":
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._win_snap_style_applied = False
        self.setWindowTitle("Comic Translate[*]")

        screen = QtWidgets.QApplication.primaryScreen()
        geo = screen.geometry()

        width = float(geo.width())
        height = float(geo.height())
        x = 50
        y = 50
        w = int(width / 1.2)
        h = int(height / 1.2)
        self.setGeometry(x, y, w, h)

        self.image_viewer = ImageViewer(self)
        self.settings_page = SettingsPage(self)
        self.settings_page.theme_changed.connect(self.apply_theme)
        self.settings_page.font_imported.connect(self.set_font)
        self.main_content_widget = None
        self._workspace_initialized = False
        self.tool_buttons = {}
        self.page_list = PageListView()

        self.webtoon_mode = False

        self.grabGesture(QtCore.Qt.GestureType.PanGesture)
        self.grabGesture(QtCore.Qt.GestureType.PinchGesture)

        self.lang_mapping = {
            self.tr("English"): "English",
            self.tr("Korean"): "Korean",
            self.tr("Japanese"): "Japanese",
            self.tr("French"): "French",
            self.tr("Simplified Chinese"): "Simplified Chinese",
            self.tr("Traditional Chinese"): "Traditional Chinese",
            self.tr("Chinese"): "Chinese",
            self.tr("Russian"): "Russian",
            self.tr("German"): "German",
            self.tr("Dutch"): "Dutch",
            self.tr("Spanish"): "Spanish",
            self.tr("Italian"): "Italian",
            self.tr("Turkish"): "Turkish",
            self.tr("Polish"): "Polish",
            self.tr("Portuguese"): "Portuguese",
            self.tr("Brazilian Portuguese"): "Brazilian Portuguese",
            self.tr("Thai"): "Thai",
            self.tr("Vietnamese"): "Vietnamese",
            self.tr("Indonesian"): "Indonesian",
            self.tr("Hungarian"): "Hungarian",
            self.tr("Finnish"): "Finnish",
            self.tr("Arabic"): "Arabic",
            self.tr("Hebrew"): "Hebrew",
            self.tr("Czech"): "Czech",
            self.tr("Persian"): "Persian",
            self.tr("Romanian"): "Romanian",
            self.tr("Mongolian"): "Mongolian",
        }
        self.reverse_lang_mapping = {v: k for k, v in self.lang_mapping.items()}

        self.button_to_alignment = {
            0: QtCore.Qt.AlignmentFlag.AlignLeft,
            1: QtCore.Qt.AlignmentFlag.AlignCenter,
            2: QtCore.Qt.AlignmentFlag.AlignRight,
        }

        self._init_ui()
        self._settings_resize_preview = QtWidgets.QLabel(self._center_stack)
        self._settings_resize_preview.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._settings_resize_preview.setScaledContents(True)
        self._settings_resize_preview.setStyleSheet("background-color: #323232;")
        self._settings_resize_preview.hide()
        self._settings_resize_active = False
        self._settings_resize_settle_timer = QtCore.QTimer(self)
        self._settings_resize_settle_timer.setSingleShot(True)
        self._settings_resize_settle_timer.setInterval(120)
        self._settings_resize_settle_timer.timeout.connect(self._finish_settings_resize_preview)

    def _init_ui(self):
        outer_widget = QtWidgets.QWidget(self)
        outer_layout = QtWidgets.QVBoxLayout(outer_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(outer_widget)
        outer_layout.addWidget(self.title_bar)

        self._apply_title_bar_style("Dark")
        self._edge_resizer = EdgeResizer(self)

        main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QHBoxLayout()
        main_widget.setLayout(self.main_layout)
        outer_layout.addWidget(main_widget)

        self.setCentralWidget(outer_widget)

        nav_rail_layout = self._create_nav_rail()
        self.main_layout.addLayout(nav_rail_layout)
        self.main_layout.addWidget(MDivider(orientation=QtCore.Qt.Vertical))

        self.main_content_widget = self._create_main_content()
        self.title_bar.set_undo_redo_widget(self.undo_tool_group)
        self._center_stack = QtWidgets.QStackedWidget()

        self.startup_home = StartupHomeScreen()
        self._center_stack.addWidget(self.startup_home)
        self._center_stack.addWidget(self.main_content_widget)
        self._center_stack.addWidget(self.settings_page)

        self._center_stack.setCurrentWidget(self.startup_home)
        self._set_document_tools_visible(False)

        self.main_layout.addWidget(self._center_stack)

    def _set_document_tools_visible(self, visible: bool) -> None:
        tools = [
            self.insert_button,
            self.save_project_button,
            self.save_as_project_button,
            self.save_browser,
            self.save_all_button,
            self.search_sidebar_button,
        ]
        for t in tools:
            if hasattr(t, "setVisible"):
                t.setVisible(visible)

        if hasattr(self, "title_bar"):
            self.title_bar.set_undo_redo_visible(visible)
            self.title_bar.set_autosave_visible(visible)
            if hasattr(self.title_bar, "webtoon_toggle"):
                self.title_bar.webtoon_toggle.setVisible(visible)

    def show_home_screen(self) -> None:
        self._finish_settings_resize_preview()
        self._set_document_tools_visible(False)
        self._center_stack.setCurrentWidget(self.startup_home)

    def show_home(self) -> None:
        if self._workspace_initialized:
            self.show_main_page()
            return
        self.show_home_screen()

    def show_settings_page(self):
        if not self.settings_page:
            self.settings_page = SettingsPage(self)
        self._finish_settings_resize_preview()
        self._center_stack.setCurrentWidget(self.settings_page)

    def show_main_page(self):
        self._finish_settings_resize_preview()
        if self.settings_page:
            self._workspace_initialized = True
            self._set_document_tools_visible(True)
            self._center_stack.setCurrentWidget(self.main_content_widget)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if sys.platform != "win32":
            return
        if not hasattr(self, "_center_stack") or self._center_stack.currentWidget() is not self.settings_page:
            self._finish_settings_resize_preview()
            return
        old = event.oldSize()
        new = event.size()
        is_contracting = (
            old.isValid() and
            (new.width() < old.width() or new.height() < old.height())
        )
        if is_contracting:
            self._start_settings_resize_preview()
        else:
            self._finish_settings_resize_preview()

    def _start_settings_resize_preview(self) -> None:
        if not self._settings_resize_active:
            self.settings_page.setVisible(False)
            self._settings_resize_active = True
        # Refresh snapshot on every contraction tick to reduce "pinch" artifacts
        # from stretching a stale pixmap during live resize.
        self._settings_resize_preview.setPixmap(self.settings_page.grab())
        self._settings_resize_preview.setGeometry(self.settings_page.geometry())
        self._settings_resize_preview.show()
        self._settings_resize_preview.raise_()
        self._settings_resize_settle_timer.start()

    def _finish_settings_resize_preview(self) -> None:
        if self._settings_resize_settle_timer.isActive():
            self._settings_resize_settle_timer.stop()
        if self._settings_resize_active:
            self._settings_resize_preview.hide()
            self._settings_resize_preview.clear()
            self.settings_page.setVisible(True)
            self._settings_resize_active = False
            if hasattr(self, "settings_page") and self.settings_page is not None:
                self.settings_page.update()


    def changeEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
        super().changeEvent(event)
        if not hasattr(self, "title_bar"):
            return
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self.title_bar.update_maximize_icon(self.isMaximized())
        elif event.type() == QtCore.QEvent.Type.WindowTitleChange:
            self.title_bar.update_title(self.windowTitle())
        elif event.type() == QtCore.QEvent.Type.ModifiedChange:
            self.title_bar.update_title(self.windowTitle())

    if sys.platform == "win32":

        def showEvent(self, event: QtGui.QShowEvent) -> None:  # type: ignore[override]
            super().showEvent(event)
            if not self._win_snap_style_applied:
                self._apply_windows_snap_window_style()

        def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
            p = QtGui.QPainter(self)
            p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(self.rect(), self.palette().window())
            p.end()
            super().paintEvent(event)

        def nativeEvent(self, event_type: bytes, message: int):  # type: ignore[override]
            if isinstance(event_type, str):
                native_event_type = event_type.encode("ascii", errors="ignore")
            else:
                native_event_type = bytes(event_type)
            if native_event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                msg_ptr = int(message)
                if not msg_ptr:
                    return super().nativeEvent(event_type, message)
                msg = ctypes.cast(msg_ptr, ctypes.POINTER(_WinMSG)).contents
                if msg.message == WM_NCHITTEST:
                    x = ctypes.c_short(msg.lParam & 0xFFFF).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                    hit = self._windows_hit_test(QtCore.QPoint(x, y))
                    if hit is not None:
                        return True, int(hit)
            return super().nativeEvent(event_type, message)

        def _apply_windows_snap_window_style(self) -> None:
            hwnd = int(self.winId())
            if hwnd == 0:
                return
            user32 = ctypes.windll.user32
            get_long_ptr = user32.GetWindowLongPtrW
            set_long_ptr = user32.SetWindowLongPtrW
            long_ptr_t = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
            get_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
            get_long_ptr.restype = long_ptr_t
            set_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr_t]
            set_long_ptr.restype = long_ptr_t
            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL

            style = int(get_long_ptr(hwnd, GWL_STYLE))
            snap_style_mask = WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_THICKFRAME | WS_SYSMENU
            if (style & snap_style_mask) != snap_style_mask:
                set_long_ptr(hwnd, GWL_STYLE, long_ptr_t(style | snap_style_mask))
                user32.SetWindowPos(
                    hwnd,
                    0,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
                )
            self._win_snap_style_applied = True

        def _windows_hit_test(self, global_pos: QtCore.QPoint) -> int | None:
            local_pos = self.mapFromGlobal(global_pos)
            rect = self.rect()
            if not rect.contains(local_pos):
                return None

            if not (self.isMaximized() or self.isFullScreen()):
                near_left = local_pos.x() < RESIZE_MARGIN
                near_right = local_pos.x() >= rect.width() - RESIZE_MARGIN
                near_top = local_pos.y() < RESIZE_MARGIN
                near_bottom = local_pos.y() >= rect.height() - RESIZE_MARGIN

                if near_top and near_left:
                    return HTTOPLEFT
                if near_top and near_right:
                    return HTTOPRIGHT
                if near_bottom and near_left:
                    return HTBOTTOMLEFT
                if near_bottom and near_right:
                    return HTBOTTOMRIGHT
                if near_left:
                    return HTLEFT
                if near_right:
                    return HTRIGHT
                if near_top:
                    return HTTOP
                if near_bottom:
                    return HTBOTTOM

            if hasattr(self, "title_bar") and self.title_bar.isVisible():
                title_pos = self.title_bar.mapFromGlobal(global_pos)
                if self.title_bar.is_caption_draggable(title_pos):
                    return HTCAPTION

            return HTCLIENT

    def _apply_title_bar_style(self, theme: str) -> None:
        if not hasattr(self, "title_bar"):
            return
        light = (theme == self.settings_page.ui.tr("Light")) if hasattr(self, "settings_page") else False
        if light:
            self.title_bar.apply_style(bg="#f0f0f0", fg="#1a1a1a", hover="rgba(0,0,0,25)")
        else:
            self.title_bar.apply_style(bg="#2b2b2b", fg="#e8e8e8", hover="rgba(255,255,255,30)")

    def apply_theme(self, theme: str):
        if theme == self.settings_page.ui.tr("Light"):
            dayu_theme.set_primary_color(MTheme.blue)
            dayu_theme.set_theme("light")
            is_dark = False
        else:
            dayu_theme.set_primary_color(MTheme.yellow)
            dayu_theme.set_theme("dark")
            is_dark = True

        dayu_theme.apply(self)
        self._apply_title_bar_style(theme)

        if self.startup_home:
            self.startup_home.apply_theme(is_dark)

        self.repaint()
