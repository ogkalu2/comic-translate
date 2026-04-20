from types import SimpleNamespace

import numpy as np

from pipeline.batch_execution_mixin import BatchExecutionMixin
from pipeline.batch_state_mixin import BatchStateMixin


class _FakeSettingsPage:
    def get_llm_settings(self):
        return {"extra_context": ""}

    def get_tool_selection(self, tool_type):
        if tool_type == "translator":
            return "LM Studio"
        raise KeyError(tool_type)


class _FakeRemoteSettingsPage(_FakeSettingsPage):
    def get_tool_selection(self, tool_type):
        if tool_type == "translator":
            return "GPT-4.1"
        raise KeyError(tool_type)


class _FakeCustomLocalSettingsPage(_FakeSettingsPage):
    ui = SimpleNamespace(tr=lambda value: value)

    def get_tool_selection(self, tool_type):
        if tool_type == "translator":
            return "Custom"
        raise KeyError(tool_type)

    def get_credentials(self, _service):
        return {"api_url": "http://127.0.0.1:1234/v1"}


class _FakeTranslator:
    def __init__(self, _main_page, _source_lang, _target_lang):
        self.engine = SimpleNamespace(last_usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})

    def translate(self, blk_list, _image, _extra_context):
        if len(blk_list) > 1:
            raise ValueError("Unterminated string starting at: line 1 column 7 (char 6)")
        blk_list[0].translation = f"tr:{blk_list[0].text}"
        return blk_list


class _FakeCacheManager:
    def _get_translation_cache_key(self, *_args, **_kwargs):
        return "translation-cache-key"


class _FakeBatchExecution(BatchExecutionMixin):
    def __init__(self):
        self.main_page = SimpleNamespace(settings_page=_FakeSettingsPage())
        self.cache_manager = _FakeCacheManager()


class _FakeDoneSettingsPage(_FakeRemoteSettingsPage):
    def is_gpu_enabled(self):
        return False


class _FakeDoneCacheManager:
    def _can_serve_all_blocks_from_ocr_cache(self, *_args, **_kwargs):
        return True

    def _can_serve_all_blocks_from_translation_cache(self, *_args, **_kwargs):
        return True

    def _get_translation_cache_key(self, *_args, **_kwargs):
        return "translation-cache-key"


class _FakeBatchProcessor(BatchExecutionMixin, BatchStateMixin):
    def __init__(self, state):
        self.main_page = SimpleNamespace(
            settings_page=_FakeDoneSettingsPage(),
            image_states={"page.png": state},
            image_patches={},
            image_files=["page.png"],
            t_combo=SimpleNamespace(currentText=lambda: "English"),
        )
        self.cache_manager = _FakeDoneCacheManager()

    def _get_ocr_cache_key_for_page(self, _page):
        return "ocr-cache-key"


def test_batch_translation_falls_back_to_smaller_chunks(monkeypatch):
    import pipeline.batch_execution_mixin as batch_execution_module

    monkeypatch.setattr(batch_execution_module, "Translator", _FakeTranslator)

    worker = _FakeBatchExecution()
    blocks = [
        SimpleNamespace(text="one", translation=""),
        SimpleNamespace(text="two", translation=""),
    ]
    page = SimpleNamespace(
        target_lang="English",
        image=np.zeros((2, 2, 3), dtype=np.uint8),
        blk_list=blocks,
        image_path="page.png",
        _translation_missing_blocks=blocks,
    )

    translated_blk_list, translated_source_blocks, usage, scene_memory = worker._translate_one_page_worker(page)

    assert translated_blk_list is blocks
    assert translated_source_blocks is blocks
    assert [blk.translation for blk in blocks] == ["tr:one", "tr:two"]
    assert usage == {"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6}
    assert scene_memory == ""


def test_lm_studio_translation_is_serial_without_page_to_page_context():
    worker = _FakeBatchExecution()
    prepared_pages = [SimpleNamespace(image_path=f"page_{idx}.png") for idx in range(4)]

    assert worker._get_translation_max_workers(prepared_pages) == 1


def test_custom_lm_studio_url_translation_is_serial_without_page_to_page_context():
    worker = _FakeBatchExecution()
    worker.main_page.settings_page = _FakeCustomLocalSettingsPage()
    prepared_pages = [SimpleNamespace(image_path=f"page_{idx}.png") for idx in range(4)]

    assert worker._get_translation_max_workers(prepared_pages) == 1


def test_remote_translation_batches_without_page_to_page_context():
    worker = _FakeBatchExecution()
    worker.main_page.settings_page = _FakeRemoteSettingsPage()
    prepared_pages = [SimpleNamespace(image_path=f"page_{idx}.png") for idx in range(4)]

    assert worker._get_translation_max_workers(prepared_pages) == 4


def test_previous_page_context_forces_single_worker():
    class _ContextSettingsPage(_FakeSettingsPage):
        def get_llm_settings(self):
            return {
                "extra_context": "",
                "use_previous_page_context": True,
            }

    worker = _FakeBatchExecution()
    worker.main_page.settings_page = _ContextSettingsPage()
    prepared_pages = [SimpleNamespace(image_path=f"page_{idx}.png") for idx in range(4)]

    assert worker._get_translation_max_workers(prepared_pages) == 1


def test_merge_translated_blocks_does_not_restore_obsolete_source_lang():
    worker = _FakeBatchExecution()
    page_blocks = [
        SimpleNamespace(text="one", translation="", source_lang="ja"),
    ]
    original_blocks = [
        page_blocks[0],
    ]
    translated_blocks = [
        SimpleNamespace(text="one sanitized", translation="tr:one", source_lang="en"),
    ]
    page = SimpleNamespace(blk_list=page_blocks)

    worker._merge_translated_blocks(page, original_blocks, translated_blocks)

    assert page_blocks[0].text == "one sanitized"
    assert page_blocks[0].translation == "tr:one"
    assert page_blocks[0].source_lang == "ja"


def test_fully_done_accepts_legacy_stage_state_with_cache_and_render_snapshot():
    block = SimpleNamespace(text="source", translation="target", block_uid="title")
    state = {
        "target_lang": "English",
        "blk_list": [block],
        "pipeline_state": {
            "target_lang": "English",
            "completed_stages": ["detection"],
        },
        "target_render_states": {
            "English": {
                "text_items_state": [
                    {
                        "block_uid": "title",
                        "text": "target",
                    }
                ]
            }
        },
    }
    worker = _FakeBatchProcessor(state)
    page = SimpleNamespace(
        image_path="page.png",
        target_lang="English",
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )

    assert worker._page_is_fully_done(page, "GPT-4.1", "") is True
