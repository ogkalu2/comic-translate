from PySide6 import QtWidgets, QtCore
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.line_edit import MLineEdit
from ..dayu_widgets.check_box import MCheckBox
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

        info_label = MLabel(self.tr(
            "These settings are for advanced users who wish to use their own Custom API endpoints (e.g. Local Language Models) for translation. "
            "For most users, no configuration is needed here."
        )).secondary()
        info_label.setWordWrap(True)
        
        content_layout.addWidget(info_label)
        content_layout.addSpacing(10)
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
                # # Translator
                # translate_label = MLabel(self.tr("Translate")).secondary()
                # service_layout.addWidget(translate_label)

                # translator_api_key_input = MLineEdit()
                # translator_api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                # translator_api_key_input.setFixedWidth(400)
                # translator_api_key_prefix = MLabel(self.tr("API Key")).border()
                # set_label_width(translator_api_key_prefix)
                # translator_api_key_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                # translator_api_key_input.set_prefix_widget(translator_api_key_prefix)
                # service_layout.addWidget(translator_api_key_input)
                # self.credential_widgets["Microsoft Azure_api_key_translator"] = translator_api_key_input

                # region_input = MLineEdit()
                # region_input.setFixedWidth(400)
                # region_prefix = MLabel(self.tr("Region")).border()
                # set_label_width(region_prefix)
                # region_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                # region_input.set_prefix_widget(region_prefix)
                # service_layout.addWidget(region_input)
                # self.credential_widgets["Microsoft Azure_region"] = region_input

            elif normalized == "Ollama":
                # Description for Ollama
                ollama_info = MLabel(self.tr(
                    "Ollama provides free local translation without API costs. "
                    "Install from https://ollama.com and run 'ollama pull gemma2:9b'."
                )).secondary()
                ollama_info.setWordWrap(True)
                service_layout.addWidget(ollama_info)
                service_layout.addSpacing(5)

                model_input = MLineEdit()
                model_input.setPlaceholderText("gemma2:9b")
                model_input.setFixedWidth(400)
                model_prefix = MLabel(self.tr("Model")).border()
                set_label_width(model_prefix)
                model_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                model_input.set_prefix_widget(model_prefix)
                service_layout.addWidget(model_input)
                self.credential_widgets[f"{normalized}_model"] = model_input

                endpoint_input = MLineEdit()
                endpoint_input.setPlaceholderText("http://localhost:11434/v1")
                endpoint_input.setFixedWidth(400)
                endpoint_prefix = MLabel(self.tr("API URL")).border()
                set_label_width(endpoint_prefix)
                endpoint_prefix.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                endpoint_input.set_prefix_widget(endpoint_prefix)
                service_layout.addWidget(endpoint_input)
                self.credential_widgets[f"{normalized}_api_url"] = endpoint_input

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
