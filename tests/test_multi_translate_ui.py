from types import SimpleNamespace

from app.controllers.batch_ui_mixin import BatchUiMixin
from app.ui.main_window.constants import supported_target_languages


class _Controller(BatchUiMixin):
    pass


def test_multi_translate_targets_exclude_russian_and_current_target():
    controller = _Controller()
    controller.lang_mapping = {lang: lang for lang in supported_target_languages}
    controller.reverse_lang_mapping = {lang: lang for lang in supported_target_languages}
    controller.t_combo = SimpleNamespace(currentText=lambda: "Russian")

    targets = controller._multi_translate_targets()

    assert "Russian" not in targets
    assert "English" in targets


def test_multi_translate_targets_support_localized_ui_labels():
    controller = _Controller()
    controller.lang_mapping = {
        "Русский": "Russian",
        "Английский": "English",
        "Японский": "Japanese",
    }
    controller.reverse_lang_mapping = {
        "Russian": "Русский",
        "English": "Английский",
        "Japanese": "Японский",
    }
    controller.t_combo = SimpleNamespace(currentText=lambda: "Русский")

    targets = controller._multi_translate_targets()

    assert "Русский" not in targets
    assert "Английский" in targets
    assert "Японский" in targets
