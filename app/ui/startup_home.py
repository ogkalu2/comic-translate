from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from .dayu_widgets import dayu_theme

if TYPE_CHECKING:
    pass

IMPORT_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".psd",
    ".pdf", ".epub",
    ".zip", ".rar", ".7z", ".tar",
    ".cbz", ".cbr", ".cb7", ".cbt",
    ".ctpr",
}


# "New" card  (big clickable tile like Word's "Blank document")

class _NewCard(QtWidgets.QFrame):
    clicked = QtCore.Signal()

    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(140, 150)
        self.setObjectName("NewCard")

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Preview area
        self._preview = QtWidgets.QLabel(icon_text)
        self._preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._preview.setObjectName("CardPreview")
        self._preview.setFixedHeight(110)
        self._preview.setStyleSheet("font-size: 36px;")

        # Label bar
        self._label = QtWidgets.QLabel(label)
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.setObjectName("CardLabel")
        self._label.setWordWrap(True)
        self._label.setFixedHeight(40)

        lay.addWidget(self._preview)
        lay.addWidget(self._label)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def apply_theme(self, is_dark: bool):
        if is_dark:
            border   = "#484848"
            bg       = "#3a3a3a"
            bg_prev  = "#424242"
            bg_lbl   = "#333333"
            fg_lbl   = "#c0c0c0"
            hover_b  = dayu_theme.primary_color or "#1890ff"
        else:
            border   = "#d0d0d0"
            bg       = "#ffffff"
            bg_prev  = "#f0f0f0"
            bg_lbl   = "#f5f5f5"
            fg_lbl   = "#333333"
            hover_b  = dayu_theme.primary_color or "#1890ff"

        self.setStyleSheet(f"""
            QFrame#NewCard {{
                border: 1px solid {border};
                border-radius: 4px;
                background: {bg};
            }}
            QFrame#NewCard:hover {{
                border: 2px solid {hover_b};
            }}
            QLabel#CardPreview {{
                background: {bg_prev};
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border-bottom: 1px solid {border};
            }}
            QLabel#CardLabel {{
                background: {bg_lbl};
                color: {fg_lbl};
                font-size: 11px;
                font-weight: 500;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)


# Recent project row  

class _RecentRow(QtWidgets.QFrame):
    sig_open   = QtCore.Signal(str)
    sig_remove = QtCore.Signal(str)
    sig_pin    = QtCore.Signal(str, bool)

    def __init__(self, path: str, mtime: float, pinned: bool = False, parent=None):
        super().__init__(parent)
        self._path   = path
        self._pinned = pinned
        self.setObjectName("RecentRow")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(52)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._build(path, mtime)

    def _build(self, path: str, mtime: float):
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 16, 0)
        lay.setSpacing(10)

        # File icon
        icon = QtWidgets.QLabel("📄")
        icon.setFixedSize(36, 36)
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        lay.addWidget(icon)

        # Name + breadcrumb path
        txt_col = QtWidgets.QVBoxLayout()
        txt_col.setSpacing(2)

        name   = os.path.splitext(os.path.basename(path))[0]   # strip .ctpr
        folder = os.path.dirname(path)
        home   = os.path.expanduser("~")
        if folder.startswith(home):
            folder = folder[len(home):].lstrip(os.sep)

        # Build Word-style breadcrumb:  "Desktop › UNB › Fall 2025"
        parts = [p for p in folder.replace("\\", "/").split("/") if p]
        breadcrumb = " › ".join(parts) if parts else folder

        self._name_lbl = QtWidgets.QLabel(name)
        self._name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 500; background: transparent; border: none;"
        )

        self._path_lbl = QtWidgets.QLabel(breadcrumb)
        self._path_lbl.setStyleSheet(
            "font-size: 10px; background: transparent; border: none;"
        )

        txt_col.addWidget(self._name_lbl)
        txt_col.addWidget(self._path_lbl)
        lay.addLayout(txt_col, 1)

        # Date
        date_str = self._fmt_date(mtime)
        self._date_lbl = QtWidgets.QLabel(date_str)
        self._date_lbl.setFixedWidth(120)
        self._date_lbl.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._date_lbl.setStyleSheet(
            "font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(self._date_lbl)

    @staticmethod
    def _fmt_date(mtime: float) -> str:
        try:
            dt  = datetime.fromtimestamp(mtime)
            now = datetime.now()
            if dt.date() == now.date():
                time_fmt = "%#I:%M %p" if sys.platform == "win32" else "%-I:%M %p"
                return "Today, " + dt.strftime(time_fmt)
            diff = (now.date() - dt.date()).days
            if diff == 1:
                return "Yesterday"
            if diff < 7:
                return dt.strftime("%A")          # "Monday"
            return dt.strftime("%-d %B %Y") if sys.platform != "win32" else dt.strftime("%#d %B %Y")
        except Exception:
            return ""

    # styling
    def apply_theme(self, is_dark: bool):
        self._is_dark = is_dark
        if is_dark:
            self._fg       = "#d0d0d0"
            self._fg_sub   = "#777"
            self._date_fg  = "#666"
            self._hover    = "rgba(255,255,255,0.06)"
            self._normal   = "transparent"
            self._accent   = dayu_theme.primary_color or "#1890ff"
        else:
            self._fg       = "#1a1a1a"
            self._fg_sub   = "#666"
            self._date_fg  = "#888"
            self._hover    = "rgba(0,0,0,0.04)"
            self._normal   = "transparent"
            self._accent   = dayu_theme.primary_color or "#1890ff"
        self._set_normal()

    def _set_normal(self):
        self.setStyleSheet(f"""
            QFrame#RecentRow {{
                background: {self._normal};
                border-radius: 4px;
                border: none;
            }}
        """)
        self._name_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {self._fg}; "
            "background: transparent; border: none;"
        )
        self._path_lbl.setStyleSheet(
            f"font-size: 10px; color: {self._fg_sub}; background: transparent; border: none;"
        )
        self._date_lbl.setStyleSheet(
            f"font-size: 11px; color: {self._date_fg}; background: transparent; border: none;"
        )

    def _set_hovered(self):
        self.setStyleSheet(f"""
            QFrame#RecentRow {{
                background: {self._hover};
                border-radius: 4px;
                border: none;
            }}
        """)

    def enterEvent(self, e):
        if hasattr(self, "_hover"):
            self._set_hovered()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if hasattr(self, "_normal"):
            self._set_normal()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self.sig_open.emit(self._path)
        elif e.button() == QtCore.Qt.MouseButton.RightButton:
            self._ctx(e.globalPosition().toPoint())
        super().mousePressEvent(e)

    def _ctx(self, gpos):
        menu = QtWidgets.QMenu(self)
        is_dark = bool(getattr(self, "_is_dark", True))
        if is_dark:
            menu_bg = "#2f2f2f"
            menu_border = "#4a4a4a"
            item_fg = "#dddddd"
            item_hover = "rgba(255,255,255,0.10)"
            sep = "#4a4a4a"
        else:
            menu_bg = "#ffffff"
            menu_border = "#d9d9d9"
            item_fg = "#222222"
            item_hover = "rgba(0,0,0,0.08)"
            sep = "#e5e5e5"

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {menu_bg};
                border: 1px solid {menu_border};
                padding: 4px;
            }}
            QMenu::item {{
                color: {item_fg};
                background-color: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {item_hover};
            }}
            QMenu::separator {{
                height: 1px;
                background: {sep};
                margin: 4px 8px;
            }}
        """)
        menu.addAction(self.tr("Open"), lambda: self.sig_open.emit(self._path))
        menu.addAction(self.tr("Open File Location"), self._open_folder)
        menu.addAction(self.tr("Copy Path"), self._copy_path_to_clipboard)
        menu.addSeparator()
        pin_label = self.tr("Unpin") if self._pinned else self.tr("Pin to list")
        menu.addAction(pin_label, self._toggle_pin)
        menu.addAction(self.tr("Remove from Recent"), lambda: self.sig_remove.emit(self._path))
        menu.addSeparator()
        menu.addAction(self.tr("Delete File"), self._delete_file)
        menu.exec(gpos)

    def _open_folder(self):
        folder = os.path.dirname(self._path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self._path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self._path])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.sig_pin.emit(self._path, self._pinned)

    def _copy_path_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(os.path.normpath(self._path))

    def _delete_file(self):
        normalized_path = os.path.normpath(self._path)
        dialog_parent = self.window() if isinstance(self.window(), QtWidgets.QWidget) else self
        if not os.path.exists(normalized_path):
            QtWidgets.QMessageBox.warning(
                dialog_parent,
                self.tr("File Not Found"),
                self.tr(
                    "The selected project file could not be found.\n"
                    "It may have already been moved, renamed, or deleted.\n\n{path}"
                ).format(path=normalized_path),
            )
            self.sig_remove.emit(self._path)
            return

        msg_box = QtWidgets.QMessageBox(dialog_parent)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(self.tr("Delete File"))
        msg_box.setText(self.tr("Are you sure you want to permanently delete this project file?"))
        msg_box.setInformativeText(normalized_path)
        delete_btn = msg_box.addButton(
            self.tr("Delete"),
            QtWidgets.QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = msg_box.addButton(
            self.tr("Cancel"),
            QtWidgets.QMessageBox.ButtonRole.RejectRole,
        )
        msg_box.setDefaultButton(cancel_btn)
        msg_box.exec()

        if msg_box.clickedButton() is not delete_btn:
            return

        try:
            os.remove(normalized_path)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(
                dialog_parent,
                self.tr("Delete Failed"),
                self.tr("Could not delete the selected project file.\n\n{error}").format(
                    error=str(exc)
                ),
            )
            return

        self.sig_remove.emit(self._path)


# Filter pill button

class _PillButton(QtWidgets.QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def apply_theme(self, is_dark: bool):
        if is_dark:
            normal_bg   = "transparent"
            normal_fg   = "#a0a0a0"
            checked_bg  = "#1890ff"
            checked_fg  = "#ffffff"
            hover_bg    = "rgba(255,255,255,0.08)"
        else:
            normal_bg   = "transparent"
            normal_fg   = "#595959"
            checked_bg  = "#1890ff"
            checked_fg  = "#ffffff"
            hover_bg    = "rgba(0,0,0,0.06)"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {normal_bg};
                color: {normal_fg};
                border: none;
                border-radius: 14px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
            QPushButton:checked {{
                background: {checked_bg};
                color: {checked_fg};
            }}
        """)


# Startup HomeScreen

class StartupHomeScreen(QtWidgets.QWidget):
    sig_open_files   = QtCore.Signal(list)
    sig_open_project = QtCore.Signal(str)
    _sig_remove_one  = QtCore.Signal(str)
    _sig_clear_all   = QtCore.Signal()
    _sig_pin         = QtCore.Signal(str, bool)   # (path, pinned)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._rows: list[_RecentRow] = []
        self._all_entries: list[dict] = []   # full list for filter tab
        self._is_dark = True
        self._filter  = "recent"             # "recent" | "pinned"
        self._search  = ""
        self._build()
        self._refresh_theme()

    # build 
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        root.addWidget(scroll)

        content = QtWidgets.QWidget()
        content.setStyleSheet("background: transparent;")
        vlay = QtWidgets.QVBoxLayout(content)
        vlay.setContentsMargins(52, 40, 52, 40)
        vlay.setSpacing(0)
        scroll.setWidget(content)
        self._vlay = vlay

        # "New" section
        new_hdr = QtWidgets.QLabel(self.tr("New"))
        new_hdr.setStyleSheet(
            "font-size: 15px; font-weight: 600; background: transparent; border: none;"
        )
        vlay.addWidget(new_hdr)
        vlay.addSpacing(10)
        self._new_hdr = new_hdr

        cards_row = QtWidgets.QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.setContentsMargins(0, 0, 0, 0)

        self._card_new  = _NewCard("＋", self.tr("New Project"))
        self._card_open = _NewCard("📂", self.tr("Open Files"))

        self._card_new.clicked.connect(self._on_new_project)
        self._card_open.clicked.connect(self._on_browse)

        cards_row.addWidget(self._card_new)
        cards_row.addWidget(self._card_open)
        cards_row.addStretch()
        vlay.addLayout(cards_row)
        self._drop_hint = QtWidgets.QLabel(
            self.tr("Drag and drop files anywhere on this page to open them.")
        )
        self._drop_hint.setStyleSheet(
            "font-size: 11px; background: transparent; border: none;"
        )
        vlay.addSpacing(8)
        vlay.addWidget(self._drop_hint)
        vlay.addSpacing(16)

        # Divider 
        self._div1 = QtWidgets.QFrame()
        self._div1.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self._div1.setFixedHeight(1)
        vlay.addWidget(self._div1)
        vlay.addSpacing(10)

        # Filter tabs + search
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(4)

        self._btn_recent = _PillButton(self.tr("Recent"))
        self._btn_pinned = _PillButton(self.tr("Pinned"))
        self._btn_recent.setChecked(True)

        self._btn_recent.clicked.connect(lambda: self._set_filter("recent"))
        self._btn_pinned.clicked.connect(lambda: self._set_filter("pinned"))

        for b in (self._btn_recent, self._btn_pinned):
            filter_row.addWidget(b)
        filter_row.addSpacing(12)

        # Search
        self._search_box = QtWidgets.QLineEdit()
        self._search_box.setPlaceholderText(self.tr("Search"))
        self._search_box.setFixedWidth(220)
        self._search_box.setFixedHeight(28)
        self._search_box.textChanged.connect(self._on_search)
        filter_row.addStretch()
        filter_row.addWidget(self._search_box)

        vlay.addLayout(filter_row)
        vlay.addSpacing(16)

        # Column headers
        hdr_row = QtWidgets.QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 16, 0)
        self._col_name = QtWidgets.QLabel(self.tr("Name"))
        self._col_date = QtWidgets.QLabel(self.tr("Date modified"))
        self._col_date.setFixedWidth(120)
        self._col_date.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        hdr_row.addWidget(self._col_name, 1)
        hdr_row.addWidget(self._col_date)
        vlay.addLayout(hdr_row)
        vlay.addSpacing(2)

        # Thin divider under column headers 
        self._div2 = QtWidgets.QFrame()
        self._div2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self._div2.setFixedHeight(1)
        vlay.addWidget(self._div2)
        vlay.addSpacing(2)

        # Rows area
        self._rows_w = QtWidgets.QWidget()
        self._rows_w.setStyleSheet("background: transparent;")
        self._rows_lay = QtWidgets.QVBoxLayout(self._rows_w)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(1)
        vlay.addWidget(self._rows_w)

        # Empty state 
        self._empty = QtWidgets.QLabel(
            self.tr("No recent projects.\nOpen or create a project to get started.")
        )
        self._empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            "font-size: 12px; background: transparent; border: none; padding: 32px;"
        )
        vlay.addWidget(self._empty)
        vlay.addStretch()

    # Public API 

    def populate(self, recent: list[dict]) -> None:
        """Rebuild rows from [{path, mtime}, …] list (newest modified first)."""
        self._all_entries = recent
        self._rebuild_rows()

    def apply_theme(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        self._refresh_theme()

    # Internal 

    def _set_filter(self, mode: str):
        self._filter = mode
        self._btn_recent.setChecked(mode == "recent")
        self._btn_pinned.setChecked(mode == "pinned")
        self._rebuild_rows()

    def _on_search(self, text: str):
        self._search = text.lower().strip()
        self._rebuild_rows()

    def _rebuild_rows(self):
        # Remove existing
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()

        entries = self._all_entries
        if self._filter == "pinned":
            entries = [e for e in entries if e.get("pinned")]
        if self._search:
            entries = [e for e in entries
                       if self._search in os.path.basename(e.get("path", "")).lower()]

        for e in entries:
            path  = e.get("path", "")
            mtime = e.get("mtime", 0.0)
            if not path:
                continue
            row = _RecentRow(path, mtime, pinned=e.get("pinned", False), parent=self._rows_w)
            row.apply_theme(self._is_dark)
            row.sig_open.connect(self.sig_open_project)
            row.sig_remove.connect(self._on_remove)
            row.sig_pin.connect(self._on_pin)
            self._rows_lay.addWidget(row)
            self._rows.append(row)

        has = bool(self._rows)
        self._empty.setVisible(not has)
        self._col_name.setVisible(has)
        self._col_date.setVisible(has)
        self._div2.setVisible(has)

    def _on_remove(self, path: str):
        self._all_entries = [e for e in self._all_entries if e.get("path") != path]
        self._rebuild_rows()
        self._sig_remove_one.emit(path)

    def _on_pin(self, path: str, pinned: bool):
        for e in self._all_entries:
            if e.get("path") == path:
                e["pinned"] = pinned
                break
        self._rebuild_rows()
        self._sig_pin.emit(path, pinned)

    def _on_new_project(self):
        """Emit via sig so controller can clear state & show home."""
        # We emit an empty list — controller interprets as "new blank project"
        self.sig_open_files.emit([])

    def _on_browse(self):
        exts = " ".join(f"*{e}" for e in sorted(IMPORT_EXTS))
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            self.tr("Open Files"),
            os.path.expanduser("~"),
            self.tr(f"Supported Files ({exts});;All Files (*)"),
        )
        if not paths:
            return
        projects = [p for p in paths if p.lower().endswith(".ctpr")]
        images   = [p for p in paths if not p.lower().endswith(".ctpr")]
        if projects:
            self.sig_open_project.emit(projects[0])
        if images:
            self.sig_open_files.emit(images)

    # Theme

    def _refresh_theme(self):
        d = self._is_dark
        if d:
            fg       = "#d9d9d9"
            fg_sub   = "#888"
            hdr_fg   = "#a0a0a0"
            div      = "#3a3a3a"
            sb_bg    = "#3a3a3a"
            sb_fg    = "#d0d0d0"
            sb_ph    = "#666"
            sb_brd   = "#505050"
        else:
            fg       = "#262626"
            fg_sub   = "#666"
            hdr_fg   = "#8c8c8c"
            div      = "#e0e0e0"
            sb_bg    = "#ffffff"
            sb_fg    = "#262626"
            sb_ph    = "#aaa"
            sb_brd   = "#d0d0d0"

        self._new_hdr.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {fg}; "
            "background: transparent; border: none;"
        )
        self._drop_hint.setStyleSheet(
            f"font-size: 11px; color: {fg_sub}; background: transparent; border: none;"
        )
        self._div1.setStyleSheet(f"background: {div}; border: none;")
        self._div2.setStyleSheet(f"background: {div}; border: none;")
        self._col_name.setStyleSheet(
            f"font-size: 10px; color: {hdr_fg}; background: transparent; border: none;"
        )
        self._col_date.setStyleSheet(
            f"font-size: 10px; color: {hdr_fg}; background: transparent; border: none;"
        )
        self._empty.setStyleSheet(
            f"font-size: 12px; color: {fg_sub}; background: transparent; border: none; padding: 32px;"
        )
        self._search_box.setStyleSheet(f"""
            QLineEdit {{
                background: {sb_bg};
                color: {sb_fg};
                border: 1px solid {sb_brd};
                border-radius: 14px;
                padding: 0 12px;
                font-size: 12px;
            }}
            QLineEdit::placeholder {{
                color: {sb_ph};
            }}
        """)

        for b in (self._btn_recent, self._btn_pinned):
            b.apply_theme(d)

        self._card_new.apply_theme(d)
        self._card_open.apply_theme(d)

        for row in self._rows:
            row.apply_theme(d)

    # Drop support on the whole screen 

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            if self._valid_urls(event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        valid    = self._valid_urls(event.mimeData().urls())
        projects = [p for p in valid if p.lower().endswith(".ctpr")]
        images   = [p for p in valid if not p.lower().endswith(".ctpr")]
        if projects:
            self.sig_open_project.emit(projects[0])
        if images:
            self.sig_open_files.emit(images)

    @staticmethod
    def _valid_urls(urls) -> list[str]:
        result = []
        for url in urls:
            local = url.toLocalFile()
            if os.path.isfile(local):
                ext = os.path.splitext(local)[-1].lower()
                if ext in IMPORT_EXTS:
                    result.append(local)
        return result
