import os
from PySide6 import QtWidgets, QtGui
from PySide6 import QtCore
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase

from .dayu_widgets import dayu_theme
from .dayu_widgets.divider import MDivider
from .dayu_widgets.combo_box import MComboBox
from .dayu_widgets.check_box import MCheckBox
from .dayu_widgets.text_edit import MTextEdit
from .dayu_widgets.line_edit import MLineEdit
from .dayu_widgets.browser import MDragFileButton, MClickBrowserFileToolButton, MClickSaveFileToolButton
from .dayu_widgets.push_button import MPushButton
from .dayu_widgets.tool_button import MToolButton
from .dayu_widgets.radio_button import MRadioButton
from .dayu_widgets.button_group import MPushButtonGroup, MToolButtonGroup
from .dayu_widgets.slider import MSlider
from .dayu_widgets.label import MLabel
from .dayu_widgets.qt import MPixmap
from .dayu_widgets.progress_bar import MProgressBar
from .dayu_widgets.loading import MLoading
from .dayu_widgets.theme import MTheme

from .canvas.image_viewer import ImageViewer
from .settings.settings_page import SettingsPage


supported_source_languages = [
"Korean", "Japanese", "French", "Chinese", "English",
"Russian", "German", "Dutch", "Spanish", "Italian"
]

supported_target_languages = [
"English", "Korean", "Japanese", "French", "Simplified Chinese",
"Traditional Chinese", "Russian", "German", "Dutch", "Spanish", 
"Italian", "Turkish", "Polish", "Portuguese", "Brazilian Portuguese"
]


class ComicTranslateUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super(ComicTranslateUI, self).__init__(parent)
        self.setWindowTitle("Comic Translate")
        
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
        self.main_content_widget = None
        self.tool_buttons = {}  # Dictionary to store mutually exclusive tool names and their corresponding buttons

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
            self.tr("Brazilian Portuguese"): "Brazilian Portuguese"
        }
        # Create reverse mapping
        self.reverse_lang_mapping = {v: k for k, v in self.lang_mapping.items()}

        self.button_to_alignment = {
            0: QtCore.Qt.AlignmentFlag.AlignLeft,
            1: QtCore.Qt.AlignmentFlag.AlignCenter,
            -1: QtCore.Qt.AlignmentFlag.AlignRight,
        }

        self._init_ui()

    def _init_ui(self):
        main_widget = QtWidgets.QWidget(self)
        self.main_layout = QtWidgets.QHBoxLayout()
        main_widget.setLayout(self.main_layout)
        self.setCentralWidget(main_widget)

        # Navigation rail
        nav_rail_layout = self._create_nav_rail()
        self.main_layout.addLayout(nav_rail_layout)
        self.main_layout.addWidget(MDivider(orientation=QtCore.Qt.Vertical))

        # Create main content
        self.main_content_widget = self._create_main_content()
        self.main_layout.addWidget(self.main_content_widget)

    def _create_nav_rail(self):
        nav_rail_layout = QtWidgets.QVBoxLayout()
        nav_divider = MDivider()
        nav_divider.setFixedWidth(30)

        self.tool_browser = MClickBrowserFileToolButton(multiple=True)
        self.tool_browser.set_dayu_svg("upload-file.svg")
        self.tool_browser.set_dayu_filters([".png", ".jpg", ".jpeg", ".webp", ".bmp",
                                            ".zip", ".cbz", ".cbr", ".cb7", ".cbt",
                                            ".pdf", ".epub"])
        self.tool_browser.setToolTip(self.tr("Import Images, PDFs, Epubs or Comic Book Archive Files(cbr, cbz, etc)"))

        self.save_browser = MClickSaveFileToolButton()
        save_file_types = [("Images", ["png", "jpg", "jpeg", "webp", "bmp"])]
        self.save_browser.set_file_types(save_file_types)
        self.save_browser.set_dayu_svg("save.svg")
        self.save_browser.setToolTip(self.tr("Save Currently Loaded Image"))

        save_all_file_types = [
            ("ZIP files", "zip"),
            ("CBZ files", "cbz"),
            ("CB7 files", "cb7"),
            ("PDF files", "pdf"),
            ("EPUB files", "epub"),
        ]

        self.save_all_browser = MClickSaveFileToolButton()
        self.save_all_browser.set_dayu_svg("save-all.svg")
        self.save_all_browser.set_file_types(save_all_file_types)
        self.save_all_browser.setToolTip(self.tr("Save all Images"))

        nav_tool_group = MToolButtonGroup(orientation=QtCore.Qt.Vertical, exclusive=True)
        nav_tools = [
            {"svg": "home_line.svg", "checkable": True, "tooltip": self.tr("Home"), "clicked": self.show_main_page},
            {"svg": "settings.svg", "checkable": True, "tooltip": self.tr("Settings"), "clicked": self.show_settings_page},
        ]
        nav_tool_group.set_button_list(nav_tools)
        nav_tool_group.get_button_group().buttons()[0].setChecked(True)

        nav_rail_layout.addWidget(self.tool_browser)
        nav_rail_layout.addWidget(self.save_browser)
        nav_rail_layout.addWidget(self.save_all_browser)
        nav_rail_layout.addWidget(nav_divider)
        nav_rail_layout.addWidget(nav_tool_group)
        nav_rail_layout.addStretch()

        nav_rail_layout.setContentsMargins(0, 0, 0, 0)

        return nav_rail_layout
    
    def create_push_button(self, text: str, clicked = None):
        button = MPushButton(text)
        button.set_dayu_size(dayu_theme.small)
        button.set_dayu_type(MPushButton.DefaultType)

        if clicked:
            button.clicked.connect(clicked)

        return button

    def _create_main_content(self):

        content_widget = QtWidgets.QWidget()

        header_layout = QtWidgets.QHBoxLayout()

        button_config_list = [
            {"text": self.tr("Detect Text Boxes"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("OCR"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("Get Translations"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("Segment Text"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("Clean Image"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("Rendering"), "dayu_type": MPushButton.DefaultType, "enabled": False},
        ]

        self.hbutton_group = MPushButtonGroup()
        self.hbutton_group.set_dayu_size(dayu_theme.small)
        self.hbutton_group.set_button_list(button_config_list)
        self.hbutton_group.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        # Add progress bar
        self.progress_bar = MProgressBar().auto_color()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.loading = MLoading().small()
        self.loading.setVisible(False)

        self.manual_radio = MRadioButton(self.tr("Manual"))
        self.manual_radio.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    
        self.automatic_radio = MRadioButton(self.tr("Automatic"))
        self.automatic_radio.setChecked(True)
        self.automatic_radio.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.translate_button = MPushButton(self.tr("Translate"))
        self.translate_button.setEnabled(True)
        self.translate_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.cancel_button = MPushButton(self.tr("Cancel"))
        self.cancel_button.setEnabled(True)
        self.cancel_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        header_layout.addWidget(self.hbutton_group)

        header_layout.addWidget(self.loading)
        header_layout.addStretch()
        header_layout.addWidget(self.manual_radio)
        header_layout.addWidget(self.automatic_radio)
        header_layout.addWidget(self.translate_button)
        header_layout.addWidget(self.cancel_button)

        # Left Side (Image Selection)
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(MDivider())
        self.image_card_layout = QtWidgets.QVBoxLayout()
        self.image_card_layout.addStretch(1)  # Add stretch to keep cards at the top
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        img_selection = QtWidgets.QWidget()
        img_selection.setLayout(self.image_card_layout)
        scroll.setWidget(img_selection)
        scroll.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        scroll.setMinimumWidth(60)

        left_layout.addWidget(scroll)
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)

        # Central Widget (File Loader / Image Viewer)
        self.central_stack = QtWidgets.QStackedWidget()
        
        # File Loader
        self.drag_browser = MDragFileButton(text=self.tr("Click or drag files here"), multiple=True)
        self.drag_browser.set_dayu_svg("attachment_line.svg")
        self.drag_browser.set_dayu_filters([".png", ".jpg", ".jpeg", ".webp", ".bmp",
                                            ".zip", ".cbz", ".cbr", ".cb7", ".cbt",
                                            ".pdf", ".epub"])
        self.drag_browser.setToolTip(self.tr("Import Images, PDFs, Epubs or Comic Book Archive Files(cbr, cbz, etc)"))
        self.central_stack.addWidget(self.drag_browser)
        
        # Photo Viewer
        #self.image_viewer.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.central_stack.addWidget(self.image_viewer)
        
        central_widget = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central_widget)
        central_layout.addWidget(self.central_stack)
        central_layout.setContentsMargins(10, 10, 10, 10)  # Add some padding

        # Right Side - Text Input Boxes
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(MDivider())

        input_layout = QtWidgets.QHBoxLayout()
       
        # Source Language
        s_combo_text_layout = QtWidgets.QVBoxLayout()
        self.s_combo = MComboBox().medium()
        self.s_combo.addItems([self.tr(lang) for lang in supported_source_languages])
        self.s_combo.setToolTip(self.tr("Source Language"))
        s_combo_text_layout.addWidget(self.s_combo)
        self.s_text_edit = MTextEdit()
        self.s_text_edit.setFixedHeight(150)
        s_combo_text_layout.addWidget(self.s_text_edit)
        input_layout.addLayout(s_combo_text_layout)

        # Target Language
        t_combo_text_layout = QtWidgets.QVBoxLayout()
        self.t_combo = MComboBox().medium()
        self.t_combo.addItems([self.tr(lang) for lang in supported_target_languages])
        self.t_combo.setToolTip(self.tr("Target Language"))
        t_combo_text_layout.addWidget(self.t_combo)
        self.t_text_edit = MTextEdit()
        self.t_text_edit.setFixedHeight(150)
        t_combo_text_layout.addWidget(self.t_text_edit)

        input_layout.addLayout(t_combo_text_layout)

        # Text Render Settings
        text_render_layout = QtWidgets.QVBoxLayout()
        text_render_layout.addSpacing(20)

        font_settings_layout = QtWidgets.QHBoxLayout()

        self.font_dropdown = MComboBox().small()
        self.font_dropdown.setToolTip(self.tr("Font"))
        font_folder_path = os.path.join(os.getcwd(), "fonts")
        font_files = [os.path.join(font_folder_path, f) for f in os.listdir(font_folder_path)
                       if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
        font_families = [self.get_font_family(f) for f in font_files]
        self.font_dropdown.addItems(font_families)

        self.font_size_dropdown = MComboBox().small()
        self.font_size_dropdown.setToolTip(self.tr("Font Size"))
        self.font_size_dropdown.addItems(['4', '8', '9', '10', '11', '12', '14', '16', '18', 
                                          '20', '22', '24', '28', '32', '36', '48', '72'])
        self.font_size_dropdown.setCurrentText('12')
        self.font_size_dropdown.setFixedWidth(60)
        self.line_spacing_dropdown = MComboBox().small()
        self.line_spacing_dropdown.setToolTip(self.tr("Line Spacing"))
        self.line_spacing_dropdown.addItems(['1.0', '1.1', '1.2', '1.3', '1.4', '1.5'])
        self.line_spacing_dropdown.setFixedWidth(60)

        font_settings_layout.addWidget(self.font_dropdown)
        font_settings_layout.addWidget(self.font_size_dropdown)
        font_settings_layout.addWidget(self.line_spacing_dropdown)
        font_settings_layout.addStretch()

        # Main Text Settings Layout
        main_text_settings_layout = QtWidgets.QHBoxLayout()

        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup('text_rendering')
        dflt_clr = settings.value('color', '#000000')
        dflt_outline_check = settings.value('outline', True, type=bool)
        settings.endGroup()
        
        self.block_font_color_button = QtWidgets.QPushButton()
        self.block_font_color_button.setToolTip(self.tr("Font Color"))
        self.block_font_color_button.setFixedSize(30, 30)

        self.block_font_color_button.setStyleSheet(
            f"background-color: {dflt_clr}; border: none; border-radius: 5px;"
        )
        self.block_font_color_button.setProperty('selected_color', dflt_clr)

        self.alignment_tool_group = MToolButtonGroup(orientation=QtCore.Qt.Horizontal, exclusive=True)
        alignment_tools = [
            {"svg": "tabler--align-left.svg", "checkable": True, "tooltip": "Align Left"},
            {"svg": "tabler--align-center.svg", "checkable": True, "tooltip": "Align Center"},
            {"svg": "tabler--align-right.svg", "checkable": True, "tooltip": "Align Right"},
        ]
        self.alignment_tool_group.set_button_list(alignment_tools)
        self.alignment_tool_group.get_button_group().buttons()[1].setChecked(True)

        self.bold_button = self.create_tool_button(svg = "bold.svg", checkable=True)
        self.bold_button.setToolTip(self.tr("Bold"))
        self.italic_button = self.create_tool_button(svg = "italic.svg", checkable=True)
        self.italic_button.setToolTip(self.tr("Italic"))
        self.underline_button = self.create_tool_button(svg = "underline.svg", checkable=True)
        self.underline_button.setToolTip(self.tr("Underline"))

        main_text_settings_layout.addWidget(self.block_font_color_button)
        main_text_settings_layout.addWidget(self.alignment_tool_group)
        main_text_settings_layout.addWidget(self.bold_button)
        main_text_settings_layout.addWidget(self.italic_button)
        main_text_settings_layout.addWidget(self.underline_button)
        main_text_settings_layout.addStretch()

        # Outline Settings Layout
        outline_settings_layout = QtWidgets.QHBoxLayout()
        
        self.outline_checkbox = MCheckBox(self.tr("Outline"))
        self.outline_checkbox.setChecked(dflt_outline_check)
        
        self.outline_font_color_button = QtWidgets.QPushButton()
        self.outline_font_color_button.setToolTip(self.tr("Outline Color"))
        self.outline_font_color_button.setFixedSize(30, 30)
        self.outline_font_color_button.setStyleSheet(
            "background-color: white; border: none; border-radius: 5px;"
        )
        self.outline_font_color_button.setProperty('selected_color', "#ffffff")

        self.outline_width_dropdown = MComboBox().small()
        self.outline_width_dropdown.setFixedWidth(60)
        self.outline_width_dropdown.setToolTip(self.tr("Outline Width"))
        self.outline_width_dropdown.addItems(['1.0', '1.15', '1.3', '1.4', '1.5'])

        outline_settings_layout.addWidget(self.outline_checkbox)
        outline_settings_layout.addWidget(self.outline_font_color_button)
        outline_settings_layout.addWidget(self.outline_width_dropdown)
        outline_settings_layout.addStretch()

        rendering_divider_top = MDivider(self.tr('Custom font settings for the block'))
        rendering_divider_bottom = MDivider()
        text_render_layout.addWidget(rendering_divider_top)
        text_render_layout.addLayout(font_settings_layout)
        text_render_layout.addLayout(main_text_settings_layout)
        text_render_layout.addLayout(outline_settings_layout)
        text_render_layout.addWidget(rendering_divider_bottom)

        # Tools Layout
        tools_widget = QtWidgets.QWidget() 
        tools_layout = QtWidgets.QVBoxLayout()

        misc_lay = QtWidgets.QHBoxLayout()

        # Pan Button
        self.pan_button = self.create_tool_button(svg = "pan_tool.svg", checkable = True)
        self.pan_button.setToolTip("Pan Image")
        self.pan_button.clicked.connect(self.toggle_pan_tool)
        self.tool_buttons['pan'] = self.pan_button

        # Set Source/Target Button
        self.set_all_button = MPushButton(self.tr("Set for all"))
        self.set_all_button.setToolTip(self.tr("Sets the Source and Target Language on the current page for all pages"))

        misc_lay.addWidget(self.pan_button)
        misc_lay.addWidget(self.set_all_button)
        misc_lay.addStretch()

        # For Drawing Text Boxes
        box_tools_lay = QtWidgets.QHBoxLayout()

        self.box_button = self.create_tool_button(svg = "select.svg", checkable=True)
        self.box_button.setToolTip("Draw or Select Text Boxes")
        self.box_button.clicked.connect(self.toggle_box_tool)
        self.tool_buttons['box'] = self.box_button

        self.delete_button = self.create_tool_button(svg = "trash_line.svg", checkable=False)
        self.delete_button.setToolTip("Delete Selected Box")

        self.clear_rectangles_button = self.create_tool_button(svg = "clear-outlined.svg")
        self.clear_rectangles_button.setToolTip(self.tr("Remove all the Boxes on the Image"))

        self.draw_blklist_blks = self.create_tool_button(svg = "gridicons--create.svg")
        self.draw_blklist_blks.setToolTip(self.tr("Draws all the Text Blocks in the existing Text Block List\n"
                                                "back on the Image (for further editing)"))

        box_tools_lay.addWidget(self.box_button)
        box_tools_lay.addWidget(self.delete_button)
        box_tools_lay.addWidget(self.clear_rectangles_button)
        box_tools_lay.addWidget(self.draw_blklist_blks)

        self.change_all_blocks_size_dec = self.create_tool_button(svg="minus_line.svg")
        self.change_all_blocks_size_dec.setToolTip(self.tr("Reduce the size of all blocks"))
        
        self.change_all_blocks_size_diff = MLineEdit()
        self.change_all_blocks_size_diff.setFixedWidth(30)
        self.change_all_blocks_size_diff.setText("3")
        
        # Set up integer validator
        int_validator = QIntValidator()
        self.change_all_blocks_size_diff.setValidator(int_validator)
        
        # Optional: Ensure the text is center-aligned
        self.change_all_blocks_size_diff.setAlignment(QtCore.Qt.AlignCenter)
        
        self.change_all_blocks_size_inc = self.create_tool_button(svg="add_line.svg")
        self.change_all_blocks_size_inc.setToolTip(self.tr("Increase the size of all blocks"))
        
        box_tools_lay.addStretch()
        box_tools_lay.addWidget(self.change_all_blocks_size_dec)
        box_tools_lay.addWidget(self.change_all_blocks_size_diff)
        box_tools_lay.addWidget(self.change_all_blocks_size_inc)
        box_tools_lay.addStretch()

        # Inpainting Tools
        inp_tools_lay = QtWidgets.QHBoxLayout()

        self.brush_button = self.create_tool_button(svg = "brush-fill.svg", checkable=True)
        self.brush_button.setToolTip(self.tr("Draw Brush Strokes for Cleaning Image"))
        self.brush_button.clicked.connect(self.toggle_brush_tool)
        self.tool_buttons['brush'] = self.brush_button

        self.eraser_button = self.create_tool_button(svg = "eraser_fill.svg", checkable=True)
        self.eraser_button.setToolTip(self.tr("Erase Brush Strokes"))
        self.eraser_button.clicked.connect(self.toggle_eraser_tool)
        self.tool_buttons['eraser'] = self.eraser_button

        self.chk_inp_tool_group = MToolButtonGroup(orientation=QtCore.Qt.Horizontal, exclusive=True)
        chk_inp_tools = [
            {"svg": "undo.svg", "checkable": False, "tooltip": self.tr("Undo Brush Stroke"), "clicked": self.brush_undo},
            {"svg": "redo.svg", "checkable": False, "tooltip": self.tr("Redo Brush Stroke"), "clicked": self.brush_redo},
        ]
        self.chk_inp_tool_group.set_button_list(chk_inp_tools)

        self.clear_brush_strokes_button = self.create_tool_button(svg = "clear-outlined.svg")
        self.clear_brush_strokes_button.setToolTip(self.tr("Remove all the brush strokes on the Image"))

        inp_tools_lay.addWidget(self.brush_button)
        inp_tools_lay.addWidget(self.eraser_button)
        inp_tools_lay.addWidget(self.chk_inp_tool_group)
        inp_tools_lay.addWidget(self.clear_brush_strokes_button)
        inp_tools_lay.addStretch()

        self.brush_size_slider = MSlider()
        self.eraser_size_slider = MSlider()

        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(50)
        self.brush_size_slider.setValue(10)
        self.brush_size_slider.valueChanged.connect(self.set_brush_size)

        self.eraser_size_slider.setMinimum(1)
        self.eraser_size_slider.setMaximum(50)
        self.eraser_size_slider.setValue(20)
        self.eraser_size_slider.valueChanged.connect(self.set_eraser_size)
        b_slider_label = MLabel(self.tr("Brush Size Slider"))
        e_slider_label = MLabel(self.tr("Eraser Size Slider"))

        # For returning an Image
        return_buttons_lay = QtWidgets.QHBoxLayout()
        self.return_buttons_group = MToolButtonGroup(orientation=QtCore.Qt.Horizontal, exclusive=False)
        return_buttons = [
            {"text": self.tr("Undo Image"), "svg": "arrow-left.svg", "checkable": False, "tooltip": self.tr("Undo Image")},
            {"text": self.tr("Redo Image"), "svg": "arrow-right.svg", "checkable": False, "tooltip": self.tr("Redo Image")},
        ]

        self.return_buttons_group.set_button_list(return_buttons)
        return_buttons_lay.addWidget(self.return_buttons_group)


        tools_layout.addLayout(misc_lay)
        box_div = MDivider(self.tr('Box Drawing'))
        tools_layout.addWidget(box_div)
        tools_layout.addLayout(box_tools_lay)

        inp_div = MDivider(self.tr('Inpainting'))
        tools_layout.addWidget(inp_div)
        tools_layout.addLayout(inp_tools_lay)
        tools_layout.addWidget(b_slider_label)
        tools_layout.addWidget(self.brush_size_slider)
        tools_layout.addWidget(e_slider_label)
        tools_layout.addWidget(self.eraser_size_slider)
        tools_layout.addLayout(return_buttons_lay)
        tools_widget.setLayout(tools_layout)

        tools_scroll = QtWidgets.QScrollArea()
        tools_scroll.setWidgetResizable(True)
        tools_scroll.setWidget(tools_widget)
        tools_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tools_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tools_scroll.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        #tools_scroll.setMinimumHeight(300)

        right_layout.addLayout(input_layout)
        right_layout.addLayout(text_render_layout)
        right_layout.addWidget(tools_scroll)
        right_layout.addStretch()

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(central_widget)
        splitter.addWidget(right_widget)

        right_widget.setMinimumWidth(240)  # Adjust this value as needed

        splitter.setStretchFactor(0, 40)  # Left widget
        splitter.setStretchFactor(1, 80)  # Central widget
        splitter.setStretchFactor(2, 10)  # Right widget

        content_layout = QtWidgets.QVBoxLayout()
        content_layout.addLayout(header_layout)
        content_layout.addWidget(self.progress_bar)
        content_layout.addWidget(splitter)

        content_layout.setStretchFactor(header_layout, 0)
        content_layout.setStretchFactor(splitter, 1)

        content_widget.setLayout(content_layout)

        return content_widget

    def create_tool_button(self, text: str = "", svg: str = "", checkable: bool = False):
        if text:
            button = MToolButton().svg(svg).text_beside_icon()
            button.setText(text)
        else:
            button = MToolButton().svg(svg)

        button.setCheckable(True) if checkable else button.setCheckable(False)

        return button

    def show_settings_page(self):
        if not self.settings_page:
            self.settings_page = SettingsPage(self)
        
        # Remove the main content widget
        self.main_layout.removeWidget(self.main_content_widget)
        self.main_content_widget.hide()
        
        # Add the settings page
        self.main_layout.addWidget(self.settings_page)
        self.settings_page.show()

    def show_main_page(self):
        if self.settings_page:
            # Remove the settings page
            self.main_layout.removeWidget(self.settings_page)
            self.settings_page.hide()
        
        # Add back the main content widget
        self.main_layout.addWidget(self.main_content_widget)
        self.main_content_widget.show()

    def apply_theme(self, theme: str):
        if theme == self.settings_page.ui.tr("Light"):
            new_theme = MTheme("light", primary_color=MTheme.blue)
        else:
            new_theme = MTheme("dark", primary_color=MTheme.yellow)
        
        new_theme.apply(self)

        # Refresh the UI to apply the new theme
        self.repaint()

    def toggle_pan_tool(self):
        if self.pan_button.isChecked():
            self.set_tool('pan')
        else:
            self.set_tool(None)

    def toggle_box_tool(self):
        if self.box_button.isChecked():
            self.set_tool('box')
        else:
            self.set_tool(None)

    def toggle_brush_tool(self):
        if self.brush_button.isChecked():
            self.set_tool('brush')
        else:
            self.set_tool(None)

    def toggle_eraser_tool(self):
        if self.eraser_button.isChecked():
            self.set_tool('eraser')
        else:
            self.set_tool(None)

    def set_tool(self, tool_name: str):
        self.image_viewer.unsetCursor()
        self.image_viewer.set_tool(tool_name)

        for name, button in self.tool_buttons.items():
            if name != tool_name:
                button.setChecked(False)
            elif tool_name is not None:
                button.setChecked(True)

        # If tool_name is None, uncheck all buttons
        if not tool_name:
            for button in self.tool_buttons.values():
                button.setChecked(False)

    def set_brush_size(self, size: int):
        if self.image_viewer.hasPhoto():
            image = self.image_viewer.get_cv2_image()
            h, w, c = image.shape
            scaled_size = self.scale_size(size, w, h)
            self.image_viewer.set_brush_size(scaled_size)

    def set_eraser_size(self, size: int):
        if self.image_viewer.hasPhoto():
            image = self.image_viewer.get_cv2_image()
            h, w, c = image.shape
            scaled_size = self.scale_size(size, w, h)
            self.image_viewer.set_eraser_size(scaled_size)

    def scale_size(self, base_size, image_width, image_height):
        # Calculate the diagonal of the image
        image_diagonal = (image_width**2 + image_height**2)**0.5
        
        # Use a reference diagonal (e.g., 1000 pixels) to calculate scaling factor
        reference_diagonal = 1000
        scaling_factor = image_diagonal / reference_diagonal
        
        # Scale the diameter and pen width
        scaled_size = base_size * scaling_factor
        
        return scaled_size

    def brush_undo(self):
        self.image_viewer.undo_brush_stroke()

    def brush_redo(self):
        self.image_viewer.redo_brush_stroke()

    def get_font_family(self, font_input: str) -> QFont:
        # Check if font_input is a file path
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            font_id = QFontDatabase.addApplicationFont(font_input)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        
        # If not a file path or loading failed, treat as font family name
        return font_input
    
    def get_color(self):
        default_color = QtGui.QColor('#000000')
        color_dialog = QtWidgets.QColorDialog()
        color_dialog.setCurrentColor(default_color)
        if color_dialog.exec() == QtWidgets.QDialog.Accepted:
            color = color_dialog.selectedColor()
            return color
        

