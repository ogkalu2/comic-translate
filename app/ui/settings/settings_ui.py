import os
from PySide6 import QtWidgets
from PySide6 import QtCore

from ..dayu_widgets.clickable_card import ClickMeta
from ..dayu_widgets.divider import MDivider
from ..dayu_widgets.qt import MPixmap

# New imports for refactored pages
from .personalization_page import PersonalizationPage
from .tools_page import ToolsPage
from .credentials_page import CredentialsPage
from .llms_page import LlmsPage
from .text_rendering_page import TextRenderingPage
from .export_page import ExportPage


current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
font_folder_path = os.path.join(project_root, 'resources', 'fonts')

class CurrentPageStack(QtWidgets.QStackedWidget):
    """A QStackedWidget that reports size based on the current page only.
    This ensures the scroll area uses only the active page's size and
    avoids empty scroll space from larger sibling pages.
    """
    def sizeHint(self):
        w = self.currentWidget()
        if w is not None:
            # Use the current page's hint without forcing a resize,
            # to avoid constraining horizontal expansion.
            return w.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        if w is not None:
            return w.minimumSizeHint()
        return super().minimumSizeHint()

    def hasHeightForWidth(self):
        w = self.currentWidget()
        return w.hasHeightForWidth() if w is not None else False

    def heightForWidth(self, width):
        w = self.currentWidget()
        return w.heightForWidth(width) if w is not None else -1


class SettingsPageUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SettingsPageUI, self).__init__(parent)

        self.credential_widgets = {}
        self.export_widgets = {}

        self.inpainters = ['LaMa', 'AOT']
        self.detectors = ['RT-DETR-v2']
        self.ocr_engines = [self.tr("Default"), self.tr('Microsoft OCR'), self.tr('Google Cloud Vision'), self.tr('Gemini-2.0-Flash'), self.tr('GPT-4.1-mini')]
        self.inpaint_strategy = [self.tr('Resize'), self.tr('Original'), self.tr('Crop')]
        self.themes = [self.tr('Dark'), self.tr('Light')]
        self.alignment = [self.tr("Left"), self.tr("Center"), self.tr("Right")]

        self.credential_services = [self.tr("Custom"), self.tr("Deepseek"), self.tr("Open AI GPT"), self.tr("Microsoft Azure"), self.tr("Google Cloud"), 
                                    self.tr("Google Gemini"), self.tr("DeepL"), self.tr("Anthropic Claude"), self.tr("Yandex"), self.tr("xAI")]
        
        self.supported_translators = [self.tr("GPT-4.1"), self.tr("GPT-4.1-mini"), self.tr("DeepL"), 
                                    self.tr("Claude-4.5-Sonnet"), self.tr("Claude-4.5-Haiku"),
                                    self.tr("Gemini-2.5-Flash"), self.tr("Yandex"), self.tr("Google Translate"),
                                    self.tr("Microsoft Translator"), self.tr("Deepseek-v3"), self.tr("Grok-4"), self.tr("Custom"),]
        
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
            self.tr("Claude-4.5-Sonnet"): "Claude-4.5-Sonnet",
            self.tr("Claude-4.5-Haiku"): "Claude-4.5-Haiku",
            self.tr("Gemini-2.5-Flash"): "Gemini-2.5-Flash",
            self.tr("Gemini-2.5-Pro"): "Gemini-2.5-Pro",
            self.tr("Yandex"): "Yandex",
            self.tr("Google Translate"): "Google Translate",
            self.tr("Microsoft Translator"): "Microsoft Translator",
            self.tr("Grok-4"): "Grok-4",

            # OCR mappings
            self.tr("Default"): "Default",
            self.tr("Microsoft OCR"): "Microsoft OCR",
            self.tr("Google Cloud Vision"): "Google Cloud Vision",

            # Inpainter mappings
            "LaMa": "LaMa",
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
            self.tr("xAI"): "xAI",
        }

        # Create reverse mappings for loading
        self.reverse_mappings = {v: k for k, v in self.value_mappings.items()}

        self._init_ui()

    def _init_ui(self):
        self.stacked_widget = CurrentPageStack()
        # Ensure the right content can expand horizontally
        self.stacked_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        # Instantiate each page widget and keep references as attributes
        self.personalization_page = PersonalizationPage(
            languages=self.languages,
            themes=self.themes,
            parent=self,
        )
        self.tools_page = ToolsPage(
            translators=self.supported_translators,
            ocr_engines=self.ocr_engines,
            detectors=self.detectors,
            inpainters=self.inpainters,
            inpaint_strategy=self.inpaint_strategy,
            parent=self,
        )
        self.credentials_page = CredentialsPage(
            services=self.credential_services,
            value_mappings=self.value_mappings,
            parent=self,
        )
        self.llms_page = LlmsPage(parent=self)
        self.text_rendering_page = TextRenderingPage(parent=self)
        self.export_page = ExportPage(parent=self)

        # Backward-compatible attribute proxies for existing SettingsPage references
        # Personalization
        self.lang_combo = self.personalization_page.lang_combo
        self.theme_combo = self.personalization_page.theme_combo

        # Tools
        self.translator_combo = self.tools_page.translator_combo
        self.ocr_combo = self.tools_page.ocr_combo
        self.detector_combo = self.tools_page.detector_combo
        self.inpainter_combo = self.tools_page.inpainter_combo
        self.inpaint_strategy_combo = self.tools_page.inpaint_strategy_combo
        self.resize_spinbox = self.tools_page.resize_spinbox
        self.crop_margin_spinbox = self.tools_page.crop_margin_spinbox
        self.crop_trigger_spinbox = self.tools_page.crop_trigger_spinbox
        self.use_gpu_checkbox = self.tools_page.use_gpu_checkbox

        # Credentials
        self.save_keys_checkbox = self.credentials_page.save_keys_checkbox
        self.credential_widgets = self.credentials_page.credential_widgets

        # LLMs
        self.image_checkbox = self.llms_page.image_checkbox
        self.extra_context = self.llms_page.extra_context
        self.temp_slider = self.llms_page.temp_slider
        self.temp_edit = self.llms_page.temp_edit
        self.top_p_slider = self.llms_page.top_p_slider
        self.top_p_edit = self.llms_page.top_p_edit
        self.max_tokens_slider = self.llms_page.max_tokens_slider
        self.max_tokens_edit = self.llms_page.max_tokens_edit

        # Text rendering
        self.min_font_spinbox = self.text_rendering_page.min_font_spinbox
        self.max_font_spinbox = self.text_rendering_page.max_font_spinbox
        self.font_browser = self.text_rendering_page.font_browser
        self.uppercase_checkbox = self.text_rendering_page.uppercase_checkbox

        # Export
        self.raw_text_checkbox = self.export_page.raw_text_checkbox
        self.translated_text_checkbox = self.export_page.translated_text_checkbox
        self.inpainted_image_checkbox = self.export_page.inpainted_image_checkbox
        self.export_widgets = self.export_page.export_widgets
        self.from_file_types = self.export_page.from_file_types

        # Add pages to stacked widget (order must match navbar order)
        self.stacked_widget.addWidget(self.personalization_page)
        self.stacked_widget.addWidget(self.tools_page)
        self.stacked_widget.addWidget(self.credentials_page)
        self.stacked_widget.addWidget(self.llms_page)
        self.stacked_widget.addWidget(self.text_rendering_page)
        self.stacked_widget.addWidget(self.export_page)

        settings_layout = QtWidgets.QHBoxLayout()
        
        # Create a separate scroll area for the left navbar
        navbar_scroll = QtWidgets.QScrollArea()
        navbar_scroll.setWidget(self._create_navbar_widget())
        navbar_scroll.setWidgetResizable(True)
        navbar_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        navbar_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        navbar_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Keep navbar at a reasonable width without over-constraining layout
        navbar_scroll.setMinimumWidth(200)
        navbar_scroll.setMaximumWidth(260)
        
        settings_layout.addWidget(navbar_scroll)
        settings_layout.addWidget(MDivider(orientation=QtCore.Qt.Orientation.Vertical))

        # Make only the right-side content scrollable so the left navbar
        # remains fixed and doesn't scroll when the content is scrolled.
        self.content_scroll = QtWidgets.QScrollArea()
        self.content_scroll.setWidget(self.stacked_widget)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Allow the scroll area to take available space
        self.content_scroll.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        settings_layout.addWidget(self.content_scroll, 1)
        settings_layout.setContentsMargins(3, 3, 3, 3)

        # Connect to stacked widget page changes to ensure scroll area recalculates
        self.stacked_widget.currentChanged.connect(self._on_page_changed)

        self.setLayout(settings_layout)

    def _create_navbar_widget(self):
        """Create the navbar as a widget that can be scrolled."""
        navbar_widget = QtWidgets.QWidget()
        navbar_layout = QtWidgets.QVBoxLayout(navbar_widget)
        navbar_layout.setContentsMargins(5, 5, 5, 5)

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
        return navbar_widget

    def on_nav_clicked(self, index: int, clicked_nav: ClickMeta):
        # Remove highlight from the previously highlighted nav item
        if self.current_highlighted_nav:
            self.current_highlighted_nav.set_highlight(False)

        # Highlight the clicked nav item
        clicked_nav.set_highlight(True)
        self.current_highlighted_nav = clicked_nav

        # Set the current index of the stacked widget
        self.stacked_widget.setCurrentIndex(index)
        # Update geometry so scroll range recalculates for the new page
        self.stacked_widget.updateGeometry()
        # Reset scroll position to top for a better UX
        self.content_scroll.verticalScrollBar().setValue(0)

    def _on_page_changed(self, index):
        """Handle page changes to ensure scroll area recalculates properly."""
        # Force the stacked widget to update its size hint
        self.stacked_widget.updateGeometry()
        # Force the scroll area to recalculate
        self.content_scroll.widget().updateGeometry()
        self.content_scroll.updateGeometry()
        # Reset scroll position
        self.content_scroll.verticalScrollBar().setValue(0)
