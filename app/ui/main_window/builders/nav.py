from PySide6 import QtCore, QtWidgets

from ...dayu_widgets import dayu_theme
from ...dayu_widgets.browser import (
    MClickBrowserFileToolButton,
    MClickBrowserFolderToolButton,
    MClickSaveFileToolButton,
)
from ...dayu_widgets.button_group import MToolButtonGroup
from ...dayu_widgets.divider import MDivider
from ...dayu_widgets.menu import MMenu
from ...dayu_widgets.push_button import MPushButton
from ...dayu_widgets.qt import MIcon
from ...dayu_widgets.tool_button import MToolButton


class NavRailMixin:
    def _create_nav_rail(self):
        nav_rail_layout = QtWidgets.QVBoxLayout()
        nav_divider = MDivider()
        nav_divider.setFixedWidth(30)

        self.new_project_button = MToolButton()
        self.new_project_button.set_dayu_svg("file.svg")
        self.new_project_button.setToolTip(self.tr("New Project"))

        self.tool_browser = MToolButton()
        self.tool_browser.set_dayu_svg("folder-open.svg")
        self.tool_browser.setToolTip(
            self.tr(
                "Import Images, PDFs, Epubs or Comic Book Archive Files (cbr, cbz, etc). "
                "This will Open a new project"
            )
        )
        self.tool_browser.clicked.connect(self.show_tool_menu)

        self.image_browser_button = MClickBrowserFileToolButton(multiple=True)
        self.image_browser_button.set_dayu_filters([".png", ".jpg", ".jpeg", ".webp", ".bmp"])

        self.psd_browser_button = MClickBrowserFileToolButton(multiple=True)
        self.psd_browser_button.set_dayu_filters([".psd"])

        self.document_browser_button = MClickBrowserFileToolButton(multiple=True)
        self.document_browser_button.set_dayu_filters([".pdf", ".epub"])

        self.archive_browser_button = MClickBrowserFileToolButton(multiple=True)
        self.archive_browser_button.set_dayu_filters([".zip", ".rar", ".7z", ".tar"])

        self.comic_browser_button = MClickBrowserFileToolButton(multiple=True)
        self.comic_browser_button.set_dayu_filters([".cbz", ".cbr", ".cb7", ".cbt"])

        self.project_browser_button = MClickBrowserFileToolButton(multiple=False)
        self.project_browser_button.set_dayu_filters([".ctpr"])

        self.tool_menu = MMenu(parent=self)

        image_action = self.tool_menu.addAction(MIcon("ion--image-outline.svg"), self.tr("Images"))
        image_action.triggered.connect(self.image_browser_button.clicked)

        psd_action = self.tool_menu.addAction(MIcon("psd-file.svg"), self.tr("PSD"))
        psd_action.triggered.connect(self.psd_browser_button.clicked)

        document_action = self.tool_menu.addAction(MIcon("mingcute--document-line.svg"), self.tr("Document"))
        document_action.triggered.connect(self.document_browser_button.clicked)

        archive_action = self.tool_menu.addAction(MIcon("flowbite--file-zip-outline.svg"), self.tr("Archive"))
        archive_action.triggered.connect(self.archive_browser_button.clicked)

        comic_action = self.tool_menu.addAction(
            MIcon("mdi--comic-thought-bubble-outline.svg"), self.tr("Comic Book Archive")
        )
        comic_action.triggered.connect(self.comic_browser_button.clicked)

        project_action = self.tool_menu.addAction(MIcon("ct-file-icon.svg"), self.tr("Project File"))
        project_action.triggered.connect(self.project_browser_button.clicked)

        self.save_browser = MClickSaveFileToolButton()
        save_file_types = [("Images", ["png", "jpg", "jpeg", "webp", "bmp"])]
        self.save_browser.set_file_types(save_file_types)
        self.save_browser.set_dayu_svg("save.svg")
        self.save_browser.setToolTip(self.tr("Save Currently Loaded Image"))

        self.save_project_button = MToolButton()
        self.save_project_button.set_dayu_svg("fluent--save-16-regular.svg")
        self.save_project_button.setToolTip(self.tr("Save Project"))

        self.save_as_project_button = MToolButton()
        self.save_as_project_button.set_dayu_svg("fluent--save-as-24-regular.svg")
        self.save_as_project_button.setToolTip(self.tr("Save as"))

        save_all_file_types = [
            ("ZIP files", "zip"),
            ("CBZ files", "cbz"),
            ("CB7 files", "cb7"),
            ("PDF files", "pdf"),
        ]

        self.save_all_button = MToolButton()
        self.save_all_button.set_dayu_svg("tabler--file-export.svg")
        self.save_all_button.setToolTip(self.tr("Export all Images"))
        self.save_all_button.clicked.connect(self.show_export_menu)

        self.save_all_browser = MClickSaveFileToolButton()
        self.save_all_browser.set_file_types(save_all_file_types)
        self.export_psd_folder_browser = MClickBrowserFolderToolButton(multiple=False)

        self.export_menu = MMenu(parent=self)
        self.export_menu.setMinimumWidth(80)
        export_archive_action = self.export_menu.addAction(
            MIcon("flowbite--file-zip-outline.svg"),
            self.tr("ZIP"),
        )
        export_archive_action.triggered.connect(lambda: self._export_all_as("zip"))

        export_comic_action = self.export_menu.addAction(
            MIcon("mdi--comic-thought-bubble-outline.svg"),
            self.tr("CBZ"),
        )
        export_comic_action.triggered.connect(lambda: self._export_all_as("cbz"))

        export_document_action = self.export_menu.addAction(
            MIcon("mingcute--document-line.svg"),
            self.tr("PDF"),
        )
        export_document_action.triggered.connect(lambda: self._export_all_as("pdf"))

        export_psd_action = self.export_menu.addAction(
            MIcon("psd-file.svg"),
            self.tr("PSD"),
        )
        export_psd_action.triggered.connect(self._on_export_psd_requested)

        nav_tool_group = MToolButtonGroup(orientation=QtCore.Qt.Vertical, exclusive=True)
        nav_tools = [
            {
                "svg": "startup_line.svg",
                "checkable": True,
                "tooltip": self.tr("Start"),
                "clicked": self.show_home_screen,
            },
            {
                "svg": "home_line.svg",
                "checkable": True,
                "tooltip": self.tr("Home"),
                "clicked": self.show_main_page,
            },
            {
                "svg": "settings.svg",
                "checkable": True,
                "tooltip": self.tr("Settings"),
                "clicked": self.show_settings_page,
            },
        ]
        nav_tool_group.set_button_list(nav_tools)
        nav_buttons = nav_tool_group.get_button_group().buttons()
        self.nav_tool_group = nav_tool_group
        self.startup_nav_button = nav_buttons[0]
        self.home_nav_button = nav_buttons[1]
        self.settings_nav_button = nav_buttons[2]
        self.startup_nav_button.setChecked(True)

        self.search_sidebar_button = MToolButton()
        self.search_sidebar_button.set_dayu_svg("search_line.svg")
        self.search_sidebar_button.setToolTip(self.tr("Search / Replace (Ctrl+F)"))
        self.search_sidebar_button.setCheckable(True)
        self.search_sidebar_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.search_sidebar_button.toggled.connect(self._set_search_sidebar_visible)

        self.insert_button = MToolButton()
        self.insert_button.set_dayu_svg("file-plus.svg")
        self.insert_button.setToolTip(self.tr("Insert files into current project"))
        self.insert_browser_button = MClickBrowserFileToolButton(multiple=True)
        self.insert_browser_button.set_dayu_filters(
            [
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".bmp",
                ".zip",
                ".cbz",
                ".cbr",
                ".cb7",
                ".cbt",
                ".pdf",
                ".epub",
            ]
        )
        self.insert_button.clicked.connect(self.insert_browser_button.clicked)

        nav_rail_layout.addWidget(self.new_project_button)
        nav_rail_layout.addWidget(self.tool_browser)
        nav_rail_layout.addWidget(self.insert_button)
        nav_rail_layout.addWidget(self.save_project_button)
        nav_rail_layout.addWidget(self.save_as_project_button)
        nav_rail_layout.addWidget(self.save_browser)
        nav_rail_layout.addWidget(self.save_all_button)
        nav_rail_layout.addWidget(nav_divider)
        nav_rail_layout.addWidget(self.search_sidebar_button)
        nav_rail_layout.addWidget(nav_tool_group)
        nav_rail_layout.addStretch()
        nav_rail_layout.setContentsMargins(0, 0, 0, 0)

        return nav_rail_layout

    def _set_search_sidebar_visible(self, visible: bool):
        if not hasattr(self, "search_panel") or not hasattr(self, "page_list"):
            return
        try:
            self.search_panel.setVisible(bool(visible))
            self.page_list.setVisible(not bool(visible))
        except Exception:
            return

        if visible:
            try:
                self.search_panel.find_input.setFocus()
                self.search_panel.find_input.selectAll()
            except Exception:
                pass

    def show_search_sidebar(self, focus: str = "find"):
        btn = getattr(self, "search_sidebar_button", None)
        if btn is not None:
            try:
                with QtCore.QSignalBlocker(btn):
                    btn.setChecked(True)
            except Exception:
                btn.setChecked(True)
        self._set_search_sidebar_visible(True)
        if focus == "replace":
            try:
                self.search_panel.replace_input.setFocus()
                self.search_panel.replace_input.selectAll()
            except Exception:
                pass

    def hide_search_sidebar(self):
        btn = getattr(self, "search_sidebar_button", None)
        if btn is not None:
            try:
                with QtCore.QSignalBlocker(btn):
                    btn.setChecked(False)
            except Exception:
                btn.setChecked(False)
        self._set_search_sidebar_visible(False)

    def _confirm_start_new_project(self) -> bool:
        try:
            if hasattr(self, "text_ctrl"):
                self.text_ctrl._commit_pending_text_command()
            if hasattr(self, "has_unsaved_changes"):
                has_unsaved = bool(self.has_unsaved_changes())
            else:
                has_unsaved = (getattr(self, "project_file", None) is None) and bool(getattr(self, "image_files", []))
        except Exception:
            has_unsaved = False

        if has_unsaved:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Question)
            msg_box.setWindowTitle(self.tr("Start New Project"))
            msg_box.setText(self.tr("Your current project has unsaved changes. Start a new project?"))
            yes_btn = msg_box.addButton(self.tr("Yes"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            no_btn = msg_box.addButton(self.tr("No"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(no_btn)
            msg_box.exec()
            return msg_box.clickedButton() == yes_btn
        return True

    def show_tool_menu(self):
        if not self._confirm_start_new_project():
            return
        self.tool_menu.exec_(self.tool_browser.mapToGlobal(self.tool_browser.rect().bottomLeft()))

    def show_export_menu(self):
        self.export_menu.exec_(self.save_all_button.mapToGlobal(self.save_all_button.rect().bottomLeft()))

    def _export_all_as(self, extension: str):
        extension = (extension or "").lower().lstrip(".")
        project_ctrl = getattr(self, "project_ctrl", None)
        if project_ctrl is None or not hasattr(project_ctrl, "start_export_as"):
            return
        project_ctrl.start_export_as(extension)

    def _on_export_psd_requested(self):
        project_ctrl = getattr(self, "project_ctrl", None)
        if project_ctrl is not None and hasattr(project_ctrl, "export_to_psd_dialog"):
            project_ctrl.export_to_psd_dialog()
            return
        self.export_psd_folder_browser.click()

    def create_push_button(self, text: str, clicked=None):
        button = MPushButton(text)
        button.set_dayu_size(dayu_theme.small)
        button.set_dayu_type(MPushButton.DefaultType)

        if clicked:
            button.clicked.connect(clicked)

        return button
