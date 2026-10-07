import json
import logging

from PySide6 import QtWidgets, QtCore
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.text_edit import MTextEdit
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.push_button import MPushButton
from .utils import create_title_and_combo
from modules.translation.presets import BUILTIN_GLOSSARIES, build_extra_context, parse_glossary, validate_glossary


logger = logging.getLogger(__name__)

class LlmsPage(QtWidgets.QWidget):
    DEFAULT_EXTRA_CONTEXT_LIMIT = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extra_context_limit: int | None = self.DEFAULT_EXTRA_CONTEXT_LIMIT
        self._glossary_settings = QtCore.QSettings("ComicLabs", "ComicTranslate")
        self._custom_glossaries = self._load_custom_glossaries()

        v = QtWidgets.QVBoxLayout(self)
        main_layout = QtWidgets.QHBoxLayout()

        self.image_checkbox = MCheckBox()
        self.set_image_context_credits(1)
        self.image_checkbox.setChecked(False)

        # Left
        left_layout = QtWidgets.QVBoxLayout()
        prompt_label = MLabel(self.tr("Extra Context:"))
        self.extra_context = MTextEdit()
        self.extra_context.setMinimumHeight(200)
        left_layout.addWidget(prompt_label)
        left_layout.addWidget(self.extra_context)
        left_layout.addWidget(self.image_checkbox)
        left_layout.addStretch(1)

        # Right
        right_layout = QtWidgets.QVBoxLayout()

        right_layout.addWidget(MLabel(self.tr("Translation presets")).h4())
        hint = MLabel(self.tr("For LLM translators. Choose a glossary matching your translation languages. Apply to load editable instructions into Extra Context."))
        hint.setWordWrap(True)
        right_layout.addWidget(hint)

        glossary_widget, self.glossary_combo = create_title_and_combo(self.tr("Name glossary"), [], h4=False)
        self.glossary_combo.setAccessibleName(self.tr("Name glossary"))
        self.glossary_combo.setMinimumContentsLength(18)
        self.glossary_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.glossary_combo.addItem(self.tr("No glossary"), None)
        builtin_names = (self.tr("Marvel (Mainland China)"), self.tr("Marvel (Taiwan)"), self.tr("Marvel (Hong Kong)"))
        for name, glossary in zip(builtin_names, BUILTIN_GLOSSARIES):
            self.glossary_combo.addItem(name, glossary)
        for glossary in self._custom_glossaries:
            self.glossary_combo.addItem(glossary["name"], glossary)
        right_layout.addWidget(glossary_widget)

        self.import_glossary_button = MPushButton(self.tr("Import glossary (JSON)…")).small()
        right_layout.addWidget(self.import_glossary_button)
        style_widget, self.style_combo = create_title_and_combo(self.tr("Dialogue style"), [], h4=False)
        self.style_combo.setAccessibleName(self.tr("Dialogue style"))
        for label, key in ((self.tr("No style instructions"), "none"),
                           (self.tr("Faithful to original"), "faithful"),
                           (self.tr("Natural dialogue"), "natural")):
            self.style_combo.addItem(label, key)
        right_layout.addWidget(style_widget)
        self.apply_preset_button = MPushButton(self.tr("Apply to Extra Context")).small()
        right_layout.addWidget(self.apply_preset_button)
        self.preset_info = MLabel()
        self.preset_info.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.preset_info.setWordWrap(True)
        right_layout.addWidget(self.preset_info)
        right_layout.addStretch(1)

        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 2)

        v.addLayout(main_layout)
        v.addStretch(1)

        self.extra_context.textChanged.connect(self._limit_extra_context)
        self.glossary_combo.currentIndexChanged.connect(self._update_preset_info)
        self.style_combo.currentIndexChanged.connect(self._update_preset_info)
        self.apply_preset_button.clicked.connect(self._apply_preset)
        self.import_glossary_button.clicked.connect(self._import_glossary)
        self._update_preset_info()

    def _load_custom_glossaries(self) -> list[dict]:
        raw = self._glossary_settings.value("translation_glossaries", "[]")
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Saved glossaries must be a list.")
            return [validate_glossary(glossary) for glossary in data]
        except (TypeError, ValueError) as error:
            logger.warning("Could not load saved translation glossaries: %s", error)
            return []

    def _preset_context(self) -> str:
        return build_extra_context(self.glossary_combo.currentData(), self.style_combo.currentData())

    def _update_preset_info(self):
        context = self._preset_context()
        self.apply_preset_button.setEnabled(bool(context))
        self.glossary_combo.setToolTip(self.glossary_combo.currentText())
        if self._extra_context_limit is None:
            info = self.tr("Preset: {count} characters (Custom: no limit).").format(count=len(context))
        else:
            info = self.tr("Preset: {count} / {limit} characters.").format(count=len(context), limit=self._extra_context_limit)
        glossary = self.glossary_combo.currentData()
        if glossary is not None:
            info = f"{glossary['source_language']} → {glossary['target_language']}\n{info}"
        self.preset_info.setText(info)

    def _apply_preset(self):
        context = self._preset_context()
        if not context:
            return
        if self._extra_context_limit is not None and len(context) > self._extra_context_limit:
            QtWidgets.QMessageBox.warning(self, self.tr("Preset too long"),
                self.tr("This preset exceeds the {limit}-character limit. Use a smaller glossary or select the Custom translator. Extra Context was not changed.").format(limit=self._extra_context_limit))
            return
        current = self.extra_context.toPlainText()
        if current.strip() and current != context:
            answer = QtWidgets.QMessageBox.question(self, self.tr("Replace Extra Context?"),
                self.tr("Applying this preset will replace your current Extra Context. Continue?"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.extra_context.setPlainText(context)

    def _import_glossary(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, self.tr("Import glossary"), "", self.tr("JSON files (*.json)"))
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as stream:
                glossary = parse_glossary(stream.read())
            if any(glossary["name"] == item["name"] for item in BUILTIN_GLOSSARIES):
                raise ValueError("This name is reserved for a built-in glossary. Choose another name in the JSON file.")
        except (OSError, ValueError, RecursionError) as error:
            QtWidgets.QMessageBox.warning(self, self.tr("Cannot import glossary"), str(error))
            return

        existing = next((item for item in self._custom_glossaries if item["name"] == glossary["name"]), None)
        if existing is not None:
            answer = QtWidgets.QMessageBox.question(self, self.tr("Replace glossary?"),
                self.tr("A glossary named {name} already exists. Replace it?").format(name=glossary["name"]),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        glossaries = [item for item in self._custom_glossaries if item["name"] != glossary["name"]] + [glossary]
        self._glossary_settings.setValue("translation_glossaries", json.dumps(glossaries, ensure_ascii=False))
        self._glossary_settings.sync()
        if self._glossary_settings.status() != QtCore.QSettings.Status.NoError:
            QtWidgets.QMessageBox.warning(self, self.tr("Cannot save glossary"), self.tr("Could not save the glossary to application settings."))
            return
        self._custom_glossaries = glossaries
        if existing is not None:
            for index in range(1 + len(BUILTIN_GLOSSARIES), self.glossary_combo.count()):
                if self.glossary_combo.itemData(index)["name"] == glossary["name"]:
                    self.glossary_combo.removeItem(index)
                    break
        self.glossary_combo.addItem(glossary["name"], glossary)
        self.glossary_combo.setCurrentIndex(self.glossary_combo.count() - 1)

    def set_extra_context_unlimited(self, enabled: bool) -> None:
        self._extra_context_limit = None if enabled else self.DEFAULT_EXTRA_CONTEXT_LIMIT
        self._limit_extra_context()
        self._update_preset_info()

    def set_image_context_credits(self, credits: int) -> None:
        unit = "Credit" if credits == 1 else "Credits"
        self.image_checkbox.setText(f"{self.tr('Provide Image as Input to AI')} (+{credits} {unit})")

    def _limit_extra_context(self):
        max_length = self._extra_context_limit
        if max_length is None:
            return
        text = self.extra_context.toPlainText()
        if len(text) > max_length:
            # Preserve cursor position
            cursor = self.extra_context.textCursor()
            position = cursor.position()
            
            # Truncate
            self.extra_context.setPlainText(text[:max_length])
            
            # Restore cursor (clamped to end)
            new_position = min(position, max_length)
            cursor.setPosition(new_position)
            self.extra_context.setTextCursor(cursor)
