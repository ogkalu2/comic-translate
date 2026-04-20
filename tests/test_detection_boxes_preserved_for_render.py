from types import SimpleNamespace

import numpy as np

from app.projects.parsers import ProjectDecoder, ProjectEncoder
from app.ui.commands.base import RectCommandBase
from modules.detection import text_block_builder
from modules.detection.base import DetectionEngine
from modules.utils.textblock import TextBlock
from pipeline.block_detection import BlockDetectionHandler
from pipeline.webtoon_utils import (
    VisibleBlockSelection,
    filter_and_convert_visible_blocks,
    restore_original_block_coordinates,
)


class _FakeDetector:
    def __init__(self, blocks):
        self._blocks = blocks

    def detect(self, _image):
        return self._blocks


class _FakeViewer:
    def __init__(self, image):
        self._image = image

    def hasPhoto(self):
        return True

    def get_image_array(self):
        return self._image


class _FakeWebtoonImageViewer(_FakeViewer):
    def __init__(self, image, webtoon_manager, mappings):
        super().__init__(image)
        self.webtoon_manager = webtoon_manager
        self._mappings = mappings

    def get_visible_area_image(self):
        return self._image, self._mappings


class _DummyDetectionEngine(DetectionEngine):
    def initialize(self, **kwargs) -> None:
        return None

    def detect(self, image: np.ndarray):
        return []


class _FakeFontEngine:
    def process(self, _crop):
        return {
            "direction": "vertical",
            "text_color": (1, 2, 3),
            "font_size_px": 18,
        }


class _FakePipeline:
    def __init__(self, selected_block=None):
        self._selected_block = selected_block

    def get_selected_block(self):
        return self._selected_block


def test_detect_blocks_keeps_detected_xyxy_for_regular_pages():
    image = np.zeros((800, 600, 3), dtype=np.uint8)
    block = TextBlock(
        text_bbox=[100, 120, 220, 260],
        bubble_bbox=[80, 90, 260, 320],
        text_class="text_bubble",
        text="test",
    )
    original_xyxy = list(block.xyxy)

    main_page = SimpleNamespace(
        image_viewer=_FakeViewer(image),
        webtoon_mode=False,
        settings_page=SimpleNamespace(),
    )
    handler = BlockDetectionHandler(main_page)
    handler.block_detector_cache = _FakeDetector([block])

    blk_list, load_rects, current_page = handler.detect_blocks(load_rects=False)

    assert blk_list[0].xyxy == original_xyxy
    assert load_rects is False
    assert current_page is None


def test_create_text_blocks_handles_missing_bubbles_and_preserves_font_metadata(monkeypatch):
    monkeypatch.setattr(
        text_block_builder.FontEngineFactory,
        "create_engine",
        lambda settings, backend='onnx': _FakeFontEngine(),
    )

    engine = _DummyDetectionEngine(settings=object())
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    text_boxes = np.array([[10, 10, 30, 30]])

    blocks = engine.create_text_blocks(image, text_boxes, None)

    assert len(blocks) == 1
    assert blocks[0].text_class == "text_free"
    assert blocks[0].bubble_xyxy is None
    assert blocks[0].direction == "vertical"
    assert blocks[0].font_color == (1, 2, 3)
    assert blocks[0].font_size_px == 18.0
    assert blocks[0].max_font_size == 18


def test_textblock_state_snapshots_roundtrip_and_deep_copy_preserve_direction():
    block = TextBlock(
        text_bbox=np.array([1, 2, 11, 22]),
        bubble_bbox=np.array([0, 0, 15, 30]),
        text_class="text_bubble",
        text="source",
        texts=["source"],
        translation="target",
        line_spacing=1.4,
        alignment="center",
        target_lang="en",
        min_font_size=9,
        max_font_size=22,
        font_size_px=18.0,
        font_color=(10, 20, 30),
        direction="vertical",
    )
    block.tr_origin_point = (3, 4)
    block.max_chars = 12
    block._page_index = 7

    clone = block.deep_copy()

    assert clone.direction == "vertical"
    assert clone.max_chars == 12
    assert clone._page_index == 7
    assert np.array_equal(clone.xyxy, block.xyxy)
    assert clone.xyxy is not block.xyxy

    restored = TextBlock()
    restored.apply_geometry_state(block.geometry_state())
    restored.apply_content_state(block.content_state())
    restored.apply_render_state(block.render_state())
    restored.apply_metadata_state(block.metadata_state())

    assert np.array_equal(restored.xyxy, block.xyxy)
    assert restored.bubble_xyxy.tolist() == block.bubble_xyxy.tolist()
    assert restored.text == "source"
    assert restored.translation == "target"
    assert restored.direction == "vertical"
    assert restored.font_color == (10, 20, 30)
    assert restored.max_chars == 12


