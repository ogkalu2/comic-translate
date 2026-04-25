from types import SimpleNamespace

import numpy as np

from pipeline.batch_processor import BatchProcessor
from pipeline.stage_state import is_stage_available


class _FakeSettingsPage:
    def get_batch_settings(self):
        return {"batch_size": 1, "ocr_batch_size": 1}


def test_prepare_text_stages_marks_detection_and_ocr_ready(monkeypatch):
    file_path = "page-1.png"
    main_page = SimpleNamespace(
        settings_page=_FakeSettingsPage(),
        image_states={file_path: {}},
        image_patches={},
        image_files=[file_path],
        curr_img_idx=0,
        blk_list=[],
        t_combo=SimpleNamespace(currentText=lambda: "English"),
        lang_mapping={},
        file_handler=SimpleNamespace(archive_info=[]),
    )
    block_detection = SimpleNamespace(
        block_detector_cache=None,
        _serialize_rectangles_from_blocks=lambda blk_list: [
            {"block_uid": blk.block_uid, "rect": tuple(blk.xyxy)}
            for blk in blk_list
        ],
    )
    worker = BatchProcessor(
        main_page,
        cache_manager=SimpleNamespace(),
        block_detection_handler=block_detection,
        inpainting_handler=SimpleNamespace(inpaint_pages_from_states=lambda _paths: []),
        ocr_handler=SimpleNamespace(),
    )

    def _load_page(page, _total_images):
        page.image = np.zeros((8, 8, 3), dtype=np.uint8)
        return page

    def _reload_page_image(page):
        page.image = np.zeros((8, 8, 3), dtype=np.uint8)
        return page

    def _run_chunk_detection(pages, _total_images):
        for page in pages:
            page.blk_list = [
                SimpleNamespace(
                    xyxy=(1, 2, 6, 7),
                    angle=0.0,
                    tr_origin_point=(0.0, 0.0),
                    block_uid="blk-1",
                    text="hello",
                    translation="",
                )
            ]
        return pages

    def _run_chunk_ocr(pages, _total_images):
        for page in pages:
            page.ocr_cache_key = "ocr-cache-key"
        return pages

    monkeypatch.setattr(worker, "_load_page", _load_page)
    monkeypatch.setattr(worker, "_reload_page_image", _reload_page_image)
    monkeypatch.setattr(worker, "_run_chunk_detection", _run_chunk_detection)
    monkeypatch.setattr(worker, "_run_chunk_ocr", _run_chunk_ocr)

    updated_paths = worker.prepare_text_stages([file_path])
    state = main_page.image_states[file_path]

    assert updated_paths == [file_path]
    assert len(state["blk_list"]) == 1
    assert state["viewer_state"]["rectangles"] == [{"block_uid": "blk-1", "rect": (1, 2, 6, 7)}]
    assert state["pipeline_state"]["ocr_cache_key"] == "ocr-cache-key"
    assert is_stage_available(state, "detect") is True
    assert is_stage_available(state, "ocr") is True


def test_release_inpainting_before_translation_clears_cached_inpainter(monkeypatch):
    inpainting_handler = SimpleNamespace(
        inpainter_cache=object(),
        cached_inpainter_key="LaMa",
    )
    worker = BatchProcessor(
        SimpleNamespace(),
        cache_manager=SimpleNamespace(),
        block_detection_handler=SimpleNamespace(),
        inpainting_handler=inpainting_handler,
        ocr_handler=SimpleNamespace(),
    )
    trimmed = []
    monkeypatch.setattr(worker, "_trim_runtime_memory", lambda: trimmed.append(True))

    worker._release_inpainting_before_translation()

    assert inpainting_handler.inpainter_cache is None
    assert inpainting_handler.cached_inpainter_key is None
    assert trimmed == [True]
