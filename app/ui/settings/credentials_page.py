from PySide6 import QtWidgets, QtCore
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.line_edit import MLineEdit
from ..dayu_widgets.check_box import MCheckBox
from ..dayu_widgets.combo_box import MComboBox
from ..dayu_widgets.browser import MClickBrowserFolderToolButton
from .utils import set_label_width

class CredentialsPage(QtWidgets.QWidget):
    def __init__(self, services: list[str], value_mappings: dict[str, str], parent=None):
        super().__init__(parent)
        self.services = services
        self.value_mappings = value_mappings
        self.credential_widgets: dict[str, MLineEdit] = {}

        # main layout (no internal scroll here — outer settings scroll handles it)
        main_layout = QtWidgets.QVBoxLayout(self)
        content_layout = QtWidgets.QVBoxLayout()

        self.save_keys_checkbox = MCheckBox(self.tr("Save Keys"))
        content_layout.addWidget(self.save_keys_checkbox)
        content_layout.addSpacing(20)

        for service_label in self.services:
            service_layout = QtWidgets.QVBoxLayout()
            service_header = MLabel(service_label).strong()
            service_header.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            service_layout.addWidget(service_header)

            normalized = self.value_mappings.get(service_label, service_label)

            if normalized == "Microsoft Azure":
                # OCR
                ocr_label = MLabel(self.tr("OCR")).secondary()
                service_layout.addWidget(ocr_label)

                ocr_api_key_input = MLineEdit()
                ocr_api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                ocr_api_key_input.setFixedWidth(400)
                ocr_api_key_prefix = MLabel(self.tr("API Key")).border()
                set_label_width(ocr_api_key_prefix)
                ocr_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                ocr_api_key_input.set_prefix_widget(ocr_api_key_prefix)
                service_layout.addWidget(ocr_api_key_input)
                self.credential_widgets["Microsoft Azure_api_key_ocr"] = ocr_api_key_input

                endpoint_input = MLineEdit()
                endpoint_input.setFixedWidth(400)
                endpoint_prefix = MLabel(self.tr("Endpoint URL")).border()
                set_label_width(endpoint_prefix)
                endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                endpoint_input.set_prefix_widget(endpoint_prefix)
                service_layout.addWidget(endpoint_input)
                self.credential_widgets["Microsoft Azure_endpoint"] = endpoint_input

                # Translator
                translate_label = MLabel(self.tr("Translate")).secondary()
                service_layout.addWidget(translate_label)

                translator_api_key_input = MLineEdit()
                translator_api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                translator_api_key_input.setFixedWidth(400)
                translator_api_key_prefix = MLabel(self.tr("API Key")).border()
                set_label_width(translator_api_key_prefix)
                translator_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                translator_api_key_input.set_prefix_widget(translator_api_key_prefix)
                service_layout.addWidget(translator_api_key_input)
                self.credential_widgets["Microsoft Azure_api_key_translator"] = translator_api_key_input

                region_input = MLineEdit()
                region_input.setFixedWidth(400)
                region_prefix = MLabel(self.tr("Region")).border()
                set_label_width(region_prefix)
                region_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                region_input.set_prefix_widget(region_prefix)
                service_layout.addWidget(region_input)
                self.credential_widgets["Microsoft Azure_region"] = region_input

            elif normalized == "Custom":
                api_key_input = MLineEdit()
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                api_key_input.setFixedWidth(400)
                api_key_prefix = MLabel(self.tr("API Key")).border()
                set_label_width(api_key_prefix)
                api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                api_key_input.set_prefix_widget(api_key_prefix)
                service_layout.addWidget(api_key_input)
                self.credential_widgets[f"{normalized}_api_key"] = api_key_input

                endpoint_input = MLineEdit()
                endpoint_input.setFixedWidth(400)
                endpoint_prefix = MLabel(self.tr("Endpoint URL")).border()
                set_label_width(endpoint_prefix)
                endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                endpoint_input.set_prefix_widget(endpoint_prefix)
                service_layout.addWidget(endpoint_input)
                self.credential_widgets[f"{normalized}_api_url"] = endpoint_input

                model_input = MLineEdit()
                model_input.setFixedWidth(400)
                model_prefix = MLabel(self.tr("Model")).border()
                set_label_width(model_prefix)
                model_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                model_input.set_prefix_widget(model_prefix)
                service_layout.addWidget(model_input)
                self.credential_widgets[f"{normalized}_model"] = model_input

                # --- Section Modèle local HuggingFace / Ollama ---
                service_layout.addSpacing(15)
                local_model_section_title = MLabel(self.tr("Modèle local (LLM/Traduction)")).secondary()
                local_model_section_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                service_layout.addWidget(local_model_section_title)
                service_layout.addSpacing(5)

                # Choix du type de modèle
                model_type_combo = MComboBox()
                model_type_combo.addItems(["Seq2Seq (Traduction)", "CausalLM (LLM)", "Ollama"])
                model_type_combo.setCurrentIndex(0)
                model_type_label = MLabel(self.tr("Type de modèle local")).border()
                set_label_width(model_type_label)
                model_type_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                model_type_layout = QtWidgets.QHBoxLayout()
                model_type_layout.addWidget(model_type_label)
                model_type_layout.addWidget(model_type_combo)
                model_type_layout.addStretch(1)
                service_layout.addLayout(model_type_layout)
                # Note: credential_widgets keys must match what settings.py expects or what initialize() uses
                self.credential_widgets[f"{normalized}_local_model_type"] = model_type_combo

                # Chemin modèle local HuggingFace
                local_model_path_input = MLineEdit()
                local_model_path_input.setFixedWidth(320)
                local_model_path_prefix = MLabel(self.tr("Chemin modèle local")).border()
                set_label_width(local_model_path_prefix)
                local_model_path_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                local_model_path_input.set_prefix_widget(local_model_path_prefix)
                
                local_model_folder_btn = MClickBrowserFolderToolButton()
                local_model_folder_btn.setToolTip(self.tr("Sélectionner le dossier du modèle HuggingFace"))
                local_model_folder_btn.setFixedWidth(40)
                local_model_path_layout = QtWidgets.QHBoxLayout()
                local_model_path_layout.addWidget(local_model_path_input)
                local_model_path_layout.addWidget(local_model_folder_btn)
                local_model_path_layout.addStretch(1)
                service_layout.addLayout(local_model_path_layout)
                self.credential_widgets[f"{normalized}_local_transformers_model"] = local_model_path_input
                local_model_folder_btn.sig_folder_changed.connect(lambda folder: local_model_path_input.setText(folder))

                # Champs Ollama
                ollama_url_input = MLineEdit()
                ollama_url_input.setFixedWidth(320)
                ollama_url_prefix = MLabel(self.tr("Ollama URL")).border()
                set_label_width(ollama_url_prefix)
                ollama_url_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                ollama_url_input.set_prefix_widget(ollama_url_prefix)
                
                ollama_model_input = MLineEdit()
                ollama_model_input.setFixedWidth(320)
                ollama_model_prefix = MLabel(self.tr("Nom du modèle Ollama")).border()
                set_label_width(ollama_model_prefix)
                ollama_model_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                ollama_model_input.set_prefix_widget(ollama_model_prefix)
                
                ollama_layout = QtWidgets.QVBoxLayout()
                ollama_layout.addWidget(ollama_url_input)
                ollama_layout.addWidget(ollama_model_input)
                service_layout.addLayout(ollama_layout)
                self.credential_widgets[f"{normalized}_ollama_url"] = ollama_url_input
                self.credential_widgets[f"{normalized}_ollama_model"] = ollama_model_input
                
                ollama_url_input.hide()
                ollama_model_input.hide()

                def on_model_type_changed(idx):
                    is_ollama = (idx == 2)
                    ollama_url_input.setVisible(is_ollama)
                    ollama_model_input.setVisible(is_ollama)
                    local_model_path_input.setVisible(not is_ollama)
                    local_model_folder_btn.setVisible(not is_ollama)
                model_type_combo.currentIndexChanged.connect(on_model_type_changed)

            elif normalized == "Yandex":
                api_key_input = MLineEdit()
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                api_key_input.setFixedWidth(400)
                api_key_prefix = MLabel(self.tr("Secret Key")).border()
                set_label_width(api_key_prefix)
                api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                api_key_input.set_prefix_widget(api_key_prefix)
                service_layout.addWidget(api_key_input)
                self.credential_widgets[f"{normalized}_api_key"] = api_key_input

                folder_id_input = MLineEdit()
                folder_id_input.setFixedWidth(400)
                folder_id_prefix = MLabel(self.tr("Folder ID")).border()
                set_label_width(folder_id_prefix)
                folder_id_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                folder_id_input.set_prefix_widget(folder_id_prefix)
                service_layout.addWidget(folder_id_input)
                self.credential_widgets[f"{normalized}_folder_id"] = folder_id_input

            else:
                api_key_input = MLineEdit()
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                api_key_input.setFixedWidth(400)
                api_key_prefix = MLabel(self.tr("API Key")).border()
                set_label_width(api_key_prefix)
                api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                api_key_input.set_prefix_widget(api_key_prefix)
                service_layout.addWidget(api_key_input)
                self.credential_widgets[f"{normalized}_api_key"] = api_key_input

            content_layout.addLayout(service_layout)
            content_layout.addSpacing(20)

        content_layout.addStretch(1)
        main_layout.addLayout(content_layout)
