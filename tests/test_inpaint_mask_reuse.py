import os
from types import SimpleNamespace

import numpy as np

from modules.utils import image_utils as image_utils_module
from modules.utils.textblock import TextBlock
from pipeline import inpainting as inpainting_module
from pipeline.batch_state_mixin import BatchStateMixin
from pipeline.inpainting import InpaintingHandler
from pipeline.page_state import get_runtime_patches, sync_inpaint_cache_from_image_patches
from pipeline.stage_state import mark_clean_ready


def test_generate_mask_reuses_precomputed_inpaint_bboxes(monkeypatch):
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    block = TextBlock(
        text_bbox=np.array([10, 10, 20, 20]),
        text="segment",
        inpaint_bboxes=[[12, 13, 18, 19]],
    )

    def _unexpected_redetect(*_args, **_kwargs):
        raise AssertionError("generate_mask should reuse precomputed inpaint_bboxes")

    monkeypatch.setattr(image_utils_module, "get_inpaint_bboxes", _unexpected_redetect)

    mask = image_utils_module.generate_mask(image, [block], default_padding=1)

    assert np.count_nonzero(mask) > 0
    assert np.count_nonzero(mask[13:19, 12:18]) > 0


def test_generate_mask_from_saved_strokes_prefers_saved_segment_bboxes(monkeypatch):
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    captured = {}

    def _unexpected_redetect(*_args, **_kwargs):
        raise AssertionError("saved segment_bboxes should be reused before re-detecting content")

    def _fake_generate_mask(img, blk_list, default_padding=5, *, force_default_padding=False):
        captured["inpaint_bboxes"] = np.asarray(blk_list[0].inpaint_bboxes).tolist()
        captured["default_padding"] = default_padding
        captured["force_default_padding"] = force_default_padding
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        for x1, y1, x2, y2 in captured["inpaint_bboxes"]:
            mask[y1:y2, x1:x2] = 255
        return mask

    monkeypatch.setattr(inpainting_module, "get_inpaint_bboxes", _unexpected_redetect)
    monkeypatch.setattr(inpainting_module, "generate_mask", _fake_generate_mask)

    handler = InpaintingHandler(SimpleNamespace(image_viewer=None))
    stroke = {
        "segment_meta": {
            "text_bbox": [10, 10, 20, 20],
            "bubble_xyxy": None,
            "text_class": "text_bubble",
        },
        "segment_bboxes": [[12, 13, 18, 19]],
    }

    mask = handler._generate_mask_from_saved_strokes([stroke], image)

    assert captured["inpaint_bboxes"] == [[12, 13, 18, 19]]
    assert captured["default_padding"] == inpainting_module.AUTO_SEGMENT_MASK_PADDING
    assert captured["force_default_padding"] is True
    assert np.count_nonzero(mask) > 0


def test_build_mask_from_blocks_uses_expanded_auto_segment_padding(monkeypatch):
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    block = TextBlock(
        text_bbox=np.array([10, 10, 20, 20]),
        text="segment",
        inpaint_bboxes=[[12, 13, 18, 19]],
    )
    captured = {}

    def _fake_generate_mask(img, blk_list, default_padding=5, *, force_default_padding=False):
        captured["default_padding"] = default_padding
        captured["force_default_padding"] = force_default_padding
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        mask[10:20, 10:20] = 255
        return mask

    monkeypatch.setattr(inpainting_module, "generate_mask", _fake_generate_mask)

    handler = InpaintingHandler(SimpleNamespace(image_viewer=None))
    mask = handler.build_mask_from_blocks(image, [block])

    assert captured["default_padding"] == inpainting_module.AUTO_SEGMENT_MASK_PADDING
    assert captured["force_default_padding"] is True
    assert np.count_nonzero(mask) > 0


