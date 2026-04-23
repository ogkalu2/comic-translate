import os

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QSettings
from PySide6.QtGui import QIntValidator

from ...dayu_widgets import dayu_theme
from ...dayu_widgets.browser import MDragFileButton
from ...dayu_widgets.button_group import MPushButtonGroup, MToolButtonGroup
from ...dayu_widgets.check_box import MCheckBox
from ...dayu_widgets.combo_box import MComboBox, MFontComboBox
from ...dayu_widgets.divider import MDivider
from ...dayu_widgets.line_edit import MLineEdit
from ...dayu_widgets.loading import MLoading
from ...dayu_widgets.progress_bar import MProgressBar
from ...dayu_widgets.push_button import MPushButton
from ...dayu_widgets.slider import MSlider
from ...dayu_widgets.text_edit import MTextEdit
from ...dayu_widgets.tool_button import MToolButton
from ...search_replace_panel import SearchReplacePanel
from ..constants import supported_ocr_language_hints, supported_target_languages, user_font_path


class WorkspaceMixin:
    def _create_main_content(self):
        content_widget = QtWidgets.QWidget()

        header_layout = QtWidgets.QHBoxLayout()

        self.undo_tool_group = MToolButtonGroup(orientation=QtCore.Qt.Horizontal, exclusive=True)
        undo_tools = [
            {"svg": "undo.svg", "checkable": False, "tooltip": self.tr("Undo")},
            {"svg": "redo.svg", "checkable": False, "tooltip": self.tr("Redo")},
        ]
        self.undo_tool_group.set_button_list(undo_tools)

        button_config_list = [
            {"text": self.tr("Text"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("Clean"), "dayu_type": MPushButton.DefaultType, "enabled": False},
            {"text": self.tr("Render"), "dayu_type": MPushButton.DefaultType, "enabled": False},
        ]

        self.hbutton_group = MPushButtonGroup()
        self.hbutton_group.set_dayu_size(dayu_theme.small)
        self.hbutton_group.set_button_list(button_config_list)
        self.hbutton_group.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        for button in self.hbutton_group.get_button_group().buttons():
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.progress_bar = MProgressBar().auto_color()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.loading = MLoading().small()
        self.loading.setVisible(False)

        self.webtoon_toggle = MToolButton()
        self.webtoon_toggle.set_dayu_svg("webtoon-toggle.svg")
        self.webtoon_toggle.huge()
        self.webtoon_toggle.setCheckable(True)
        self.webtoon_toggle.setToolTip(
            self.tr("Toggle Webtoon Mode. " "For comics that are read in long vertical strips")
        )
        self.webtoon_toggle.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.translate_button = MPushButton(self.tr("Translate All"))
        self.translate_button.setEnabled(True)
        self.translate_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.multi_translate_button = MPushButton(self.tr("Multi Translate"))
        self.multi_translate_button.setEnabled(True)
        self.multi_translate_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.multi_translate_button.setToolTip(self.tr("Translate all pages to the common target languages"))
        self.cancel_button = MPushButton(self.tr("Cancel"))
        self.cancel_button.setEnabled(True)
        self.cancel_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.batch_report_button = MPushButton(self.tr("Report"))
        self.batch_report_button.setEnabled(False)
        self.batch_report_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.error_pages_button = MPushButton(self.tr("Error Pages"))
        self.error_pages_button.setEnabled(False)
        self.error_pages_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.preview_button = MPushButton(self.tr("Preview"))
        self.preview_button.setEnabled(True)
        self.preview_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.preview_button.setToolTip(self.tr("Open the edited page preview in full screen (F5 / F11)"))
        self.page_position_label = QtWidgets.QLabel(self.tr("Page 0 / 0"))
        self.page_position_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.page_position_label.setStyleSheet("font-weight: 600; padding: 0 8px;")

        header_layout.addWidget(self.hbutton_group)
        header_layout.addWidget(self.loading)
        header_layout.addStretch()
        header_layout.addWidget(self.page_position_label)
        header_layout.addWidget(self.webtoon_toggle)
        header_layout.addWidget(self.preview_button)
        header_layout.addWidget(self.translate_button)
        header_layout.addWidget(self.multi_translate_button)
        header_layout.addWidget(self.cancel_button)
        header_layout.addWidget(self.error_pages_button)
        header_layout.addWidget(self.batch_report_button)

        self.search_panel = SearchReplacePanel(self)
        self.search_panel.setVisible(False)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(MDivider())

        self.image_card_layout = QtWidgets.QVBoxLayout()
        self.image_card_layout.addStretch(1)

        self.page_list.setLayout(self.image_card_layout)
        left_layout.addWidget(self.page_list)
        left_layout.addWidget(self.search_panel)
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)

        self.central_stack = QtWidgets.QStackedWidget()

        self.drag_browser = MDragFileButton(text=self.tr("Click or drag files here"), multiple=True)
        self.drag_browser.set_dayu_svg("attachment_line.svg")
        self.drag_browser.set_dayu_filters(
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
                ".ctpr",
            ]
        )
        self.drag_browser.setToolTip(
            self.tr("Import Images, PDFs, Epubs or Comic Book Archive Files(cbr, cbz, etc)")
        )
        self.central_stack.addWidget(self.drag_browser)

        original_header = QtWidgets.QLabel(self.tr("Original"))
        original_header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        original_header.setStyleSheet("font-weight: 600; padding: 4px;")

        result_header = QtWidgets.QLabel(self.tr("Edited"))
        result_header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        result_header.setStyleSheet("font-weight: 600; padding: 4px;")

        self.original_preview_panel = QtWidgets.QWidget()
        original_layout = QtWidgets.QVBoxLayout(self.original_preview_panel)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(6)
        original_layout.addWidget(original_header)
        original_layout.addWidget(self.original_image_viewer, 1)

        result_panel = QtWidgets.QWidget()
        result_layout = QtWidgets.QVBoxLayout(result_panel)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(6)
        result_layout.addWidget(result_header)
        result_layout.addWidget(self.image_viewer, 1)

        self.compare_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.compare_splitter.setChildrenCollapsible(False)
        self.compare_splitter.addWidget(self.original_preview_panel)
        self.compare_splitter.addWidget(result_panel)
        self.compare_splitter.setStretchFactor(0, 1)
        self.compare_splitter.setStretchFactor(1, 1)
        self.compare_splitter.setSizes([1, 1])

        self.viewer_page = QtWidgets.QWidget()
        viewer_layout = QtWidgets.QVBoxLayout(self.viewer_page)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        viewer_layout.addWidget(self.compare_splitter)

        self.central_stack.addWidget(self.viewer_page)

        central_widget = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central_widget)
        central_layout.addWidget(self.central_stack)
        central_layout.setContentsMargins(10, 10, 10, 10)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(MDivider())

        input_layout = QtWidgets.QHBoxLayout()

        source_text_layout = QtWidgets.QVBoxLayout()
        self.ocr_language_combo = MComboBox().medium()
        self.ocr_language_combo.addItems([self.tr(lang) for lang in supported_ocr_language_hints])
        self.ocr_language_combo.setCurrentText(self.tr("Other Languages"))
        self.ocr_language_combo.setToolTip(self.tr("OCR Language"))
        source_text_layout.addWidget(self.ocr_language_combo)
        self.s_text_edit = MTextEdit()
        self.s_text_edit.setFixedHeight(120)
        source_text_layout.addWidget(self.s_text_edit)
        input_layout.addLayout(source_text_layout)

        t_combo_text_layout = QtWidgets.QVBoxLayout()
        self.t_combo = MComboBox().medium()
        self.t_combo.addItems([self.tr(lang) for lang in supported_target_languages])
        self.t_combo.setToolTip(self.tr("Target Language"))
        t_combo_text_layout.addWidget(self.t_combo)
        self.t_text_edit = MTextEdit()
        self.t_text_edit.setFixedHeight(120)
        t_combo_text_layout.addWidget(self.t_text_edit)
        input_layout.addLayout(t_combo_text_layout)

        text_render_layout = QtWidgets.QVBoxLayout()
        font_settings_layout = QtWidgets.QHBoxLayout()

        self.font_dropdown = MFontComboBox().small()
        self.font_dropdown.setToolTip(self.tr("Font"))
        all_font_files = []
        if os.path.exists(user_font_path):
            all_font_files.extend(
                [
                    os.path.join(user_font_path, f)
                    for f in os.listdir(user_font_path)
                    if f.lower().endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))
                ]
            )

        for font in all_font_files:
            self.add_custom_font(font)

        self.font_size_dropdown = MComboBox().small()
        self.font_size_dropdown.setToolTip(self.tr("Font Size"))
        self.font_size_dropdown.addItems(
            ["4", "6", "8", "9", "10", "11", "12", "14", "16", "18", "20", "22", "24", "28", "32", "36", "48", "72"]
        )
        self.font_size_dropdown.setCurrentText("12")
        self.font_size_dropdown.setFixedWidth(60)
        self.font_size_dropdown.set_editable(True)

        self.line_spacing_dropdown = MComboBox().small()
        self.line_spacing_dropdown.setToolTip(self.tr("Line Spacing"))
        self.line_spacing_dropdown.addItems([
            "0.7", "0.8", "0.9", "1.0", "1.1", "1.2", "1.3", "1.4", "1.5"
        ])
        self.line_spacing_dropdown.setFixedWidth(60)
        self.line_spacing_dropdown.set_editable(True)

        self.bulk_text_action_dropdown = MComboBox().small()
        self.bulk_text_action_dropdown.setToolTip(self.tr("Bulk Text Action"))
        self.bulk_text_action_dropdown.addItem(self.tr("Bulk Text Action"), "noop")
        self.bulk_text_action_dropdown.addItem(self.tr("Apply Font All"), "apply_font_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Restore Font All"), "restore_font_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Upper All"), "upper_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Lower All"), "lower_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Bold All"), "bold_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Bold Off All"), "bold_off_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Italic All"), "italic_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Italic Off All"), "italic_off_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Underline All"), "underline_all")
        self.bulk_text_action_dropdown.addItem(self.tr("Underline Off All"), "underline_off_all")
        self.bulk_text_action_dropdown.setCurrentIndex(0)
        self.bulk_text_action_dropdown.setFixedWidth(180)

        font_settings_layout.addWidget(self.font_dropdown)
        font_settings_layout.addWidget(self.font_size_dropdown)
        font_settings_layout.addWidget(self.line_spacing_dropdown)
        font_settings_layout.addWidget(self.bulk_text_action_dropdown)
        font_settings_layout.addStretch()

        main_text_settings_layout = QtWidgets.QHBoxLayout()

        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("text_rendering")
        dflt_clr = settings.value("color", "#000000")
        dflt_outline_check = settings.value("outline", True, type=bool)
        settings.endGroup()

        self.block_font_color_button = QtWidgets.QPushButton()
        self.block_font_color_button.setToolTip(self.tr("Font Color"))
        self.block_font_color_button.setFixedSize(30, 30)
        self.block_font_color_button.setStyleSheet(f"background-color: {dflt_clr}; border: none; border-radius: 5px;")
        self.block_font_color_button.setProperty("selected_color", dflt_clr)

        self.alignment_tool_group = MToolButtonGroup(orientation=QtCore.Qt.Horizontal, exclusive=True)
        alignment_tools = [
            {"svg": "tabler--align-left.svg", "checkable": True, "tooltip": "Align Left"},
            {"svg": "tabler--align-center.svg", "checkable": True, "tooltip": "Align Center"},
            {"svg": "tabler--align-right.svg", "checkable": True, "tooltip": "Align Right"},
        ]
        self.alignment_tool_group.set_button_list(alignment_tools)
        self.alignment_tool_group.set_dayu_checked(1)

        self.bold_button = self.create_tool_button(svg="bold.svg", checkable=True)
        self.bold_button.setToolTip(self.tr("Bold"))
        self.italic_button = self.create_tool_button(svg="italic.svg", checkable=True)
        self.italic_button.setToolTip(self.tr("Italic"))
        self.underline_button = self.create_tool_button(svg="underline.svg", checkable=True)
        self.underline_button.setToolTip(self.tr("Underline"))

        main_text_settings_layout.addWidget(self.block_font_color_button)
        main_text_settings_layout.addWidget(self.alignment_tool_group)
        main_text_settings_layout.addWidget(self.bold_button)
        main_text_settings_layout.addWidget(self.italic_button)
        main_text_settings_layout.addWidget(self.underline_button)
        main_text_settings_layout.addStretch()

        outline_settings_layout = QtWidgets.QHBoxLayout()

        self.outline_checkbox = MCheckBox(self.tr("Outline"))
        self.outline_checkbox.setChecked(dflt_outline_check)

        self.outline_font_color_button = QtWidgets.QPushButton()
        self.outline_font_color_button.setToolTip(self.tr("Outline Color"))
        self.outline_font_color_button.setFixedSize(30, 30)
        self.outline_font_color_button.setStyleSheet("background-color: white; border: none; border-radius: 5px;")
        self.outline_font_color_button.setProperty("selected_color", "#ffffff")

        self.outline_width_dropdown = MComboBox().small()
        self.outline_width_dropdown.setFixedWidth(60)
        self.outline_width_dropdown.setToolTip(self.tr("Outline Width"))
        self.outline_width_dropdown.addItems(["1.0", "1.15", "1.3", "1.4", "1.5"])
        self.outline_width_dropdown.set_editable(True)

        outline_settings_layout.addWidget(self.outline_checkbox)
        outline_settings_layout.addWidget(self.outline_font_color_button)
        outline_settings_layout.addWidget(self.outline_width_dropdown)
        outline_settings_layout.addStretch()

        effects_settings_layout = QtWidgets.QHBoxLayout()

        self.text_gradient_checkbox = MCheckBox(self.tr("Gradient"))
        self.text_gradient_start_button = QtWidgets.QPushButton()
        self.text_gradient_start_button.setToolTip(self.tr("Text Gradient Top Color"))
        self.text_gradient_start_button.setFixedSize(30, 30)
        self.text_gradient_start_button.setStyleSheet(f"background-color: {dflt_clr}; border: none; border-radius: 5px;")
        self.text_gradient_start_button.setProperty("selected_color", dflt_clr)
        self.text_gradient_end_button = QtWidgets.QPushButton()
        self.text_gradient_end_button.setToolTip(self.tr("Text Gradient Bottom Color"))
        self.text_gradient_end_button.setFixedSize(30, 30)
        self.text_gradient_end_button.setStyleSheet("background-color: #ffffff; border: none; border-radius: 5px;")
        self.text_gradient_end_button.setProperty("selected_color", "#ffffff")

        self.second_outline_checkbox = MCheckBox(self.tr("2nd Outline"))
        self.second_outline_color_button = QtWidgets.QPushButton()
        self.second_outline_color_button.setToolTip(self.tr("Second Outline Color"))
        self.second_outline_color_button.setFixedSize(30, 30)
        self.second_outline_color_button.setStyleSheet("background-color: black; border: none; border-radius: 5px;")
        self.second_outline_color_button.setProperty("selected_color", "#000000")
        self.second_outline_width_dropdown = MComboBox().small()
        self.second_outline_width_dropdown.setFixedWidth(60)
        self.second_outline_width_dropdown.setToolTip(self.tr("Second Outline Width"))
        self.second_outline_width_dropdown.addItems(["1.0", "1.5", "2.0", "2.5", "3.0"])
        self.second_outline_width_dropdown.set_editable(True)

        effects_settings_layout.addWidget(self.text_gradient_checkbox)
        effects_settings_layout.addWidget(self.text_gradient_start_button)
        effects_settings_layout.addWidget(self.text_gradient_end_button)
        effects_settings_layout.addSpacing(8)
        effects_settings_layout.addWidget(self.second_outline_checkbox)
        effects_settings_layout.addWidget(self.second_outline_color_button)
        effects_settings_layout.addWidget(self.second_outline_width_dropdown)
        effects_settings_layout.addStretch()

        rendering_divider_top = MDivider()
        rendering_divider_bottom = MDivider()
        text_render_layout.addWidget(rendering_divider_top)
        text_render_layout.addLayout(font_settings_layout)
        text_render_layout.addLayout(main_text_settings_layout)
        text_render_layout.addLayout(outline_settings_layout)
        text_render_layout.addLayout(effects_settings_layout)
        text_render_layout.addWidget(rendering_divider_bottom)

        tools_widget = QtWidgets.QWidget()
        tools_layout = QtWidgets.QVBoxLayout()

        misc_lay = QtWidgets.QHBoxLayout()

        self.pan_button = self.create_tool_button(svg="pan_tool.svg", checkable=True)
        self.pan_button.setToolTip(self.tr("Pan Image"))
        self.pan_button.clicked.connect(self.toggle_pan_tool)
        self.tool_buttons["pan"] = self.pan_button

        self.select_all_pages_button = MPushButton(self.tr("Select All Pages"))
        self.select_all_pages_button.setToolTip(
            self.tr("Selects every page in the page list for manual batch operations")
        )
        self.select_all_pages_button.setEnabled(False)

        misc_lay.addWidget(self.pan_button)
        misc_lay.addWidget(self.select_all_pages_button)
        misc_lay.addStretch()

        box_tools_lay = QtWidgets.QHBoxLayout()

        self.box_button = self.create_tool_button(svg="select.svg", checkable=True)
        self.box_button.setToolTip(self.tr("Draw or Select Text Boxes"))
        self.box_button.clicked.connect(self.toggle_box_tool)
        self.tool_buttons["box"] = self.box_button

        self.delete_button = self.create_tool_button(svg="trash_line.svg", checkable=False)
        self.delete_button.setToolTip(self.tr("Delete Selected Box"))

        self.clear_rectangles_button = self.create_tool_button(svg="clear-outlined.svg")
        self.clear_rectangles_button.setToolTip(self.tr("Remove all the Boxes on the Image"))

        self.draw_blklist_blks = self.create_tool_button(svg="gridicons--create.svg")
        self.draw_blklist_blks.setToolTip(
            self.tr(
                "Draws all the Text Blocks in the existing Text Block List\n"
                "back on the Image (for further editing)"
            )
        )

        box_tools_lay.addWidget(self.box_button)
        box_tools_lay.addWidget(self.delete_button)
        box_tools_lay.addWidget(self.clear_rectangles_button)
        box_tools_lay.addWidget(self.draw_blklist_blks)

        self.change_all_blocks_size_dec = self.create_tool_button(svg="minus_line.svg")
        self.change_all_blocks_size_dec.setToolTip(self.tr("Reduce the size of all blocks"))

        self.change_all_blocks_size_diff = MLineEdit()
        self.change_all_blocks_size_diff.setFixedWidth(30)
        self.change_all_blocks_size_diff.setText("3")

        int_validator = QIntValidator()
        self.change_all_blocks_size_diff.setValidator(int_validator)
        self.change_all_blocks_size_diff.setAlignment(QtCore.Qt.AlignCenter)

        self.change_all_blocks_size_inc = self.create_tool_button(svg="add_line.svg")
        self.change_all_blocks_size_inc.setToolTip(self.tr("Increase the size of all blocks"))

        box_tools_lay.addStretch()
        box_tools_lay.addWidget(self.change_all_blocks_size_dec)
        box_tools_lay.addWidget(self.change_all_blocks_size_diff)
        box_tools_lay.addWidget(self.change_all_blocks_size_inc)
        box_tools_lay.addStretch()

        inp_tools_lay = QtWidgets.QHBoxLayout()

        self.brush_button = self.create_tool_button(svg="brush-fill.svg", checkable=True)
        self.brush_button.setToolTip(self.tr("Draw Brush Strokes for Cleaning Image"))
        self.brush_button.clicked.connect(self.toggle_brush_tool)
        self.tool_buttons["brush"] = self.brush_button

        self.eraser_button = self.create_tool_button(svg="eraser_fill.svg", checkable=True)
        self.eraser_button.setToolTip(self.tr("Erase Brush Strokes"))
        self.eraser_button.clicked.connect(self.toggle_eraser_tool)
        self.tool_buttons["eraser"] = self.eraser_button

        self.clear_brush_strokes_button = self.create_tool_button(svg="clear-outlined.svg")
        self.clear_brush_strokes_button.setToolTip(self.tr("Remove all the brush strokes on the Image"))

        inp_tools_lay.addWidget(self.brush_button)
        inp_tools_lay.addWidget(self.eraser_button)
        inp_tools_lay.addWidget(self.clear_brush_strokes_button)
        inp_tools_lay.addStretch()

        self.brush_eraser_slider = MSlider()
        self.brush_eraser_slider.setMinimum(1)
        self.brush_eraser_slider.setMaximum(100)
        self.brush_eraser_slider.setValue(10)
        self.brush_eraser_slider.setToolTip(self.tr("Brush/Eraser Size Slider"))
        self.brush_eraser_slider.valueChanged.connect(self.set_brush_eraser_size)

        tools_layout.addLayout(misc_lay)
        box_div = MDivider(self.tr("Box Drawing"))
        tools_layout.addWidget(box_div)
        tools_layout.addLayout(box_tools_lay)

        inp_div = MDivider(self.tr("Inpainting"))
        tools_layout.addWidget(inp_div)
        tools_layout.addLayout(inp_tools_lay)
        tools_layout.addWidget(self.brush_eraser_slider)
        tools_layout.addStretch()
        tools_widget.setLayout(tools_layout)

        tools_scroll = QtWidgets.QScrollArea()
        tools_scroll.setWidgetResizable(True)
        tools_scroll.setWidget(tools_widget)
        tools_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tools_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tools_scroll.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        right_layout.addLayout(input_layout)
        right_layout.addLayout(text_render_layout)
        right_layout.addWidget(tools_scroll, 1)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(central_widget)
        splitter.addWidget(right_widget)

        right_widget.setMinimumWidth(240)

        splitter.setStretchFactor(0, 40)
        splitter.setStretchFactor(1, 80)
        splitter.setStretchFactor(2, 10)

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
