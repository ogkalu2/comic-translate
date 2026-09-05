import requests
from PySide6 import QtWidgets, QtCore

from ..dayu_widgets.line_edit import MLineEdit
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.push_button import MPushButton
from ..dayu_widgets.combo_box import MComboBox
from .utils import set_label_width

# Keep the default in sync with CustomOCR.DEFAULT_API_URL.
DEFAULT_API_URL = "http://localhost:11434/v1"


class CustomOCRDialog(QtWidgets.QDialog):
    """Dialog for configuring a single custom OCR provider.

    The provider is an OpenAI-compatible vision API endpoint. Values are
    read/written through the SettingsPage (``get_ocr_credentials`` /
    ``set_ocr_credentials``), which keeps them isolated from the translation
    ``Custom`` service in the Advanced tab.
    """

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(self.tr("Custom OCR Provider"))
        self.setMinimumWidth(520)

        main_layout = QtWidgets.QVBoxLayout(self)

        info_label = MLabel(self.tr(
            "Connect any OpenAI-compatible vision API (e.g. Ollama, LM Studio, "
            "vLLM, or a cloud provider). The base URL should point to the API "
            "root, e.g. http://localhost:11434/v1 — '/chat/completions' is added "
            "automatically."
        )).secondary()
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        main_layout.addSpacing(15)

        # API URL
        url_layout = QtWidgets.QHBoxLayout()
        url_label = MLabel(self.tr("API URL")).border()
        set_label_width(url_label)
        url_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.url_input = MLineEdit()
        self.url_input.setFixedWidth(380)
        self.url_input.set_prefix_widget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addStretch()
        main_layout.addLayout(url_layout)
        main_layout.addSpacing(10)

        # API Key
        key_layout = QtWidgets.QHBoxLayout()
        key_label = MLabel(self.tr("API Key")).border()
        set_label_width(key_label)
        key_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.key_input = MLineEdit()
        self.key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key_input.setFixedWidth(380)
        self.key_input.set_prefix_widget(key_label)
        key_layout.addWidget(self.key_input)
        key_layout.addStretch()
        main_layout.addLayout(key_layout)
        main_layout.addSpacing(10)

        # Model (editable combo) + Load Models button
        model_layout = QtWidgets.QHBoxLayout()
        model_label = MLabel(self.tr("Model")).border()
        set_label_width(model_label)
        model_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.model_combo = MComboBox().small()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.model_combo.setFixedWidth(300)
        self.load_models_button = MPushButton(self.tr("Load Models"))
        self.load_models_button.clicked.connect(self._load_models)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.load_models_button)
        model_layout.addStretch()
        main_layout.addLayout(model_layout)
        model_hint = MLabel(self.tr(
            "The model must support image (vision) input — e.g. llama3.2-vision, "
            "llava, or qwen2.5-vl. Plain text models will return an error."
        )).secondary()
        model_hint.setWordWrap(True)
        main_layout.addWidget(model_hint)
        main_layout.addSpacing(15)

        self.save_checkbox = MCheckBox(self.tr("Save API Key"))
        main_layout.addWidget(self.save_checkbox)
        main_layout.addSpacing(15)
        main_layout.addStretch(1)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        self.cancel_button = MPushButton(self.tr("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button = MPushButton(self.tr("Save"))
        self.ok_button.set_dayu_type(MPushButton.PrimaryType)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        main_layout.addLayout(button_layout)

        self._load()

    def _load(self):
        creds = self.settings.get_ocr_credentials()
        self.url_input.setText(creds.get("api_url") or DEFAULT_API_URL)
        self.key_input.setText(creds.get("api_key") or "")
        saved_model = creds.get("model") or ""
        self.model_combo.clear()
        if saved_model:
            self.model_combo.addItem(saved_model)
        self.model_combo.setCurrentText(saved_model)
        self.save_checkbox.setChecked(bool(creds.get("save_key", False)))

    def _load_models(self):
        """Fetch available models from the endpoint and populate the combo."""
        api_url = self.url_input.text().strip()
        api_key = self.key_input.text()
        if not api_url:
            return

        base = api_url.rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")]
        models_url = f"{base}/models"

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            resp = requests.get(models_url, headers=headers, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            print(f"Custom OCR: failed to load models from {models_url}: {e}")
            return

        items = payload.get("data") or payload.get("models") or []
        ids = []
        for m in items:
            if isinstance(m, dict):
                ids.append(m.get("id") or m.get("name"))
            elif isinstance(m, str):
                ids.append(m)
        ids = [i for i in ids if i]
        if not ids:
            return

        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(ids)
        if current:
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

    def accept(self):
        data = {
            "api_url": self.url_input.text().strip(),
            "api_key": self.key_input.text(),
            "model": self.model_combo.currentText().strip(),
            "save_key": self.save_checkbox.isChecked(),
        }
        self.settings.set_ocr_credentials(data)
        super().accept()