def test_generate_mask_forced_padding_changes_latin_segment_mask_size():
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    small_block = TextBlock(
        text_bbox=np.array([20, 20, 30, 30]),
        text="latin segment",
        inpaint_bboxes=[[22, 22, 27, 27]],
    )
    large_block = TextBlock(
        text_bbox=np.array([20, 20, 30, 30]),
        text="latin segment",
        inpaint_bboxes=[[22, 22, 27, 27]],
    )

    small_mask = image_utils_module.generate_mask(
        image,
        [small_block],
        default_padding=2,
        force_default_padding=True,
    )
    large_mask = image_utils_module.generate_mask(
        image,
        [large_block],
        default_padding=10,
        force_default_padding=True,
    )

    assert np.count_nonzero(large_mask) > np.count_nonzero(small_mask)


def test_inpaint_pages_from_states_uses_existing_patches_as_input(monkeypatch):
    page_path = "page.png"
    original = np.zeros((8, 8, 3), dtype=np.uint8)
    existing_patch = np.full((2, 2, 3), 9, dtype=np.uint8)
    captured = {}

    class FakeInpainter:
        def __call__(self, image, mask, config):
            captured["image"] = image.copy()
            return image

    main_page = SimpleNamespace(
        settings_page=SimpleNamespace(),
        image_states={page_path: {"brush_strokes": [{"path": object()}]}},
        image_patches={
            page_path: [{"bbox": [1, 1, 2, 2], "hash": "old", "png_path": "unused.png"}],
        },
        in_memory_patches={
            page_path: [{"hash": "old", "image": existing_patch}],
        },
        image_ctrl=SimpleNamespace(
            load_original_image=lambda _file_path: original.copy(),
            load_image=lambda _file_path: None,
        ),
        current_worker=None,
        webtoon_mode=False,
    )
    handler = InpaintingHandler(main_page)
    handler.inpainter_cache = FakeInpainter()
    handler._ensure_inpainter = lambda: handler.inpainter_cache
    handler._build_mask_from_page_state = lambda image, state: np.pad(
        np.ones((1, 1), dtype=np.uint8) * 255,
        ((1, 6), (1, 6)),
    )
    handler._get_regular_patches = lambda mask, image: [{"bbox": [1, 1, 1, 1], "image": image[1:2, 1:2].copy()}]
    monkeypatch.setattr(inpainting_module, "get_config", lambda _settings_page: {})

    result = handler.inpaint_pages_from_states([page_path])

    assert result
    assert captured["image"][1, 1].tolist() == [9, 9, 9]


def test_runtime_patches_prefer_materialized_image_patches():
    state = {
        "inpaint_cache": [
            {"bbox": [0, 0, 1, 1], "png_path": "old-temp.png", "hash": "old"}
        ]
    }
    image_patches = {
        "page.png": [
            {"bbox": [0, 0, 1, 1], "png_path": "materialized.png", "hash": "new"}
        ]
    }

    assert (
        get_runtime_patches(state, image_patches, "page.png")[0]["png_path"]
        == "materialized.png"
    )

    sync_inpaint_cache_from_image_patches({"page.png": state}, image_patches)

    assert state["inpaint_cache"][0]["png_path"] == "materialized.png"


def test_missing_cached_inpaint_patch_forces_recompute():
    page_path = "page.png"
    state = {
        "target_lang": "English",
        "inpaint_cache": [
            {
                "bbox": [1, 1, 2, 2],
                "png_path": os.path.abspath("__missing_inpaint_patch__.png"),
                "hash": "missing",
            }
        ],
    }
    mark_clean_ready(state, has_runtime_patches=True)

    processor = BatchStateMixin.__new__(BatchStateMixin)
    processor.main_page = SimpleNamespace(
        image_states={page_path: state},
        image_patches={},
        in_memory_patches={},
    )
    page = SimpleNamespace(
        image_path=page_path,
        target_lang="English",
        image=np.zeros((8, 8, 3), dtype=np.uint8),
    )

    assert processor._page_can_skip_inpainting(page) is False
    assert processor._restore_cached_inpaint_image(page) is None
