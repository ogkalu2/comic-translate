import os
from typing import List
from PySide6 import QtWidgets
from PySide6 import QtCore
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QIntValidator, QDoubleValidator

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
from ..dayu_widgets.slider import MSlider
from ..dayu_widgets.collapse import MCollapse


current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
font_folder_path = os.path.join(project_root, 'fonts')

class SettingsPageUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SettingsPageUI, self).__init__(parent)

        self.credential_widgets = {}
        self.export_widgets = {}

        self.inpainters = ['LaMa', 'AOT', 'MI-GAN']
        self.detectors = ['RT-DETR-v2']
        self.ocr_engines = [self.tr("Default"), self.tr('Microsoft OCR'), self.tr('Google Cloud Vision'), self.tr('Gemini-2.0-Flash'), self.tr('GPT-4.1-mini')]
        self.inpaint_strategy = [self.tr('Resize'), self.tr('Original'), self.tr('Crop')]
        self.themes = [self.tr('Dark'), self.tr('Light')]
        self.alignment = [self.tr("Left"), self.tr("Center"), self.tr("Right")]

        self.credential_services = [self.tr("Custom"), self.tr("Deepseek"), self.tr("Open AI GPT"), self.tr("Microsoft Azure"), self.tr("Google Cloud"), 
                                    self.tr("Google Gemini"), self.tr("DeepL"), self.tr("Anthropic Claude"), self.tr("Yandex")]
        
        self.supported_translators = [self.tr("GPT-4.1"), self.tr("GPT-4.1-mini"), self.tr("DeepL"), 
                                    self.tr("Claude-3.7-Sonnet"), self.tr("Claude-3.5-Haiku"),
                                    self.tr("Gemini-2.5-Flash"), self.tr("Yandex"), self.tr("Google Translate"),
                                    self.tr("Microsoft Translator"), self.tr("Deepseek-v3"), self.tr("Opus-MT"),
                                    self.tr("Custom"),]
        
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
            self.tr("Custom"): "Custom",
            self.tr("Deepseek-v3"): "Deepseek-v3",
            self.tr("GPT-4.1"): "GPT-4.1",
            self.tr("GPT-4.1-mini"): "GPT-4.1-mini",
            self.tr("DeepL"): "DeepL",
            self.tr("Claude-3.7-Sonnet"): "Claude-3.7-Sonnet",
            self.tr("Claude-3.5-Haiku"): "Claude-3.5-Haiku",
            self.tr("Gemini-2.5-Flash"): "Gemini-2.5-Flash",
            self.tr("Gemini-2.5-Pro"): "Gemini-2.5-Pro",
            self.tr("Yandex"): "Yandex",
            self.tr("Google Translate"): "Google Translate",
            self.tr("Microsoft Translator"): "Microsoft Translator",

            # OCR mappings
            self.tr("Default"): "Default",
            self.tr("Microsoft OCR"): "Microsoft OCR",
            self.tr("Google Cloud Vision"): "Google Cloud Vision",

            # Inpainter mappings
            "LaMa": "LaMa",
            "MI-GAN": "MI-GAN",
            "AOT": "AOT",

            # Detector mappings
            "RT-DETR-v2": "RT-DETR-v2",

            # HD Strategy mappings
            self.tr("Resize"): "Resize",
            self.tr("Original"): "Original",
            self.tr("Crop"): "Crop",

            # Alignment mappings
            self.tr("Left"): "Left",
            self.tr("Center"): "Center",
            self.tr("Right"): "Right",

            # Credential services mappings
            self.tr("Custom"): "Custom",
            self.tr("Deepseek"): "Deepseek",
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

        detector_widget, self.detector_combo = self._create_title_and_combo(self.tr("Text Detector"), self.detectors)
        self.set_combo_box_width(self.detector_combo, self.detectors)

        inpainting_label = MLabel(self.tr("Inpainting")).h4() 
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
        tools_layout.addWidget(detector_widget)
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

            elif service == "Custom":
                # API Key
                api_key_input = MLineEdit()
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                api_key_input.setFixedWidth(400)
                api_key_prefix = MLabel(self.tr("API Key")).border()
                self.set_label_width(api_key_prefix)
                api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                api_key_input.set_prefix_widget(api_key_prefix)
                service_layout.addWidget(api_key_input)
                
                self.credential_widgets[f"{service}_api_key"] = api_key_input
                
                # Endpoint URL
                endpoint_input = MLineEdit()
                endpoint_input.setFixedWidth(400)
                endpoint_prefix = MLabel(self.tr("Endpoint URL")).border()
                self.set_label_width(endpoint_prefix)
                endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                endpoint_input.set_prefix_widget(endpoint_prefix)
                service_layout.addWidget(endpoint_input)
                
                self.credential_widgets[f"{service}_api_url"] = endpoint_input

                # Model Name
                model_input = MLineEdit()
                model_input.setFixedWidth(400)
                model_prefix = MLabel(self.tr("Model")).border()
                self.set_label_width(model_prefix)
                model_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                model_input.set_prefix_widget(model_prefix)
                service_layout.addWidget(model_input)
                
                self.credential_widgets[f"{service}_model"] = model_input

            elif service == "Yandex":
                # API Key
                api_key_input = MLineEdit()
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                api_key_input.setFixedWidth(400)
                api_key_prefix = MLabel(self.tr("API Key")).border()
                self.set_label_width(api_key_prefix)
                api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                api_key_input.set_prefix_widget(api_key_prefix)
                service_layout.addWidget(api_key_input)
                
                self.credential_widgets[f"{service}_api_key"] = api_key_input
                
                # Folder ID
                folder_id_input = MLineEdit()
                folder_id_input.setFixedWidth(400)
                folder_id_prefix = MLabel(self.tr("Folder ID")).border()
                self.set_label_width(folder_id_prefix)
                folder_id_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                folder_id_input.set_prefix_widget(folder_id_prefix)
                service_layout.addWidget(folder_id_input)
                
                self.credential_widgets[f"{service}_folder_id"] = folder_id_input
                
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
        
        # Main horizontal layout to position the text edit and controls side by side
        main_layout = QtWidgets.QHBoxLayout()

        self.image_checkbox = MCheckBox(self.tr("Provide Image as input to multimodal LLMs"))
        self.image_checkbox.setChecked(True)
        
        # Left side - Text edit area
        left_layout = QtWidgets.QVBoxLayout()
        prompt_label = MLabel(self.tr("Extra Context:"))
        self.extra_context = MTextEdit()
        self.extra_context.setMinimumHeight(200)
        left_layout.addWidget(prompt_label)
        left_layout.addWidget(self.extra_context)
        left_layout.addWidget(self.image_checkbox)
        left_layout.addStretch(1)
        
        # Right side - Controls
        right_layout = QtWidgets.QVBoxLayout()
        
        # Temperature control - keep this in the main UI
        temp_layout = QtWidgets.QVBoxLayout()
        temp_header = MLabel(self.tr("Temperature")).h4()
        temp_controls = QtWidgets.QHBoxLayout()
        
        self.temp_slider = MSlider(QtCore.Qt.Horizontal)
        self.temp_slider.setRange(0, 200)  # 0-2 with 100x multiplier for precision
        self.temp_slider.setValue(100)  # Default to 1
        self.temp_slider.disable_show_text()
        
        self.temp_edit = MLineEdit().small()
        self.temp_edit.setFixedWidth(50)
        temp_validator = QDoubleValidator(0.0, 2.0, 2)  # two decimals
        self.temp_edit.setValidator(temp_validator)
        self.temp_edit.setText("1")
        
        temp_controls.addWidget(self.temp_slider)
        temp_controls.addWidget(self.temp_edit)
        
        temp_layout.addWidget(temp_header)
        temp_layout.addLayout(temp_controls)
        
        # Create advanced settings widgets for the collapsible section
        advanced_widget = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(advanced_widget)
        advanced_layout.setContentsMargins(0, 5, 0, 5)
        
        # Top P control - for advanced settings
        top_p_layout = QtWidgets.QVBoxLayout()
        top_p_header = MLabel(self.tr("Top P")).h4()
        top_p_controls = QtWidgets.QHBoxLayout()
        
        self.top_p_slider = MSlider(QtCore.Qt.Horizontal)
        self.top_p_slider.setRange(0, 100)  # 0-1 with 100x multiplier for precision
        self.top_p_slider.setValue(95)  # Default to 0.95
        self.top_p_slider.disable_show_text() 
        
        self.top_p_edit = MLineEdit().small()
        self.top_p_edit.setFixedWidth(50)
        top_p_validator = QDoubleValidator(0.0, 1.0, 2)
        self.top_p_edit.setValidator(top_p_validator)
        self.top_p_edit.setText("0.95")
        
        top_p_controls.addWidget(self.top_p_slider)
        top_p_controls.addWidget(self.top_p_edit)
        
        top_p_layout.addWidget(top_p_header)
        top_p_layout.addLayout(top_p_controls)
        
        # Max Tokens control - for advanced settings 
        max_tokens_layout = QtWidgets.QVBoxLayout()
        max_tokens_header = MLabel(self.tr("Max Tokens")).h4()
        max_tokens_controls = QtWidgets.QHBoxLayout()
        
        # Add slider for max tokens
        self.max_tokens_slider = MSlider(QtCore.Qt.Horizontal)
        self.max_tokens_slider.setRange(1, 16384)  # Common range for most models
        self.max_tokens_slider.setValue(4096)  # Default to 4096
        self.max_tokens_slider.disable_show_text()
        
        self.max_tokens_edit = MLineEdit().small()
        self.max_tokens_edit.setFixedWidth(70)
        max_tokens_validator = QIntValidator(1, 16384)
        self.max_tokens_edit.setValidator(max_tokens_validator)
        self.max_tokens_edit.setText("4096")
        
        max_tokens_controls.addWidget(self.max_tokens_slider)
        max_tokens_controls.addWidget(self.max_tokens_edit)
        
        max_tokens_layout.addWidget(max_tokens_header)
        max_tokens_layout.addLayout(max_tokens_controls)
        
        # Add Top P and Max Tokens to the advanced settings layout
        advanced_layout.addLayout(top_p_layout)
        advanced_layout.addSpacing(10)
        advanced_layout.addLayout(max_tokens_layout)
        
        # Create the collapsible section for advanced settings
        self.advanced_collapse = MCollapse()
        section_data = {
            "title": "Advanced Settings",
            "widget": advanced_widget,
            "expand": False,  # Initially collapsed
        }
        self.advanced_collapse.add_section(section_data)
        
        # Add standard controls to right layout
        right_layout.addLayout(temp_layout)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.advanced_collapse)
        right_layout.addStretch(1)
        
        # Add left and right layouts to main layout
        main_layout.addLayout(left_layout, 3)  # Text edit takes 3/4 of the space
        main_layout.addLayout(right_layout, 1)  # Controls take 1/4 of the space
        
        # Add the main layout and the checkbox to the llms layout
        llms_layout.addLayout(main_layout)
        llms_layout.addStretch(1)
        
        # Connect signals for syncing sliders and edit fields
        self.temp_slider.valueChanged.connect(self._update_temp_edit)
        self.temp_edit.textChanged.connect(self._update_temp_slider)
        self.top_p_slider.valueChanged.connect(self._update_top_p_edit)
        self.top_p_edit.textChanged.connect(self._update_top_p_slider)
        self.max_tokens_slider.valueChanged.connect(self._update_max_tokens_edit)
        self.max_tokens_edit.textChanged.connect(self._update_max_tokens_slider)
        
        return llms_layout

    def _update_temp_edit(self):
        # Update text edit when slider changes
        value = self.temp_slider.value() / 100.0
        self.temp_edit.setText(str(value))
        
    def _update_temp_slider(self):
        # Update slider when text edit changes
        try:
            text = self.temp_edit.text()
            if text:
                value = float(text) * 100
                self.temp_slider.setValue(int(value))
        except ValueError:
            pass

    def _update_top_p_edit(self):
        # Update text edit when slider changes
        value = self.top_p_slider.value() / 100.0
        self.top_p_edit.setText(str(value))
        
    def _update_top_p_slider(self):
        # Update slider when text edit changes
        try:
            text = self.top_p_edit.text()
            if text:
                value = float(text) * 100
                self.top_p_slider.setValue(int(value))
        except ValueError:
            pass

    def _update_max_tokens_edit(self):
        # Update text edit when slider changes
        value = self.max_tokens_slider.value()
        self.max_tokens_edit.setText(str(value))
        
    def _update_max_tokens_slider(self):
        # Update slider when text edit changes
        try:
            text = self.max_tokens_edit.text()
            if text:
                value = int(text)
                # Clamp the value to slider range
                value = max(1, min(value, 16384))
                self.max_tokens_slider.setValue(value)
        except ValueError:
            pass

    def _create_text_rendering_layout(self):
        text_rendering_layout = QtWidgets.QVBoxLayout()

        # Font Selection
        font_layout = QtWidgets.QVBoxLayout()

        min_font_layout = QtWidgets.QHBoxLayout()
        max_font_layout = QtWidgets.QHBoxLayout()
        min_font_label = MLabel(self.tr("Minimum Font Size:"))
        max_font_label = MLabel(self.tr("Maximum Font Size:"))

        self.min_font_spinbox = MSpinBox().small()
        self.min_font_spinbox.setFixedWidth(60)
        self.min_font_spinbox.setMaximum(100)
        self.min_font_spinbox.setValue(9)

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

        font_label = MLabel(self.tr("Font:")).h4()
        
        # Create a horizontal layout for the font browser and its label
        font_browser_layout = QtWidgets.QHBoxLayout()
        import_font_label = MLabel(self.tr("Import Font:"))
        self.font_browser = MClickBrowserFileToolButton(multiple=True)
        self.font_browser.set_dayu_filters([".ttf", ".ttc", ".otf", ".woff", ".woff2"])
        self.font_browser.setToolTip(self.tr("Import the Font to use for Rendering Text on Images"))
        
        # Add the browser and label to the horizontal layout
        font_browser_layout.addWidget(import_font_label)
        font_browser_layout.addWidget(self.font_browser)
        font_browser_layout.addStretch()

        font_layout.addWidget(font_label)
        font_layout.addLayout(font_browser_layout)  # Add the horizontal layout instead of just the browser
        font_layout.addLayout(min_font_layout)
        font_layout.addLayout(max_font_layout)

        # Uppercase checkbox 
        self.uppercase_checkbox = MCheckBox(self.tr("Render Text in UpperCase"))
        text_rendering_layout.addWidget(self.uppercase_checkbox)

        text_rendering_layout.addSpacing(10)
        text_rendering_layout.addLayout(font_layout)
        text_rendering_layout.addSpacing(10)

        text_rendering_layout.addStretch(1)
        return text_rendering_layout

    def _create_export_layout(self):
        export_layout = QtWidgets.QVBoxLayout()

        batch_label = MLabel(self.tr("Automatic Mode")).h4()

        self.raw_text_checkbox = MCheckBox(self.tr("Export Raw Text"))
        self.translated_text_checkbox = MCheckBox(self.tr("Export Translated text"))
        self.inpainted_image_checkbox = MCheckBox(self.tr("Export Inpainted Image"))

        export_layout.addWidget(batch_label)
        export_layout.addWidget(self.raw_text_checkbox)
        export_layout.addWidget(self.translated_text_checkbox)
        export_layout.addWidget(self.inpainted_image_checkbox)

        self.from_file_types = ['pdf', 'epub', 'cbr', 'cbz', 'cb7', 'cbt', 'zip', 'rar']
        available_file_types = ['pdf', 'cbz', 'cb7', 'zip']  # Exclude 'CBR' and add other types

        for file_type in self.from_file_types:
            save_layout = QtWidgets.QHBoxLayout()
            save_label = MLabel(self.tr("Save {file_type} as:").format(file_type=file_type))
            save_combo = MComboBox().small()
            save_combo.addItems(available_file_types)  
            self.set_combo_box_width(save_combo, available_file_types)

            # Set the default selection to the file type, or 'cbz' if file type is 'cbr'
            if file_type in ['cbr', 'cbt']:
                save_combo.setCurrentText('cbz')
            elif file_type == 'rar':
                save_combo.setCurrentText('zip')
            elif file_type == 'epub':
                save_combo.setCurrentText('pdf')
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



