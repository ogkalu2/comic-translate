"""Cached client-capability catalog fetched from the Comic Translate API."""

import json
import logging
import threading
from typing import Any

import requests
from PySide6.QtCore import QObject, QSettings, Signal

from app.account.config import API_BASE_URL
from modules.utils.language_utils import language_codes

logger = logging.getLogger(__name__)

_SETTINGS_KEY = "client_catalog/json"
_SCHEMA_VERSION = 1


def _fallback_rendering(language: str) -> dict[str, bool | str]:
    return {
        "direction": "rtl" if language in {"Arabic", "Hebrew", "Persian"} else "ltr",
        "no_space": language in {"Japanese", "Simplified Chinese", "Traditional Chinese", "Thai"},
        "vertical": language in {"Japanese", "Simplified Chinese", "Traditional Chinese"},
    }


class ClientCatalog(QObject):
    """Provides a bundled fallback, persisted cache, and non-blocking refresh."""

    updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("ComicLabs", "ComicTranslate")

    @staticmethod
    def fallback() -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "translators": [
                {"id": "Gemini-3.1-Flash-Lite", "label": "Gemini-3.1-Flash-Lite", "credits": 1},
                {"id": "GPT-4.1", "label": "GPT-4.1", "credits": 3},
                {"id": "GPT-4.1-mini", "label": "GPT-4.1-mini", "credits": 1},
                {"id": "Claude-4.6-Sonnet", "label": "Claude-4.6-Sonnet", "credits": 3},
                {"id": "Claude-4.5-Haiku", "label": "Claude-4.5-Haiku", "credits": 1},
                {"id": "Deepseek", "label": "Deepseek", "credits": 1},
            ],
            "ocr_models": [
                {"id": "Default", "label": "Default", "credits": 0},
                {"id": "Microsoft OCR", "label": "Microsoft OCR", "credits": 1},
                {"id": "Gemini-2.5-Flash-Lite", "label": "Gemini-2.5-Flash-Lite", "credits": 1},
            ],
            "image_context_credits": 1,
            "target_languages": [
                {"value": value, "label": label, "code": language_codes[value], "rendering": _fallback_rendering(value)} for value, label in [
                    ("English", "English"), ("Korean", "한국어"), ("Japanese", "日本語"),
                    ("French", "Français"), ("Simplified Chinese", "简体中文"),
                    ("Traditional Chinese", "繁體中文"), ("Russian", "Русский"), ("German", "Deutsch"),
                    ("Dutch", "Nederlands"), ("Spanish", "Español"), ("Italian", "Italiano"),
                    ("Turkish", "Türkçe"), ("Polish", "Polski"), ("Portuguese", "Português"),
                    ("Brazilian Portuguese", "Português (Brasil)"), ("Thai", "ไทย"), ("Vietnamese", "Tiếng Việt"),
                    ("Hungarian", "Magyar"), ("Indonesian", "Bahasa Indonesia"), ("Finnish", "Suomi"),
                    ("Arabic", "العربية"), ("Hebrew", "עברית"), ("Czech", "Čeština"),
                    ("Croatian", "Hrvatski"), ("Persian", "فارسی"), ("Romanian", "Română"), ("Mongolian", "Монгол"),
                ]
            ],
        }

    def load(self) -> dict[str, Any]:
        raw = self._settings.value(_SETTINGS_KEY, "")
        try:
            catalog = json.loads(raw) if raw else None
        except (TypeError, json.JSONDecodeError):
            catalog = None
        return catalog if self._is_valid(catalog) else self.fallback()

    def refresh_async(self) -> None:
        threading.Thread(target=self._refresh, name="client-catalog", daemon=True).start()

    def _refresh(self) -> None:
        try:
            response = requests.get(f"{API_BASE_URL}/api/v1/client-catalog", timeout=5)
            response.raise_for_status()
            catalog = response.json()
            if not self._is_valid(catalog):
                raise ValueError("unsupported or malformed catalog")
            # QSettings instances must not be shared across threads.
            QSettings("ComicLabs", "ComicTranslate").setValue(
                _SETTINGS_KEY, json.dumps(catalog, separators=(",", ":"))
            )
            self.updated.emit(catalog)
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.info("Using cached client catalog: %s", exc)

    @staticmethod
    def _is_valid(catalog: Any) -> bool:
        return (
            isinstance(catalog, dict)
            and catalog.get("schema_version") == _SCHEMA_VERSION
            and isinstance(catalog.get("translators"), list)
            and isinstance(catalog.get("ocr_models"), list)
            and isinstance(catalog.get("image_context_credits"), int)
            and isinstance(catalog.get("target_languages"), list)
            and all(isinstance(item, dict) and isinstance(item.get("value"), str) and isinstance(item.get("label"), str)
                    and isinstance(item.get("code"), str)
                    and (
                        "rendering" not in item or (
                            isinstance(item["rendering"], dict)
                            and item["rendering"].get("direction") in {"ltr", "rtl"}
                            and isinstance(item["rendering"].get("no_space"), bool)
                            and isinstance(item["rendering"].get("vertical"), bool)
                        )
                    )
                    for item in catalog.get("target_languages", []))
        )
