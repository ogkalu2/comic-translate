from types import SimpleNamespace

import numpy as np

from app.controllers.text_scene_edit_mixin import TextSceneEditMixin
from app.controllers.text_state_mixin import TextStateMixin
from pipeline.cache_manager import CacheManager
from pipeline.translation_context import build_translation_prompt_context


class _FakeTextEdit:
    def __init__(self, text: str):
        self._text = text

    def toPlainText(self) -> str:
        return self._text


class _FakeTextItem:
    def __init__(self):
        self.source_text = ""

    def set_source_text(self, text: str):
        self.source_text = text


class _FakeSettingsPage:
    def get_tool_selection(self, name: str) -> str:
        return {
            "ocr": "OCR Engine",
            "translator": "Translator Engine",
        }[name]

    def get_llm_settings(self) -> dict:
        return {"extra_context": ""}

    def is_gpu_enabled(self) -> bool:
        return False


class _FakeImageController:
    def __init__(self, image: np.ndarray):
        self._image = image

    def load_original_image(self, _file_path: str):
        return self._image


class _FakeStageNav:
    def __init__(self):
        self.invalidated_paths = []

    def invalidate_for_source_text_edit(self, file_path: str):
        self.invalidated_paths.append(file_path)


class _FakeTargetCombo:
    def __init__(self, text: str):
        self._text = text

    def currentText(self) -> str:
        return self._text


class _FakeController(TextStateMixin, TextSceneEditMixin):
    def __init__(self, main):
        self.main = main
        self._last_target_lang = ""


def test_source_text_edit_does_not_refresh_translation_cache_with_stale_translation():
    file_path = "page-1.png"
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    cache_manager = CacheManager()
    block = SimpleNamespace(
        text="old source",
        translation="old translation",
        xyxy=(1, 2, 10, 12),
        angle=0,
        block_uid="block-1",
    )
    text_item = _FakeTextItem()
    stage_nav = _FakeStageNav()

    main = SimpleNamespace(
        curr_tblock=block,
        curr_tblock_item=text_item,
        s_text_edit=_FakeTextEdit("new source"),
        t_text_edit=_FakeTextEdit("old translation"),
        curr_img_idx=0,
        image_files=[file_path],
        image_ctrl=_FakeImageController(image),
        pipeline=SimpleNamespace(cache_manager=cache_manager),
        settings_page=_FakeSettingsPage(),
        t_combo=_FakeTargetCombo("English"),
        stage_nav_ctrl=stage_nav,
        dirty_calls=0,
    )

    def _mark_project_dirty():
        main.dirty_calls += 1

    main.mark_project_dirty = _mark_project_dirty

    controller = _FakeController(main)
    _prompt_context, cache_signature = build_translation_prompt_context(
        main,
        file_path,
        "English",
        llm_settings=main.settings_page.get_llm_settings(),
    )

    translation_key = cache_manager._get_translation_cache_key(
        image,
        "",
        "English",
        "Translator Engine",
        cache_signature,
    )
    cache_manager.update_translation_cache_for_block(translation_key, block)

    controller.update_text_block()

    cached_entry = cache_manager.translation_cache[translation_key]["block-1"]
    assert block.text == "new source"
    assert text_item.source_text == "new source"
    assert cached_entry["source_text"] == "old source"
    assert cached_entry["translation"] == "old translation"
    assert cache_manager._get_cached_translation_for_block(translation_key, block) is None
    assert stage_nav.invalidated_paths == [file_path]
    assert main.dirty_calls == 1