def test_textblock_to_dict_and_parser_roundtrip_drop_runtime_fields():
    block = TextBlock(
        text_bbox=np.array([1, 2, 11, 22]),
        bubble_bbox=np.array([0, 0, 15, 30]),
        text_class="text_bubble",
        text="source",
        texts=["source"],
        translation="target",
        direction="vertical",
        block_uid="blk-1",
    )
    block.max_chars = 12
    block.source_lang = "ja"
    block._mapping = {"page_index": 0}
    block._page_index = 0
    block._original_xyxy = np.array([9, 9, 9, 9])

    data = block.to_dict()

    assert "source_lang" not in data
    assert "_mapping" not in data
    assert "_page_index" not in data
    assert "_original_xyxy" not in data
    assert data["max_chars"] == 12

    encoded = ProjectEncoder.encode_textblock(block)
    decoded = ProjectDecoder.decode_textblock(encoded)

    assert decoded.block_uid == "blk-1"
    assert decoded.direction == "vertical"
    assert decoded.max_chars == 12
    assert not hasattr(decoded, "_mapping")
    assert not hasattr(decoded, "_page_index")
    assert not hasattr(decoded, "_original_xyxy")


def test_command_layer_roundtrip_uses_textblock_dict_interface():
    block = TextBlock(
        text_bbox=np.array([1, 2, 11, 22]),
        text="source",
        translation="target",
        direction="vertical",
        block_uid="blk-2",
    )
    block.source_lang = "ja"
    block._mapping = {"page_index": 0}

    saved = RectCommandBase.save_blk_properties(block)
    restored = RectCommandBase.create_new_blk(saved)

    assert saved["block_uid"] == "blk-2"
    assert "source_lang" not in saved
    assert "_mapping" not in saved
    assert restored.block_uid == "blk-2"
    assert restored.translation == "target"
    assert not hasattr(restored, "_mapping")


def test_webtoon_visible_block_selection_restores_without_temp_block_attrs():
    image = np.zeros((120, 80, 3), dtype=np.uint8)
    block = TextBlock(text_bbox=np.array([10, 20, 30, 40]), text="bubble")
    mappings = [
        {
            "page_index": 0,
            "page_crop_top": 10,
            "page_crop_bottom": 60,
            "combined_y_start": 0,
        }
    ]
    webtoon_manager = SimpleNamespace(
        image_positions=[0],
        image_heights=[100],
        image_data={0: np.zeros((100, 80, 3), dtype=np.uint8)},
        webtoon_width=80,
    )
    main_page = SimpleNamespace(
        blk_list=[block],
        image_viewer=_FakeWebtoonImageViewer(image, webtoon_manager, mappings),
    )
    selection = filter_and_convert_visible_blocks(main_page, _FakePipeline(), mappings, single_block=False)

    assert isinstance(selection, VisibleBlockSelection)
    assert len(selection) == 1
    assert selection[0] is block
    assert selection.context_for(block).page_index == 0
    assert block.xyxy.tolist() == [10, 10, 30, 30]
    assert not hasattr(block, "_mapping")
    assert not hasattr(block, "_page_index")
    assert not hasattr(block, "_original_xyxy")

    restore_original_block_coordinates(selection)

    assert block.xyxy.tolist() == [10, 20, 30, 40]
    assert not hasattr(block, "_mapping")
    assert not hasattr(block, "_page_index")
    assert not hasattr(block, "_original_xyxy")
