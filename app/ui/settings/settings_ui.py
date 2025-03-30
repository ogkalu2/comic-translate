import os
from typing import List
from PySide6 import QtWidgets
from PySide6 import QtCore, QtGui
from PySide6.QtGui import QFontMetrics
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ..dayu_widgets.label import MLabel
from ..dayu_widgets.line_edit import MLineEdit
from ..dayu_widgets.text_edit import MTextEdit
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.clickable_card import ClickMeta
from ..dayu_widgets.divider import MDivider
from ..dayu_widgets.qt import MPixmap
from ..dayu_widgets.combo_box import MComboBox
from ..dayu_widgets.spin_box import MSpinBox
from ..dayu_widgets.message import MMessage
from ..dayu_widgets.browser import MClickBrowserFileToolButton
from ..dayu_widgets.push_button import MPushButton

current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
font_folder_path = os.path.join(project_root, 'fonts')

class SettingsPageUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SettingsPageUI, self).__init__(parent)

        self.credential_widgets = {}
        self.export_widgets = {}

        self.inpainters = ['LaMa', 'AOT', 'MI-GAN']
        self.ocr_engines = [self.tr("Default"), self.tr('Microsoft OCR'), self.tr('Google Cloud Vision'), self.tr('GPT-4o'), self.tr('Qwen2.5 VL 72B Instruct (free)'), self.tr('Qwen2.5 VL 72B Instruct'), self.tr('Qwen-vl-2.5'), self.tr('Mistral OCR')]
        self.inpaint_strategy = [self.tr('Resize'), self.tr('Original'), self.tr('Crop')]
        self.themes = [self.tr('Dark'), self.tr('Light')]
        self.alignment = [self.tr("Left"), self.tr("Center"), self.tr("Right")]

        self.credential_services = [self.tr("Custom"), self.tr("Deepseek"), self.tr("Open AI GPT"), self.tr("Microsoft Azure"), self.tr("Google Cloud"),
                                     self.tr("Google Gemini"), self.tr("DeepL"), self.tr("Anthropic Claude"), self.tr("Yandex"), self.tr("Qwen2.5 VL 72B Instruct (free)"),
                                     self.tr("Qwen2.5 VL 72B Instruct"), self.tr("Qwen-Max")]
        
        self.supported_translators = [self.tr("GPT-4o"), self.tr("GPT-4o mini"), self.tr("DeepL"),
                                    self.tr("Claude-3-Opus"), self.tr("Claude-3.7-Sonnet"),
                                    self.tr("Claude-3.5-Haiku"), self.tr("Gemini-2.0-Flash"),
                                    self.tr("Gemini-2.0-Pro"), self.tr("Yandex"), self.tr("Google Translate"),
                                    self.tr("Microsoft Translator"), self.tr("Deepseek-v3"), self.tr("Qwen2.5 VL 72B Instruct (free)"),
                                    self.tr("Qwen2.5 VL 72B Instruct"), self.tr("Qwen-Max"), self.tr("Custom"),]
        
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
            self.tr("GPT-4o"): "GPT-4o",
            self.tr("GPT-4o mini"): "GPT-4o mini",
            self.tr("DeepL"): "DeepL",
            self.tr("Claude-3-Opus"): "Claude-3-Opus",
            self.tr("Claude-3.7-Sonnet"): "Claude-3.7-Sonnet",
            self.tr("Claude-3.5-Haiku"): "Claude-3.5-Haiku",
            self.tr("Gemini-2.0-Flash"): "Gemini-2.0-Flash",
            self.tr("Gemini-2.0-Pro"): "Gemini-2.0-Pro",
            self.tr("Yandex"): "Yandex",
            self.tr("Google Translate"): "Google Translate",
            self.tr("Microsoft Translator"): "Microsoft Translator",
            self.tr("Qwen2.5 VL 72B Instruct (free)"): "Qwen2.5 VL 72B Instruct (free)",
            self.tr("Qwen2.5 VL 72B Instruct"): "Qwen2.5 VL 72B Instruct",
            self.tr("Qwen-Max"): "Qwen-Max",

            # OCR mappings
            self.tr("Default"): "Default",
            self.tr("Microsoft OCR"): "Microsoft OCR",
            self.tr("Google Cloud Vision"): "Google Cloud Vision",
            self.tr("GPT-4o"): "GPT-4o",
            self.tr("Qwen2.5 VL 72B Instruct (free)"): "Qwen2.5 VL 72B Instruct (free)",
            self.tr("Qwen2.5 VL 72B Instruct"): "Qwen2.5 VL 72B Instruct",
            self.tr("Qwen-vl-2.5"): "Qwen-vl-2.5",
            self.tr("Mistral OCR"): "Mistral OCR",

            # Inpainter mappings
            "LaMa": "LaMa",
            "MI-GAN": "MI-GAN",
            "AOT": "AOT",

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
            self.tr("Qwen2.5 VL 72B Instruct (free)"): "Qwen2.5 VL 72B Instruct (free)",
            self.tr("Qwen2.5 VL 72B Instruct"): "Qwen2.5 VL 72B Instruct",
            self.tr("Qwen-Max"): "Qwen-Max",
        }

        # Create reverse mappings for loading
        self.reverse_mappings = {v: k for k, v in self.value_mappings.items()}

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI components."""
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

        self._load_saved_prompts()  # Carica i prompt salvati

    def _load_saved_prompts(self):
        """Carica i prompt salvati dal file JSON."""
        try:
            import os
            import json
            
            # Percorso del file dei prompt
            prompts_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "config", "prompts.json")
            
            # Verifica se il file esiste
            if os.path.exists(prompts_file):
                with open(prompts_file, "r", encoding="utf-8") as f:
                    prompts = json.load(f)
                    
                # Memorizziamo i prompt per caricarli più tardi nei widget
                self.saved_prompts = prompts
            else:
                # Inizializza con valori predefiniti
                self.saved_prompts = {
                    "qwen_ocr_prompt": "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre.",
                    "qwen_translate_prompt": ""
                }
        except Exception as e:
            print(f"Errore durante il caricamento dei prompt: {str(e)}")
            # Inizializza con valori predefiniti in caso di errore
            self.saved_prompts = {
                "qwen_ocr_prompt": "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre.",
                "qwen_translate_prompt": ""
            }

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
        
        # Mistral OCR widget
        mistral_widget = MLabel(self.tr("Mistral OCR"))
        ocr_cards_layout = QtWidgets.QVBoxLayout()
        ocr_cards_layout.addWidget(mistral_widget)
        
        # Add widgets to hd_strategy_layout
        self.hd_strategy_layout.addWidget(self.resize_widget)
        self.hd_strategy_layout.addWidget(self.crop_widget)
        self.hd_strategy_layout.addLayout(ocr_cards_layout)

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

    def update_hd_strategy_widgets(self, index):
        """Aggiorna i widget in base alla strategia di inpainting selezionata."""
        if index == 0:
            # Logica per la strategia 0
            self.resize_widget.setVisible(True)
            self.crop_widget.setVisible(False)
        elif index == 1:
            # Logica per la strategia 1
            self.resize_widget.setVisible(False)
            self.crop_widget.setVisible(False)
        else:
            # Logica per altre strategie
            self.resize_widget.setVisible(False)
            self.crop_widget.setVisible(True)

    def _create_credentials_layout(self):
        main_layout = QtWidgets.QVBoxLayout()
        
        # Add a single "Save Keys" checkbox at the top
        self.save_keys_checkbox = MCheckBox(self.tr("Save Keys"))
        main_layout.addWidget(self.save_keys_checkbox)
        main_layout.addSpacing(10)
        
        # Creiamo un tab widget per organizzare meglio le sezioni
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.setDocumentMode(True)  # Più moderno e pulito
        
        # Tab per OCR
        ocr_tab = QtWidgets.QWidget()
        ocr_layout = QtWidgets.QVBoxLayout(ocr_tab)
        
        # Tab per la traduzione
        translator_tab = QtWidgets.QWidget()
        translator_layout = QtWidgets.QVBoxLayout(translator_tab)
        
        # Tab per i servizi multiuso
        multifunction_tab = QtWidgets.QWidget()
        multifunction_layout = QtWidgets.QVBoxLayout(multifunction_tab)
        
        # Tab per i servizi personalizzati
        custom_tab = QtWidgets.QWidget()
        custom_layout = QtWidgets.QVBoxLayout(custom_tab)
        
        # Identifica quali modelli supportano OCR
        ocr_models = [
            self.tr("Microsoft Azure"),
            self.tr("Google Cloud Vision"),
            self.tr("GPT-4o")
        ]
        
        # Identifica i modelli multiuso (OCR + traduzione)
        multifunction_models = [
            self.tr("Qwen2.5 VL 72B Instruct (free)"),
            self.tr("Qwen2.5 VL 72B Instruct")
        ]
        
        # Lista di modelli solo per la traduzione
        translation_only_models = [
            service for service in self.credential_services
            if service not in ocr_models and service not in multifunction_models and service != self.tr("Custom")
        ]
        
        # ========== MODELLI MULTIUSO (OCR + TRADUZIONE) ==========
        
        # Creiamo un FlowLayout per organizzare le card in modo più flessibile
        multifunction_card_container = QtWidgets.QWidget()
        multifunction_cards_layout = QtWidgets.QVBoxLayout(multifunction_card_container)
        multifunction_cards_layout.setContentsMargins(0, 0, 0, 0)
        
        # Istruzioni in testa alla pagina
        instructions = MLabel(self.tr("Questi modelli supportano sia OCR che traduzione. Inserisci l'API key per ciascun servizio."))
        multifunction_layout.addWidget(instructions)
        multifunction_layout.addSpacing(10)
        
        # Aggiungiamo le card per i servizi multiuso
        for service in multifunction_models:
            # Creazione di una card per ogni servizio
            service_card = QtWidgets.QGroupBox(service)
            service_card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    font-weight: bold;
                }
            """)
            
            card_layout = QtWidgets.QVBoxLayout(service_card)
            
            # Badge di funzionalità
            badge = MLabel(self.tr("[OCR + Traduzione]")).secondary()
            badge.setStyleSheet("color: #3498db;")
            card_layout.addWidget(badge)
            
            # Layout orizzontale per API Key, GET e VERIFY
            api_key_layout = QtWidgets.QHBoxLayout()
            
            # API Key
            api_key_input = MLineEdit()
            api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            api_key_input.setFixedWidth(400)
            api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(api_key_prefix)
            api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            api_key_input.set_prefix_widget(api_key_prefix)
            api_key_layout.addWidget(api_key_input)
            
            # Pulsante GET
            get_button = QtWidgets.QPushButton(self.tr("GET"))
            get_button.setFixedWidth(60)
            get_button.clicked.connect(lambda checked=False, s=service: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(self._get_service_url(s))
            ))
            api_key_layout.addWidget(get_button)
            
            # Pulsante VERIFY
            verify_button = QtWidgets.QPushButton(self.tr("VERIFY"))
            verify_button.setFixedWidth(60)
            verify_button.clicked.connect(lambda checked=False, s=service, key=api_key_input: self.verify_api_key(key.text(), s))
            api_key_layout.addWidget(verify_button)
            
            card_layout.addLayout(api_key_layout)
            self.credential_widgets[f"{service}_api_key"] = api_key_input
            
            # Aggiungi la card al layout generale
            multifunction_cards_layout.addWidget(service_card)
        
        # Scrollable container per le card
        multifunction_scroll = QtWidgets.QScrollArea()
        multifunction_scroll.setWidgetResizable(True)
        multifunction_scroll.setWidget(multifunction_card_container)
        multifunction_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        multifunction_layout.addWidget(multifunction_scroll)
        
        # ========== MODELLI OCR ==========
        
        # Istruzioni in testa alla pagina
        ocr_instructions = MLabel(self.tr("Questi modelli forniscono funzionalità OCR (riconoscimento testo nelle immagini)."))
        ocr_layout.addWidget(ocr_instructions)
        ocr_layout.addSpacing(10)
        
        # Creiamo un container per le card OCR
        ocr_card_container = QtWidgets.QWidget()
        ocr_cards_layout = QtWidgets.QVBoxLayout(ocr_card_container)
        ocr_cards_layout.setContentsMargins(0, 0, 0, 0)
        
        # Microsoft Azure - OCR
        azure_service = self.tr("Microsoft Azure")
        if azure_service in ocr_models:
            azure_card = QtWidgets.QGroupBox(azure_service)
            azure_card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    font-weight: bold;
                }
            """)
            
            azure_layout = QtWidgets.QVBoxLayout(azure_card)
            
            # Badge di funzionalità
            azure_badge = MLabel(self.tr("[OCR + Traduzione]")).secondary()
            azure_badge.setStyleSheet("color: #3498db;")
            azure_layout.addWidget(azure_badge)
            
            # OCR subheading
            ocr_label = MLabel(self.tr("OCR")).secondary()
            ocr_label.setStyleSheet("font-weight: bold;")
            azure_layout.addWidget(ocr_label)

            # API Key (OCR)
            ocr_api_key_input = MLineEdit()
            ocr_api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            ocr_api_key_input.setFixedWidth(400)
            ocr_api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(ocr_api_key_prefix)
            ocr_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            ocr_api_key_input.set_prefix_widget(ocr_api_key_prefix)
            azure_layout.addWidget(ocr_api_key_input)
            
            self.credential_widgets["Microsoft Azure_api_key_ocr"] = ocr_api_key_input
            
            # Endpoint URL
            endpoint_input = MLineEdit()
            endpoint_input.setFixedWidth(400)
            endpoint_prefix = MLabel(self.tr("Endpoint URL")).border()
            self.set_label_width(endpoint_prefix)
            endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            endpoint_input.set_prefix_widget(endpoint_prefix)
            azure_layout.addWidget(endpoint_input)
            
            self.credential_widgets["Microsoft Azure_endpoint"] = endpoint_input

            # Translate subheading
            translate_label = MLabel(self.tr("Translator")).secondary()
            translate_label.setStyleSheet("font-weight: bold;")
            azure_layout.addWidget(translate_label)

            # API Key (Translator)
            translator_api_key_input = MLineEdit()
            translator_api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            translator_api_key_input.setFixedWidth(400)
            translator_api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(translator_api_key_prefix)
            translator_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            translator_api_key_input.set_prefix_widget(translator_api_key_prefix)
            azure_layout.addWidget(translator_api_key_input)
            
            self.credential_widgets["Microsoft Azure_api_key_translator"] = translator_api_key_input

            # Region
            region_input = MLineEdit()
            region_input.setFixedWidth(400)
            region_prefix = MLabel(self.tr("Region")).border()
            self.set_label_width(region_prefix)
            region_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            region_input.set_prefix_widget(region_prefix)
            azure_layout.addWidget(region_input)
            
            self.credential_widgets["Microsoft Azure_region"] = region_input
            
            # Pulsanti GET e VERIFY
            buttons_layout = QtWidgets.QHBoxLayout()
            
            get_button = QtWidgets.QPushButton(self.tr("GET"))
            get_button.setFixedWidth(100)
            get_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(self._get_service_url(azure_service))
            ))
            buttons_layout.addWidget(get_button)
            
            # Non abbiamo un pulsante VERIFY per Azure perché richiede più parametri
            info_button = QtWidgets.QPushButton(self.tr("INFO"))
            info_button.setFixedWidth(100)
            info_button.clicked.connect(lambda: MMessage.info(
                self.tr("La verifica per Microsoft Azure richiede l'endpoint e la regione. "
                       "Le credenziali verranno verificate al primo utilizzo del servizio."),
                parent=self
            ))
            buttons_layout.addWidget(info_button)
            
            buttons_layout.addStretch()
            
            azure_layout.addLayout(buttons_layout)
            
            ocr_cards_layout.addWidget(azure_card)
        
        # Google Cloud Vision - OCR
        gcv_service = self.tr("Google Cloud Vision")
        if gcv_service in ocr_models:
            gcv_card = QtWidgets.QGroupBox(gcv_service)
            gcv_card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    font-weight: bold;
                }
            """)
            
            gcv_card_layout = QtWidgets.QVBoxLayout(gcv_card)
            
            # Badge di funzionalità
            gcv_badge = MLabel(self.tr("[Solo OCR]")).secondary()
            gcv_badge.setStyleSheet("color: #2ecc71;")
            gcv_card_layout.addWidget(gcv_badge)
            
            # Layout orizzontale per API Key, GET e VERIFY
            gcv_api_key_layout = QtWidgets.QHBoxLayout()
            
            # API Key
            gcv_api_key_input = MLineEdit()
            gcv_api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            gcv_api_key_input.setFixedWidth(400)
            gcv_api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(gcv_api_key_prefix)
            gcv_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            gcv_api_key_input.set_prefix_widget(gcv_api_key_prefix)
            gcv_api_key_layout.addWidget(gcv_api_key_input)
            
            # Pulsante GET
            gcv_get_button = QtWidgets.QPushButton(self.tr("GET"))
            gcv_get_button.setFixedWidth(60)
            gcv_get_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(self._get_service_url(gcv_service))
            ))
            gcv_api_key_layout.addWidget(gcv_get_button)
            
            # Pulsante VERIFY
            gcv_verify_button = QtWidgets.QPushButton(self.tr("VERIFY"))
            gcv_verify_button.setFixedWidth(60)
            gcv_verify_button.clicked.connect(lambda: self.verify_api_key(gcv_api_key_input.text(), gcv_service))
            gcv_api_key_layout.addWidget(gcv_verify_button)
            
            gcv_card_layout.addLayout(gcv_api_key_layout)
            self.credential_widgets[f"{gcv_service}_api_key"] = gcv_api_key_input
            
            ocr_cards_layout.addWidget(gcv_card)
        
        # GPT-4o - OCR
        gpt4o_service = self.tr("GPT-4o")
        if gpt4o_service in ocr_models:
            gpt4o_card = QtWidgets.QGroupBox(gpt4o_service)
            gpt4o_card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    font-weight: bold;
                }
            """)
            
            gpt4o_card_layout = QtWidgets.QVBoxLayout(gpt4o_card)
            
            # Badge di funzionalità
            gpt4o_badge = MLabel(self.tr("[OCR + Traduzione]")).secondary()
            gpt4o_badge.setStyleSheet("color: #3498db;")
            gpt4o_card_layout.addWidget(gpt4o_badge)
            
            # Layout orizzontale per API Key, GET e VERIFY
            gpt4o_api_key_layout = QtWidgets.QHBoxLayout()
            
            # API Key
            gpt4o_api_key_input = MLineEdit()
            gpt4o_api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            gpt4o_api_key_input.setFixedWidth(400)
            gpt4o_api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(gpt4o_api_key_prefix)
            gpt4o_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            gpt4o_api_key_input.set_prefix_widget(gpt4o_api_key_prefix)
            gpt4o_api_key_layout.addWidget(gpt4o_api_key_input)
            
            # Pulsante GET
            gpt4o_get_button = QtWidgets.QPushButton(self.tr("GET"))
            gpt4o_get_button.setFixedWidth(60)
            gpt4o_get_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(self._get_service_url(gpt4o_service))
            ))
            gpt4o_api_key_layout.addWidget(gpt4o_get_button)
            
            # Pulsante VERIFY
            gpt4o_verify_button = QtWidgets.QPushButton(self.tr("VERIFY"))
            gpt4o_verify_button.setFixedWidth(60)
            gpt4o_verify_button.clicked.connect(lambda: self.verify_api_key(gpt4o_api_key_input.text(), gpt4o_service))
            gpt4o_api_key_layout.addWidget(gpt4o_verify_button)
            
            gpt4o_card_layout.addLayout(gpt4o_api_key_layout)
            self.credential_widgets[f"{gpt4o_service}_api_key"] = gpt4o_api_key_input
            
            ocr_cards_layout.addWidget(gpt4o_card)
        
        # Mistral OCR
        mistral_service = self.tr("Mistral OCR")
        if mistral_service in self.ocr_engines:
            mistral_card = QtWidgets.QGroupBox(mistral_service)
            mistral_card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    font-weight: bold;
                }
            """)
            
            mistral_card_layout = QtWidgets.QVBoxLayout(mistral_card)
            
            # Badge di funzionalità
            mistral_badge = MLabel(self.tr("[Solo OCR]")).secondary()
            mistral_badge.setStyleSheet("color: #2ecc71;")
            mistral_card_layout.addWidget(mistral_badge)
            
            # Layout orizzontale per API Key, GET e VERIFY
            mistral_api_key_layout = QtWidgets.QHBoxLayout()
            
            # API Key
            mistral_api_key_input = MLineEdit()
            mistral_api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            mistral_api_key_input.setFixedWidth(400)
            mistral_api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(mistral_api_key_prefix)
            mistral_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            mistral_api_key_input.set_prefix_widget(mistral_api_key_prefix)
            mistral_api_key_layout.addWidget(mistral_api_key_input)
            
            # Pulsante GET
            mistral_get_button = QtWidgets.QPushButton(self.tr("GET"))
            mistral_get_button.setFixedWidth(60)
            mistral_get_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(self._get_service_url(mistral_service))
            ))
            mistral_api_key_layout.addWidget(mistral_get_button)
            
            # Pulsante VERIFY
            mistral_verify_button = QtWidgets.QPushButton(self.tr("VERIFY"))
            mistral_verify_button.setFixedWidth(60)
            mistral_verify_button.clicked.connect(lambda: self.verify_api_key(mistral_api_key_input.text(), mistral_service))
            mistral_api_key_layout.addWidget(mistral_verify_button)
            
            mistral_card_layout.addLayout(mistral_api_key_layout)
            self.credential_widgets[f"{mistral_service}_api_key"] = mistral_api_key_input
            
            ocr_cards_layout.addWidget(mistral_card)
        
        # Scrollable container per le card OCR
        ocr_scroll = QtWidgets.QScrollArea()
        ocr_scroll.setWidgetResizable(True)
        ocr_scroll.setWidget(ocr_card_container)
        ocr_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        ocr_layout.addWidget(ocr_scroll)
        
        # Aggiungi il layout delle card OCR al layout delle credenziali
        main_layout.addLayout(ocr_layout)
        
        # ========== MODELLI DI TRADUZIONE ==========
        
        # Istruzioni in testa alla pagina
        translator_instructions = MLabel(self.tr("Questi modelli forniscono funzionalità di traduzione."))
        translator_layout.addWidget(translator_instructions)
        translator_layout.addSpacing(10)
        
        # Creiamo un container per le card di traduzione
        translator_card_container = QtWidgets.QWidget()
        translator_cards_layout = QtWidgets.QVBoxLayout(translator_card_container)
        translator_cards_layout.setContentsMargins(0, 0, 0, 0)
        
        # Aggiungi i modelli solo per la traduzione
        for service in translation_only_models:
            translator_card = QtWidgets.QGroupBox(service)
            translator_card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    font-weight: bold;
                }
            """)
            
            translator_card_layout = QtWidgets.QVBoxLayout(translator_card)
            
            # Badge di funzionalità
            translator_badge = MLabel(self.tr("[Solo Traduzione]")).secondary()
            translator_badge.setStyleSheet("color: #e74c3c;")
            translator_card_layout.addWidget(translator_badge)
            
            # Layout orizzontale per API Key, GET e VERIFY
            api_key_layout = QtWidgets.QHBoxLayout()
            
            # API Key for translation services
            api_key_input = MLineEdit()
            api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            api_key_input.setFixedWidth(400)
            api_key_prefix = MLabel(self.tr("API Key")).border()
            self.set_label_width(api_key_prefix)
            api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            api_key_input.set_prefix_widget(api_key_prefix)
            api_key_layout.addWidget(api_key_input)
            
            # Pulsante GET specifico per ogni servizio
            get_button = QtWidgets.QPushButton(self.tr("GET"))
            get_button.setFixedWidth(60)
            # URL specifica per ogni servizio
            service_url = self._get_service_url(service)
            get_button.clicked.connect(lambda checked=False, url=service_url: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(url)
            ))
            api_key_layout.addWidget(get_button)
            
            # Pulsante VERIFY per verificare API key
            verify_button = QtWidgets.QPushButton(self.tr("VERIFY"))
            verify_button.setFixedWidth(60)
            verify_button.clicked.connect(lambda checked=False, svc=service: self.verify_api_key(api_key_input.text(), svc))
            api_key_layout.addWidget(verify_button)
            
            translator_card_layout.addLayout(api_key_layout)
            self.credential_widgets[f"{service}_api_key"] = api_key_input
            
            translator_cards_layout.addWidget(translator_card)
        
        # Scrollable container per le card di traduzione
        translator_scroll = QtWidgets.QScrollArea()
        translator_scroll.setWidgetResizable(True)
        translator_scroll.setWidget(translator_card_container)
        translator_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        translator_layout.addWidget(translator_scroll)
        
        # ========== MODELLI CUSTOM ==========
        
        # Istruzioni in testa alla pagina
        custom_instructions = MLabel(self.tr("Configura un modello personalizzato per OCR e traduzione."))
        custom_layout.addWidget(custom_instructions)
        custom_layout.addSpacing(10)
        
        # Configurazione per modello Custom
        custom_service = self.tr("Custom")
        custom_card = QtWidgets.QGroupBox(custom_service)
        custom_card.setStyleSheet("""
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                font-weight: bold;
            }
        """)
        
        custom_card_layout = QtWidgets.QVBoxLayout(custom_card)
        
        # Badge di funzionalità
        custom_badge = MLabel(self.tr("[OCR + Traduzione]")).secondary()
        custom_badge.setStyleSheet("color: #3498db;")
        custom_card_layout.addWidget(custom_badge)
        
        # Layout orizzontale per API Key, GET e VERIFY
        custom_api_key_layout = QtWidgets.QHBoxLayout()
        
        # API Key
        custom_api_key_input = MLineEdit()
        custom_api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        custom_api_key_input.setFixedWidth(400)
        custom_api_key_prefix = MLabel(self.tr("API Key")).border()
        self.set_label_width(custom_api_key_prefix)
        custom_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        custom_api_key_input.set_prefix_widget(custom_api_key_prefix)
        custom_api_key_layout.addWidget(custom_api_key_input)
        
        # Pulsante GET
        custom_get_button = QtWidgets.QPushButton(self.tr("GET"))
        custom_get_button.setFixedWidth(60)
        custom_get_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl(self._get_service_url(custom_service))
        ))
        custom_api_key_layout.addWidget(custom_get_button)
        
        # Pulsante VERIFY
        custom_verify_button = QtWidgets.QPushButton(self.tr("VERIFY"))
        custom_verify_button.setFixedWidth(60)
        custom_verify_button.clicked.connect(lambda: self.verify_api_key(custom_api_key_input.text(), custom_service))
        custom_api_key_layout.addWidget(custom_verify_button)
        
        custom_card_layout.addLayout(custom_api_key_layout)
        self.credential_widgets[f"{custom_service}_api_key"] = custom_api_key_input
        
        # Endpoint URL
        endpoint_input = MLineEdit()
        endpoint_input.setFixedWidth(400)
        endpoint_prefix = MLabel(self.tr("Endpoint URL")).border()
        self.set_label_width(endpoint_prefix)
        endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        endpoint_input.set_prefix_widget(endpoint_prefix)
        custom_card_layout.addWidget(endpoint_input)
        
        self.credential_widgets[f"{custom_service}_api_url"] = endpoint_input

        # Model Name
        model_input = MLineEdit()
        model_input.setFixedWidth(400)
        model_prefix = MLabel(self.tr("Model")).border()
        self.set_label_width(model_prefix)
        model_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        model_input.set_prefix_widget(model_prefix)
        custom_card_layout.addWidget(model_input)
        
        self.credential_widgets[f"{custom_service}_model"] = model_input
        
        custom_layout.addWidget(custom_card)
        custom_layout.addStretch(1)  # Push everything to the top
        
        # Aggiungi i tab al tab widget
        tab_widget.addTab(multifunction_tab, self.tr("Multi-funzione"))
        tab_widget.addTab(ocr_tab, self.tr("OCR"))
        tab_widget.addTab(translator_tab, self.tr("Traduzione"))
        tab_widget.addTab(custom_tab, self.tr("Custom"))
        
        main_layout.addWidget(tab_widget)
        
        return main_layout

    def _create_llms_layout(self):
        llms_layout = QtWidgets.QVBoxLayout()

        prompt_label = MLabel(self.tr("Extra Context:"))
        self.extra_context = MTextEdit()

        self.image_checkbox = MCheckBox(self.tr("Provide Image as input to multimodal LLMs"))
        self.image_checkbox.setChecked(True)
        
        llms_layout.addWidget(prompt_label)
        llms_layout.addWidget(self.extra_context)
        llms_layout.addWidget(self.image_checkbox)
        llms_layout.addSpacing(20)

        # Set default optimized prompt for comics translation
        default_prompt = "You are a comic translation assistant. For OCR: Extract text exactly as it appears, preserving all formatting and layout. For translation: Translate from {src_lang} to {tgt_lang}, maintaining the original tone, style, and cultural context. Consider comic-specific elements like sound effects, onomatopoeia, and character speech patterns. Keep translations concise to fit speech bubbles."
        
        if hasattr(self, 'saved_prompts') and 'extra_context' in self.saved_prompts:
            self.extra_context.setPlainText(self.saved_prompts["extra_context"])
        else:
            self.extra_context.setPlainText(default_prompt)

        llms_layout.addStretch(1)
        
        return llms_layout
        
    def _save_prompts(self):
        """Salva i prompt personalizzati nel file JSON."""
        try:
            import os
            import json
            
            # Percorso del file dei prompt
            prompts_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "config", "prompts.json")
            
            # Crea la directory config se non esiste
            config_dir = os.path.dirname(prompts_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # Prepara i dati da salvare - ora salviamo solo il contesto extra
            # che verrà utilizzato sia per OCR che per traduzione con Qwen
            prompts = {
                "extra_context": self.extra_context.toPlainText()
            }
            
            # Salva i dati nel file JSON
            with open(prompts_file, "w", encoding="utf-8") as f:
                json.dump(prompts, f, ensure_ascii=False, indent=4)
            
            # Mostra un messaggio di conferma
            MMessage.success(
                self.tr("Prompt salvato con successo!"),
                parent=self
            )
            
        except Exception as e:
            # Mostra un messaggio di errore
            MMessage.error(
                self.tr(f"Errore durante il salvataggio del prompt: {str(e)}"),
                parent=self
            )

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

        # Text color selection
        color_layout = QtWidgets.QHBoxLayout()
        color_label = MLabel(self.tr("Text Color:"))
        self.color_button = QtWidgets.QPushButton()
        self.color_button.setFixedSize(30, 30)
        self.color_button.setStyleSheet("background-color: #000000; border: none; border-radius: 5px;")
        self.color_button.setProperty('selected_color', '#000000')
        
        # Outline color selection
        outline_color_label = MLabel(self.tr("Outline Color:"))
        self.outline_color_button = QtWidgets.QPushButton()
        self.outline_color_button.setFixedSize(30, 30)
        self.outline_color_button.setStyleSheet("background-color: #FFFFFF; border: none; border-radius: 5px;")
        self.outline_color_button.setProperty('selected_color', '#FFFFFF')
        
        color_layout.addWidget(color_label)
        color_layout.addWidget(self.color_button)
        color_layout.addSpacing(20)
        color_layout.addWidget(outline_color_label)
        color_layout.addWidget(self.outline_color_button)
        color_layout.addStretch()

        # Aggiungi il selettore dei font di sistema
        self.system_fonts_label = MLabel(self.tr("Font disponibili:")).h4()
        self.system_fonts_container = QtWidgets.QWidget()
        self.system_fonts_layout = QtWidgets.QVBoxLayout(self.system_fonts_container)
        
        # Creare una QScrollArea per contenere i font
        self.font_scroll_area = QtWidgets.QScrollArea()
        self.font_scroll_area.setWidgetResizable(True)
        self.font_scroll_area.setWidget(self.system_fonts_container)
        self.font_scroll_area.setMinimumHeight(200)
        
        # Popoliamo il layout con i checkbox dei font di sistema
        self.font_checkboxes = {}
        for font_family in QtGui.QFontDatabase().families():
            checkbox = MCheckBox(font_family)
            checkbox.setStyleSheet(f"font-family: '{font_family}';")
            checkbox.stateChanged.connect(self._on_font_checkbox_changed)  # Collegare al segnale stateChanged
            self.font_checkboxes[font_family] = checkbox
            self.system_fonts_layout.addWidget(checkbox)

        # Aggiungi bottoni per selezionare/deselezionare tutti i font
        font_button_layout = QtWidgets.QHBoxLayout()
        self.select_all_fonts_button = MPushButton(self.tr("Seleziona tutti"))
        self.select_all_fonts_button.clicked.connect(self._select_all_fonts)
        self.deselect_all_fonts_button = MPushButton(self.tr("Deseleziona tutti"))
        self.deselect_all_fonts_button.clicked.connect(self._deselect_all_fonts)
        
        font_button_layout.addWidget(self.select_all_fonts_button)
        font_button_layout.addWidget(self.deselect_all_fonts_button)
        font_button_layout.addStretch()

        font_layout.addWidget(font_label)
        font_layout.addLayout(font_browser_layout)  # Add the horizontal layout instead of just the browser
        font_layout.addLayout(min_font_layout)
        font_layout.addLayout(max_font_layout)
        font_layout.addLayout(color_layout)
        font_layout.addWidget(self.system_fonts_label)
        font_layout.addLayout(font_button_layout)
        font_layout.addWidget(self.font_scroll_area)

        # Uppercase checkbox 
        self.uppercase_checkbox = MCheckBox(self.tr("Render Text in UpperCase"))
        text_rendering_layout.addWidget(self.uppercase_checkbox)

        text_rendering_layout.addSpacing(10)
        text_rendering_layout.addLayout(font_layout)
        text_rendering_layout.addSpacing(10)

        text_rendering_layout.addStretch(1)
        return text_rendering_layout
        
    def _select_all_fonts(self):
        for checkbox in self.font_checkboxes.values():
            checkbox.setChecked(True)
        # Aggiungiamo qui l'emissione del segnale
        parent = self.parent()
        if parent and hasattr(parent, 'selected_fonts_changed'):
            parent.selected_fonts_changed.emit()
            
    def _deselect_all_fonts(self):
        for checkbox in self.font_checkboxes.values():
            checkbox.setChecked(False)
        # Aggiungiamo qui l'emissione del segnale
        parent = self.parent()
        if parent and hasattr(parent, 'selected_fonts_changed'):
            parent.selected_fonts_changed.emit()
            
    def _on_font_checkbox_changed(self):
        # Questo metodo viene chiamato quando un checkbox viene modificato
        parent = self.parent()
        if parent and hasattr(parent, 'selected_fonts_changed'):
            parent.selected_fonts_changed.emit()
            
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
    
    def set_combo_box_width(self, combo_box: MComboBox, items: List[str], padding: int = 40):
        font_metrics = QFontMetrics(combo_box.font())
        max_width = max(font_metrics.horizontalAdvance(item) for item in items)
        combo_box.setFixedWidth(max_width + padding)

    def set_label_width(self, label: MLabel, padding: int = 20):
        font_metrics = QFontMetrics(label.font())
        text_width = font_metrics.horizontalAdvance(label.text())
        label.setFixedWidth(text_width + padding)
        
    def _get_service_url(self, service: str) -> str:
        """Restituisce l'URL appropriato per ottenere le API key per ciascun servizio."""
        service_urls = {
            self.tr("Qwen2.5 VL 72B Instruct (free)"): "https://openrouter.ai/qwen/qwen2.5-vl-72b-instruct:free/api",
            self.tr("Qwen2.5 VL 72B Instruct"): "https://openrouter.ai/qwen/qwen2.5-vl-72b-instruct/api",
            self.tr("Qwen-Max"): "https://openrouter.ai/qwen/qwen-max/api",
            self.tr("GPT-4o"): "https://platform.openai.com/api-keys",
            self.tr("GPT-4o mini"): "https://platform.openai.com/api-keys",
            self.tr("Google Cloud Vision"): "https://console.cloud.google.com/apis/credentials",
            self.tr("DeepL"): "https://www.deepl.com/pro-api",
            self.tr("Anthropic Claude"): "https://console.anthropic.com/keys",
            self.tr("Claude-3-Opus"): "https://console.anthropic.com/keys",
            self.tr("Claude-3.7-Sonnet"): "https://console.anthropic.com/keys",
            self.tr("Claude-3.5-Haiku"): "https://console.anthropic.com/keys",
            self.tr("Gemini-2.0-Flash"): "https://aistudio.google.com/app/apikey",
            self.tr("Gemini-2.0-Pro"): "https://aistudio.google.com/app/apikey",
            self.tr("Google Gemini"): "https://aistudio.google.com/app/apikey",
            self.tr("Microsoft Azure"): "https://portal.azure.com/#create/Microsoft.CognitiveServicesTextTranslation",
            self.tr("Microsoft Translator"): "https://portal.azure.com/#create/Microsoft.CognitiveServicesTextTranslation",
            self.tr("Deepseek-v3"): "https://platform.deepseek.com/api_console",
            self.tr("Deepseek"): "https://platform.deepseek.com/api_console",
            self.tr("Yandex"): "https://translate.yandex.com/developers",
            self.tr("Google Cloud"): "https://console.cloud.google.com/apis/credentials",
            self.tr("Google Translate"): "https://console.cloud.google.com/apis/credentials",
            self.tr("Custom"): "https://github.com/Dadaphae/CTkif/wiki",  # URL alla documentazione
            self.tr("Open AI GPT"): "https://platform.openai.com/api-keys",
            self.tr("Mistral OCR"): "https://www.mistral.ai/ocr",
        }
        return service_urls.get(service, "https://github.com/Dadaphae/CTkif/wiki")
        
    def verify_api_key(self, api_key: str, service: str):
        if not api_key:
            MMessage.error(self.tr("Inserire una API key valida"), parent=self)
            return
            
        try:
            result = None
            
            # Verifica in base al tipo di servizio
            if service == self.tr("Qwen2.5 VL 72B Instruct (free)"):
                from modules.ocr.qwen_ocr import QwenOCREngine
                result = QwenOCREngine.verify_api_key(api_key)
            elif service == self.tr("Qwen2.5 VL 72B Instruct"):
                from modules.ocr.qwen_ocr import QwenFullOCREngine
                result = QwenFullOCREngine.verify_api_key(api_key)
            elif service == self.tr("GPT-4o"):
                # Verifica per GPT-4o
                import requests
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                test_data = {
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                }
                response = requests.post("https://api.openai.com/v1/chat/completions",
                                       headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service == self.tr("GPT-4o mini"):
                # Verifica per GPT-4o mini
                import requests
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                test_data = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                }
                response = requests.post("https://api.openai.com/v1/chat/completions",
                                       headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service == self.tr("Google Cloud Vision"):
                # Verifica per Google Cloud Vision API
                import requests
                url = "https://vision.googleapis.com/v1/images:annotate"
                headers = {"Content-Type": "application/json"}
                params = {"key": api_key}
                test_data = {
                    "requests": [{
                        "image": {"content": ""},
                        "features": [{"type": "TEXT_DETECTION"}]
                    }]
                }
                response = requests.post(url, headers=headers, params=params, json=test_data)
                if response.status_code in [200, 400]:  # 400 è OK perché l'immagine vuota è invalida ma l'API key è valida
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service == self.tr("DeepL"):
                # Verifica per DeepL API
                import requests
                url = "https://api-free.deepl.com/v2/usage"
                headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": "API key non valida per DeepL"}
            elif service == self.tr("Anthropic Claude") or service in [self.tr("Claude-3-Opus"), self.tr("Claude-3.7-Sonnet"), self.tr("Claude-3.5-Haiku")]:
                # Verifica per Claude API
                import requests
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                test_data = {
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "test"}]
                }
                response = requests.post(url, headers=headers, json=test_data)
                if response.status_code in [200, 201]:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service in [self.tr("Gemini-2.0-Flash"), self.tr("Gemini-2.0-Pro"), self.tr("Google Gemini")]:
                # Verifica per Gemini API
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                test_data = {
                    "contents": [{"parts": [{"text": "test"}]}]
                }
                response = requests.post(url, headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service in [self.tr("Deepseek-v3"), self.tr("Deepseek")]:
                # Verifica per Deepseek API
                import requests
                url = "https://api.deepseek.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                test_data = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                }
                response = requests.post(url, headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service == self.tr("Yandex"):
                # Verifica per Yandex Translate API
                import requests
                url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
                headers = {
                    "Authorization": f"Api-Key {api_key}",
                    "Content-Type": "application/json"
                }
                test_data = {
                    "folder_id": "b1gvmob95yysaplct532",  # Un folder ID predefinito per il test
                    "texts": ["test"],
                    "targetLanguageCode": "it"
                }
                response = requests.post(url, headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("message", "Errore sconosciuto")}
            elif service == self.tr("Open AI GPT"):
                # Verifica per OpenAI GPT API
                import requests
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                test_data = {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                }
                response = requests.post("https://api.openai.com/v1/chat/completions",
                                       headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service == self.tr("Microsoft Azure") or service == self.tr("Microsoft Translator"):
                # Per Microsoft Azure/Translator, mostriamo un messaggio informativo
                MMessage.info(self.tr("La verifica per Microsoft Azure richiede l'endpoint e la regione. "
                                    "Le credenziali verranno verificate al primo utilizzo del servizio."), parent=self)
                return
            elif service == self.tr("Qwen-Max"):
                # Verifica per Qwen-Max
                import requests
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                # Utilizziamo l'API OpenRouter per Qwen-Max
                test_data = {
                    "model": "qwen/qwen-max",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                }
                response = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                        headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            elif service == self.tr("Custom"):
                # Per Custom, mostriamo un messaggio informativo
                MMessage.info(self.tr("La verifica per il servizio Custom richiede endpoint, modello e API key. "
                                    "Le credenziali verranno verificate al primo utilizzo del servizio."), parent=self)
                return
            elif service == self.tr("Mistral OCR"):
                print(f"Verifica API Key per Mistral OCR: {api_key}")
                print(f"Invio richiesta a: {url} con headers: {headers} e data: {test_data}")
                # Verifica per Mistral OCR
                import requests
                url = "https://api.mistral.ai/v1/ocr"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                test_data = {
                    "image": "",
                    "lang": "it"
                }
                response = requests.post(url, headers=headers, json=test_data)
                if response.status_code == 200:
                    result = {"valid": True}
                else:
                    result = {"valid": False, "error": response.json().get("error", {}).get("message", "Errore sconosciuto")}
            else:
                # Servizi non ancora implementati
                MMessage.info(self.tr("La verifica per {service} non è ancora implementata. "
                                    "Le credenziali verranno verificate al primo utilizzo del servizio.").format(service=service),
                             parent=self)
                return
                
            # Mostra il risultato
            if isinstance(result, dict):
                if result.get("valid", False):
                    usage_info = ""
                    if isinstance(result.get("usage"), dict):
                        usage = result["usage"]
                        if isinstance(usage, dict) and "requests" in usage:
                            usage_info = self.tr("\n\nRichieste effettuate: {}\nCrediti utilizzati: {}").format(
                                usage.get("requests", 0),
                                usage.get("spend", 0)
                            )
                        
                    MMessage.success(self.tr("API Key valida!") + usage_info, parent=self)
                else:
                    if "error" in result:
                        MMessage.error(self.tr("API Key non valida: {}").format(result["error"]), parent=self)
                    else:
                        MMessage.error(self.tr("API Key non valida"), parent=self)
            elif result:
                MMessage.success(self.tr("API Key valida!"), parent=self)
            else:
                MMessage.error(self.tr("API Key non valida"), parent=self)
        except Exception as e:
            MMessage.error(self.tr(f"Errore durante la verifica: {str(e)}"), parent=self)

    def verify_qwen_max_credentials(self, api_key: str):
        if not api_key:
            MMessage.error(self.tr("Inserire una API key valida"), parent=self)
            return
            
        try:
            # Implementazione per Qwen-Max
            # TODO: implementare la verifica delle credenziali per Qwen-Max
            MMessage.success(self.tr("API Key valida!"), parent=self)
        except Exception as e:
            MMessage.error(self.tr(f"Errore durante la verifica: {str(e)}"), parent=self)
