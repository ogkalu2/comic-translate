import os
from typing import List
from PySide6 import QtWidgets
from PySide6 import QtCore
from PySide6.QtGui import QFontMetrics

from ..dayu_widgets.label import MLabel
from ..dayu_widgets.line_edit import MLineEdit
from ..dayu_widgets.text_edit import MTextEdit
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.clickable_card import ClickMeta
from ..dayu_widgets.divider import MDivider
from ..dayu_widgets.qt import MPixmap
from ..dayu_widgets.combo_box import MComboBox
from ..dayu_widgets.spin_box import MSpinBox
from ..dayu_widgets.browser import MClickBrowserFileToolButton


class SettingsPageUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SettingsPageUI, self).__init__(parent)

        self.credential_widgets = {}
        self.llm_widgets = {}
        self.export_widgets = {}
        self.text_rendering_widgets = {}  

        self.inpainters = ['LaMa']
        self.ocr_engines = [self.tr("Default"), self.tr("Microsoft OCR"), self.tr("Google Cloud Vision")]
        self.inpaint_strategy = [self.tr('Resize'), self.tr('Original'), self.tr('Crop')]
        self.themes = [self.tr('Dark'), self.tr('Light')]
        self.alignment = [self.tr("Left"), self.tr("Center"), self.tr("Right")]

        self.credential_services = [self.tr("Open AI GPT"), self.tr("Microsoft Azure"), self.tr("Google Cloud"), 
                                    self.tr("Google Gemini"), self.tr("DeepL"), self.tr("Anthropic Claude"), self.tr("Yandex")]
        
        self.supported_translators = [self.tr("GPT-4o"), self.tr("GPT-4o mini"), self.tr("DeepL"), 
                                    self.tr("Claude-3-Opus"), self.tr("Claude-3.5-Sonnet"), 
                                    self.tr("Claude-3-Haiku"), self.tr("Gemini-1.5-Flash"), 
                                    self.tr("Gemini-1.5-Pro"), self.tr("Yandex"), self.tr("Google Translate"),
                                    self.tr("Microsoft Translator")]
        
        self.languages = ['English', '한국어', 'Français', '日本語', 
         '简体中文', '繁體中文', 'русский', 'Deutsch', 
         'Nederlands', 'Español', 'Italiano', 'Türkçe']
        
        self.nav_cards = []  
        self.current_highlighted_nav = None

        self.value_mappings = {
            # Language mappings
            "English": "English",
            "한국어": "한국어",
            "Français": "Français",
            "日本語": "日本語",
            "简体中文": "简体中文",
            "繁體中文": "繁體中文",
            "русский": "русский",
            "Deutsch": "Deutsch",
            "Nederlands": "Nederlands",
            "Español": "Español",
            "Italiano": "Italiano",
            "Türkçe": "Türkçe",

            # Theme mappings
            self.tr("Dark"): "Dark",
            self.tr("Light"): "Light",

            # Translator mappings
            self.tr("GPT-4o"): "GPT-4o",
            self.tr("GPT-4o mini"): "GPT-4o mini",
            self.tr("DeepL"): "DeepL",
            self.tr("Claude-3-Opus"): "Claude-3-Opus",
            self.tr("Claude-3.5-Sonnet"): "Claude-3.5-Sonnet",
            self.tr("Claude-3-Haiku"): "Claude-3-Haiku",
            self.tr("Gemini-1.5-Flash"): "Gemini-1.5-Flash",
            self.tr("Gemini-1.5-Pro"): "Gemini-1.5-Pro",
            self.tr("Yandex"): "Yandex",
            self.tr("Google Translate"): "Google Translate",
            self.tr("Microsoft Translator"): "Microsoft Translator",

            # OCR mappings
            self.tr("Default"): "Default",
            self.tr("Microsoft OCR"): "Microsoft OCR",
            self.tr("Google Cloud Vision"): "Google Cloud Vision",

            # Inpainter mappings
            "LaMa": "LaMa",

            # HD Strategy mappings
            self.tr("Resize"): "Resize",
            self.tr("Original"): "Original",
            self.tr("Crop"): "Crop",

            # Alignment mappings
            self.tr("Left"): "Left",
            self.tr("Center"): "Center",
            self.tr("Right"): "Right",

            # Credential services mappings
            self.tr("Open AI GPT"): "Open AI GPT",
            self.tr("Microsoft Azure"): "Microsoft Azure",
            self.tr("Google Cloud"): "Google Cloud",
            self.tr("Google Gemini"): "Google Gemini",
            self.tr("DeepL"): "DeepL",
            self.tr("Anthropic Claude"): "Anthropic Claude",
            self.tr("Yandex"): "Yandex",
        }

        # Create reverse mappings for loading
        self.reverse_mappings = {v: k for k, v in self.value_mappings.items()}

        self._init_ui()

    def _init_ui(self):
        self.stacked_widget = QtWidgets.QStackedWidget()

        navbar_layout = self._create_navbar()
        personalization_layout = self._create_personalization_layout()
        tools_layout = self._create_tools_layout()
        credentials_layout = self._create_credentials_layout()
        llms_layout = self._create_llms_layout()
        text_rendering_layout = self._create_text_rendering_layout()
        export_layout = self._create_export_layout()

        personalization_widget = QtWidgets.QWidget()
        personalization_widget.setLayout(personalization_layout)
        self.stacked_widget.addWidget(personalization_widget)

        tools_widget = QtWidgets.QWidget()
        tools_widget.setLayout(tools_layout)
        self.stacked_widget.addWidget(tools_widget)

        credentials_widget = QtWidgets.QWidget()
        credentials_widget.setLayout(credentials_layout)
        self.stacked_widget.addWidget(credentials_widget)

        llms_widget = QtWidgets.QWidget()
        llms_widget.setLayout(llms_layout)
        self.stacked_widget.addWidget(llms_widget)

        text_rendering_widget = QtWidgets.QWidget()
        text_rendering_widget.setLayout(text_rendering_layout)
        self.stacked_widget.addWidget(text_rendering_widget)

        export_widget = QtWidgets.QWidget()
        export_widget.setLayout(export_layout)
        self.stacked_widget.addWidget(export_widget)

        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.addLayout(navbar_layout)
        settings_layout.addWidget(MDivider(orientation=QtCore.Qt.Orientation.Vertical))
        settings_layout.addWidget(self.stacked_widget, 1)
        settings_layout.setContentsMargins(3, 3, 3, 3)

        self.setLayout(settings_layout)

    def _create_title_and_combo(self, title: str, options: List[str]):
        combo_widget = QtWidgets.QWidget()
        combo_layout = QtWidgets.QVBoxLayout()

        if title in [self.tr("Inpainter"), self.tr("HD Strategy")]:
            label = MLabel(title)
        else:
            label = MLabel(title).h4()
        combo = MComboBox().small()
        combo.addItems(options)

        combo_layout.addWidget(label)
        combo_layout.addWidget(combo)

        combo_widget.setLayout(combo_layout)

        return combo_widget, combo
    
    def _create_navbar(self):
        navbar_layout = QtWidgets.QVBoxLayout()

        for index, setting in enumerate([
            {"title": self.tr("Personalization"), "avatar": MPixmap(".svg")},
            {"title": self.tr("Tools"), "avatar": MPixmap(".svg")},
            {"title": self.tr("Credentials"), "avatar": MPixmap(".svg")},
            {"title": self.tr("LLMs"), "avatar": MPixmap(".svg")},
            {"title": self.tr("Text Rendering"), "avatar": MPixmap(".svg")},
            {"title": self.tr("Export"), "avatar": MPixmap(".svg")},
        ]):
            nav_card = ClickMeta(extra=False)
            nav_card.setup_data(setting)
            nav_card.clicked.connect(lambda i=index, c=nav_card: self.on_nav_clicked(i, c))
            navbar_layout.addWidget(nav_card)
            self.nav_cards.append(nav_card)

        navbar_layout.addStretch(1)
        return navbar_layout

    def on_nav_clicked(self, index: int, clicked_nav: ClickMeta):
        # Remove highlight from the previously highlighted nav item
        if self.current_highlighted_nav:
            self.current_highlighted_nav.set_highlight(False)

        # Highlight the clicked nav item
        clicked_nav.set_highlight(True)
        self.current_highlighted_nav = clicked_nav

        # Set the current index of the stacked widget
        self.stacked_widget.setCurrentIndex(index)

    def _create_personalization_layout(self):

        personalization_layout = QtWidgets.QVBoxLayout()

        language_widget, self.lang_combo = self._create_title_and_combo(self.tr("Language"), self.languages)
        self.set_combo_box_width(self.lang_combo, self.languages)
        theme_widget, self.theme_combo = self._create_title_and_combo(self.tr("Theme"), self.themes)
        self.set_combo_box_width(self.theme_combo, self.themes)

        personalization_layout.addWidget(language_widget) 
        personalization_layout.addWidget(theme_widget) 
        personalization_layout.addStretch()

        return personalization_layout

    def _create_tools_layout(self):
        tools_layout = QtWidgets.QVBoxLayout()

        translator_widget, self.translator_combo = self._create_title_and_combo(self.tr("Translator"), self.supported_translators)
        self.set_combo_box_width(self.translator_combo, self.supported_translators)

        ocr_widget, self.ocr_combo = self._create_title_and_combo(self.tr("OCR"), self.ocr_engines)
        self.set_combo_box_width(self.ocr_combo, self.ocr_engines)

        inpainting_label = MLabel("Inpainting").h4() 
        inpainter_widget, self.inpainter_combo = self._create_title_and_combo(self.tr("Inpainter"), self.inpainters)
        self.set_combo_box_width(self.inpainter_combo, self.inpainters)

        inpaint_strategy_widget, self.inpaint_strategy_combo = self._create_title_and_combo(self.tr("HD Strategy"), self.inpaint_strategy)
        self.set_combo_box_width(self.inpaint_strategy_combo, self.inpaint_strategy)

        # Set "Resize" as the default strategy
        self.inpaint_strategy_combo.setCurrentText(self.tr("Resize"))

        # Add additional widgets for HD Strategy
        self.hd_strategy_widgets = QtWidgets.QWidget()
        self.hd_strategy_layout = QtWidgets.QVBoxLayout(self.hd_strategy_widgets)

        # Resize strategy widgets
        self.resize_widget = QtWidgets.QWidget()

        about_resize_layout = QtWidgets.QVBoxLayout(self.resize_widget)
        resize_layout = QtWidgets.QHBoxLayout()
        resize_label = MLabel(self.tr("Resize Limit:"))
        about_resize_label = MLabel(self.tr("Resize the longer side of the image to a specific size,\nthen do inpainting on the resized image."))
        self.resize_spinbox = MSpinBox().small()
        self.resize_spinbox.setFixedWidth(70)
        self.resize_spinbox.setMaximum(3000)
        self.resize_spinbox.setValue(960)
        resize_layout.addWidget(resize_label)
        resize_layout.addWidget(self.resize_spinbox)
        resize_layout.addStretch()
        about_resize_layout.addWidget(about_resize_label)
        about_resize_layout.addLayout(resize_layout)
        about_resize_layout.setContentsMargins(5, 5, 5, 5)
        about_resize_layout.addStretch()

        # Crop strategy widgets
        self.crop_widget = QtWidgets.QWidget()

        crop_layout = QtWidgets.QVBoxLayout(self.crop_widget)
        about_crop_label = MLabel(self.tr("Crop masking area from the original image to do inpainting."))
        crop_margin_layout = QtWidgets.QHBoxLayout()
        crop_margin_label = MLabel(self.tr("Crop Margin:"))
        self.crop_margin_spinbox = MSpinBox().small()
        self.crop_margin_spinbox.setFixedWidth(70)
        self.crop_margin_spinbox.setMaximum(3000)
        self.crop_margin_spinbox.setValue(512)
        crop_margin_layout.addWidget(crop_margin_label)
        crop_margin_layout.addWidget(self.crop_margin_spinbox)
        crop_margin_layout.addStretch()

        crop_trigger_layout = QtWidgets.QHBoxLayout()
        crop_trigger_label = MLabel(self.tr("Crop Trigger Size:"))
        self.crop_trigger_spinbox = MSpinBox().small()
        self.crop_trigger_spinbox.setFixedWidth(70)
        self.crop_trigger_spinbox.setMaximum(3000)
        self.crop_trigger_spinbox.setValue(512)
        crop_trigger_layout.addWidget(crop_trigger_label)
        crop_trigger_layout.addWidget(self.crop_trigger_spinbox)
        crop_trigger_layout.addStretch()

        crop_layout.addWidget(about_crop_label)
        crop_layout.addLayout(crop_margin_layout)
        crop_layout.addLayout(crop_trigger_layout)
        crop_layout.setContentsMargins(5, 5, 5, 5)

        # Add widgets to hd_strategy_layout
        self.hd_strategy_layout.addWidget(self.resize_widget)
        self.hd_strategy_layout.addWidget(self.crop_widget)

        # Initially show resize widget and hide crop widget
        self.resize_widget.show()
        self.crop_widget.hide()

        # Connect the strategy combo box to update the visible widgets
        self.inpaint_strategy_combo.currentIndexChanged.connect(self.update_hd_strategy_widgets)

        # Add "Use GPU" checkbox
        self.use_gpu_checkbox = MCheckBox(self.tr("Use GPU"))

        tools_layout.addWidget(translator_widget)
        tools_layout.addSpacing(10)
        tools_layout.addWidget(ocr_widget)
        tools_layout.addSpacing(10)
        tools_layout.addWidget(inpainting_label)
        tools_layout.addWidget(inpainter_widget)
        tools_layout.addWidget(inpaint_strategy_widget)
        tools_layout.addWidget(self.hd_strategy_widgets)
        tools_layout.addSpacing(10)
        tools_layout.addWidget(self.use_gpu_checkbox)
        tools_layout.addStretch(1)

        # Initialize the HD strategy widgets
        self.update_hd_strategy_widgets(self.inpaint_strategy_combo.currentIndex())

        return tools_layout

    def _create_credentials_layout(self):
        credentials_layout = QtWidgets.QVBoxLayout()

        # Add a single "Save Keys" checkbox at the top
        self.save_keys_checkbox = MCheckBox(self.tr("Save Keys"))
        credentials_layout.addWidget(self.save_keys_checkbox)
        credentials_layout.addSpacing(20)

        for service in self.credential_services:
            service_layout = QtWidgets.QVBoxLayout()
            
            # Service name
            service_label = MLabel(service).strong()
            service_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            service_layout.addWidget(service_label)
            
            if service == "Microsoft Azure":
                # OCR subheading
                ocr_label = MLabel(self.tr("OCR")).secondary()
                service_layout.addWidget(ocr_label)

                # API Key (OCR)
                ocr_api_key_input = MLineEdit()
                ocr_api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                ocr_api_key_input.setFixedWidth(400)
                ocr_api_key_prefix = MLabel(self.tr("API Key")).border()
                self.set_label_width(ocr_api_key_prefix)
                ocr_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                ocr_api_key_input.set_prefix_widget(ocr_api_key_prefix)
                service_layout.addWidget(ocr_api_key_input)
                
                self.credential_widgets["Microsoft Azure_api_key_ocr"] = ocr_api_key_input
                
                # Endpoint URL
                endpoint_input = MLineEdit()
                endpoint_input.setFixedWidth(400)
                endpoint_prefix = MLabel(self.tr("Endpoint URL")).border()
                self.set_label_width(endpoint_prefix)
                endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                endpoint_input.set_prefix_widget(endpoint_prefix)
                service_layout.addWidget(endpoint_input)
                
                self.credential_widgets["Microsoft Azure_endpoint"] = endpoint_input

                # Translate subheading
                translate_label = MLabel(self.tr("Translate")).secondary()
                service_layout.addWidget(translate_label)

                # API Key (Translator)
                translator_api_key_input = MLineEdit()
                translator_api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                translator_api_key_input.setFixedWidth(400)
                translator_api_key_prefix = MLabel(self.tr("API Key")).border()
                self.set_label_width(translator_api_key_prefix)
                translator_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                translator_api_key_input.set_prefix_widget(translator_api_key_prefix)
                service_layout.addWidget(translator_api_key_input)
                
                self.credential_widgets["Microsoft Azure_api_key_translator"] = translator_api_key_input

                # Region
                region_input = MLineEdit()
                region_input.setFixedWidth(400)
                region_prefix = MLabel(self.tr("Region")).border()
                self.set_label_width(region_prefix)
                region_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                region_input.set_prefix_widget(region_prefix)
                service_layout.addWidget(region_input)
                
                self.credential_widgets["Microsoft Azure_region"] = region_input
            else:
                # API Key for other services
                api_key_input = MLineEdit()
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                api_key_input.setFixedWidth(400)
                api_key_prefix = MLabel(self.tr("API Key")).border()
                self.set_label_width(api_key_prefix)
                api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                api_key_input.set_prefix_widget(api_key_prefix)
                service_layout.addWidget(api_key_input)
                
                self.credential_widgets[f"{service}_api_key"] = api_key_input

            credentials_layout.addLayout(service_layout)
            credentials_layout.addSpacing(20)  # Add 20 pixels of vertical spacing between services


        credentials_layout.addStretch(1)  # Push everything to the top

        # Wrap the layout in a QScrollArea
        scroll_area = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        scroll_widget.setLayout(credentials_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(scroll_area)

        return main_layout

    def _create_llms_layout(self):
        llms_layout = QtWidgets.QVBoxLayout()

        prompt_label = MLabel(self.tr("Extra Context:"))
        self.llm_widgets['extra_context'] = MTextEdit()

        image_checkbox = MCheckBox(self.tr("Provide Image as input to multimodal LLMs"))
        image_checkbox.setChecked(True)
        self.llm_widgets['image_input'] = image_checkbox

        llms_layout.addWidget(prompt_label)
        llms_layout.addWidget(self.llm_widgets['extra_context'])
        llms_layout.addWidget(image_checkbox)
        llms_layout.addStretch(1)

        return llms_layout

    def _create_text_rendering_layout(self):
        text_rendering_layout = QtWidgets.QVBoxLayout()

        # Text Alignment
        alignment_layout = QtWidgets.QVBoxLayout()
        alignment_label = MLabel(self.tr("Text Alignment")).h4()
        alignment_combo = MComboBox().small()
        alignment_combo.addItems(self.alignment)
        self.set_combo_box_width(alignment_combo, self.alignment)
        alignment_combo.setCurrentText(self.tr("Center"))
        alignment_layout.addWidget(alignment_label)
        alignment_layout.addWidget(alignment_combo)
        text_rendering_layout.addLayout(alignment_layout)

        # Font Selection
        font_layout = QtWidgets.QVBoxLayout()
        combo_layout = QtWidgets.QHBoxLayout()

        min_font_layout = QtWidgets.QHBoxLayout()
        max_font_layout = QtWidgets.QHBoxLayout()
        min_font_label = MLabel(self.tr("Minimum Font Size:"))
        max_font_label = MLabel(self.tr("Maximum Font Size:"))

        self.min_font_spinbox = MSpinBox().small()
        self.min_font_spinbox.setFixedWidth(60)
        self.min_font_spinbox.setMaximum(100)
        self.min_font_spinbox.setValue(12)

        self.max_font_spinbox = MSpinBox().small()
        self.max_font_spinbox.setFixedWidth(60)
        self.max_font_spinbox.setMaximum(100)
        self.max_font_spinbox.setValue(40)

        min_font_layout.addWidget(min_font_label)
        min_font_layout.addWidget(self.min_font_spinbox)
        min_font_layout.addStretch()

        max_font_layout.addWidget(max_font_label)
        max_font_layout.addWidget(self.max_font_spinbox)
        max_font_layout.addStretch()

        font_label = MLabel(self.tr("Font")).h4()
        self.font_combo = MComboBox().small()
        font_folder_path = os.path.join(os.getcwd(), "fonts")
        font_files = [f for f in os.listdir(font_folder_path) if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
        self.font_combo.addItems(font_files)
        self.set_combo_box_width(self.font_combo, font_files)

        self.font_browser = MClickBrowserFileToolButton(multiple=True)
        self.font_browser.set_dayu_filters([".ttf", ".ttc", ".otf", ".woff", ".woff2"])
        self.font_browser.setToolTip(self.tr("Import the Font to use for Rendering Text on Images"))

        combo_layout.addWidget(self.font_combo)
        combo_layout.addWidget(self.font_browser)
        combo_layout.addStretch()

        font_layout.addWidget(font_label)
        font_layout.addLayout(combo_layout)
        font_layout.addLayout(min_font_layout)
        font_layout.addLayout(max_font_layout)

        text_rendering_layout.addSpacing(10)
        text_rendering_layout.addLayout(font_layout)

        # Font Color
        color_layout = QtWidgets.QVBoxLayout()
        color_label = MLabel(self.tr("Color"))
        self.color_button = QtWidgets.QPushButton()
        self.color_button.setFixedSize(30, 30)  # Set a fixed size for the button
        self.color_button.setStyleSheet(
            "background-color: black; border: none; border-radius: 5px;"
        )
        self.color_button.setProperty('selected_color', "#000000")
        
        color_layout.addWidget(color_label)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        text_rendering_layout.addLayout(color_layout)
        text_rendering_layout.addSpacing(10)

        uppercase_checkbox = MCheckBox(self.tr("Render Text in UpperCase"))
        text_rendering_layout.addWidget(uppercase_checkbox)

        self.outline_checkbox = MCheckBox(self.tr("Render Text With White Outline"))
        self.outline_checkbox.setToolTip(self.tr("When checked, black bubbles with white text will be rendered automatically without changing color"))
        text_rendering_layout.addWidget(self.outline_checkbox)

        # Store widgets for later access
        self.text_rendering_widgets['alignment'] = alignment_combo
        self.text_rendering_widgets['font'] = self.font_combo
        self.text_rendering_widgets['color_button'] = self.color_button
        self.text_rendering_widgets['upper_case'] = uppercase_checkbox
        self.text_rendering_widgets['outline'] = self.outline_checkbox

        text_rendering_layout.addStretch(1)
        return text_rendering_layout

    def _create_export_layout(self):
        export_layout = QtWidgets.QVBoxLayout()

        batch_label = MLabel(self.tr("Automatic Mode")).h4()

        raw_text_checkbox = MCheckBox(self.tr("Export Raw Text"))
        translated_text_checkbox = MCheckBox(self.tr("Export Translated text"))
        inpainted_image_checkbox = MCheckBox(self.tr("Export Inpainted Image"))

        self.export_widgets['raw_text'] = raw_text_checkbox
        self.export_widgets['translated_text'] = translated_text_checkbox
        self.export_widgets['inpainted_image'] = inpainted_image_checkbox

        export_layout.addWidget(batch_label)
        export_layout.addWidget(raw_text_checkbox)
        export_layout.addWidget(translated_text_checkbox)
        export_layout.addWidget(inpainted_image_checkbox)

        file_types = ['pdf', 'epub', 'cbr', 'cbz', 'cb7', 'cbt']
        available_file_types = ['pdf', 'epub', 'cbz', 'cb7']  # Exclude 'CBR' and add other types

        for file_type in file_types:
            save_layout = QtWidgets.QHBoxLayout()
            save_label = MLabel(self.tr("Save {file_type} as:").format(file_type=file_type))
            save_combo = MComboBox().small()
            save_items = [ft for ft in available_file_types if ft != 'cbr']
            save_combo.addItems(save_items)  # Exclude 'CBR'
            self.set_combo_box_width(save_combo, save_items)

            # Set the default selection to the file type, or 'cbz' if file type is 'cbr'
            if file_type == 'cbr':
                save_combo.setCurrentText('cbz')
            elif file_type in available_file_types:
                save_combo.setCurrentText(file_type)

            self.export_widgets[f'.{file_type.lower()}_save_as'] = save_combo

            save_layout.addWidget(save_label)
            save_layout.addWidget(save_combo)
            save_layout.addStretch(1)

            export_layout.addLayout(save_layout)

        export_layout.addStretch(1)

        return export_layout
    
    def update_hd_strategy_widgets(self, index: int):
        strategy = self.inpaint_strategy_combo.itemText(index)
        self.resize_widget.setVisible(strategy == self.tr("Resize"))
        self.crop_widget.setVisible(strategy == self.tr("Crop"))
        
        # Adjust the layout to remove empty space when "Original" is selected
        if strategy == self.tr("Original"):
            self.hd_strategy_widgets.setFixedHeight(0)
        else:
            self.hd_strategy_widgets.setFixedHeight(self.hd_strategy_widgets.sizeHint().height())

    def set_combo_box_width(self, combo_box: MComboBox, items: List[str], padding: int = 40):
        font_metrics = QFontMetrics(combo_box.font())
        max_width = max(font_metrics.horizontalAdvance(item) for item in items)
        combo_box.setFixedWidth(max_width + padding)

    def set_label_width(self, label: MLabel, padding: int = 20):
        font_metrics = QFontMetrics(label.font())
        text_width = font_metrics.horizontalAdvance(label.text())
        label.setFixedWidth(text_width + padding)



