import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.controllers.text_render_batch_mixin import TextRenderBatchMixin
from app.controllers.text_state_mixin import TextStateMixin
from pipeline.render_state import (
    build_render_template_map,
    ensure_target_snapshot,
    get_render_template_for_block,
    get_target_snapshot,
    set_target_snapshot,
    update_render_style_overrides,
)


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _item(block_uid, text, color, gradient=False, x=10):
    return {
        "block_uid": block_uid,
        "text": text,
        "source_text": text,
        "font_family": "Comic Font",
        "font_size": 32,
        "text_color": color,
        "outline": True,
        "outline_color": "#ffffff",
        "outline_width": 1.5,
        "second_outline": gradient,
        "second_outline_color": "#000000",
        "second_outline_width": 2.0,
        "text_gradient": gradient,
        "text_gradient_start_color": "#ff0000",
        "text_gradient_end_color": "#ffff00",
        "position": (x, 20),
        "rotation": 0,
        "scale": 1.0,
        "width": 120,
        "height": 40,
    }


def _snapshot(text, color, gradient=False):
    return {
        "text_items_state": [
            _item("cover-title", text, color, gradient),
        ]
    }


def test_style_override_applies_to_matching_block_without_overwriting_text():
    state = {"target_render_states": {}}
    set_target_snapshot(state, "English", _snapshot("HELLO", "#111111", gradient=False))
    set_target_snapshot(state, "Arabic", _snapshot("مرحبا", "#222222", gradient=False))
    update_render_style_overrides(state, _snapshot("HELLO", "#ff00ff", gradient=True))

    template = build_render_template_map(state, "Arabic")[("cover-title", (), 0.0)]

    assert template["text"] == "مرحبا"
    assert template["text_color"] == "#ff00ff"
    assert template["text_gradient"] is True
    assert template["second_outline"] is True


def test_style_override_does_not_reuse_fitted_font_size_across_languages():
    state = {"target_render_states": {}}
    english = _snapshot("HELLO", "#111111", gradient=False)
    arabic = _snapshot("مرحبا", "#222222", gradient=False)
    english["text_items_state"][0]["font_size"] = 10
    arabic["text_items_state"][0]["font_size"] = 28
    set_target_snapshot(state, "English", english)
    set_target_snapshot(state, "Arabic", arabic)
    update_render_style_overrides(state, english)

    template = build_render_template_map(state, "Arabic")[("cover-title", (), 0.0)]

    assert template["font_size"] == 28


def test_style_override_does_not_reuse_selection_outline_ranges_across_languages():
    state = {"target_render_states": {}}
    english = _snapshot("HELLO", "#111111", gradient=False)
    arabic = _snapshot("مرحبا بالعالم", "#222222", gradient=False)
    english["text_items_state"][0]["selection_outlines"] = [
        {"start": 0, "end": 5, "color": "#ffffff", "width": 1.5, "type": "full_document"}
    ]
    arabic["text_items_state"][0]["selection_outlines"] = [
        {"start": 0, "end": 13, "color": "#ffffff", "width": 1.5, "type": "full_document"}
    ]
    set_target_snapshot(state, "English", english)
    set_target_snapshot(state, "Arabic", arabic)
    update_render_style_overrides(state, english)

    template = build_render_template_map(state, "Arabic")[("cover-title", (), 0.0)]

    assert template["selection_outlines"] == arabic["text_items_state"][0]["selection_outlines"]


def test_new_target_snapshot_drops_stale_selection_outline_ranges():
    viewer_state = _snapshot("HELLO", "#111111", gradient=False)
    viewer_state["text_items_state"][0]["selection_outlines"] = [
        {"start": 0, "end": 5, "color": "#ffffff", "width": 1.5, "type": "full_document"}
    ]
    state = {"viewer_state": viewer_state, "target_render_states": {}}

    cloned = ensure_target_snapshot(state, "Arabic", fallback_snapshot=viewer_state)
    item = cloned["text_items_state"][0]

    assert "selection_outlines" not in item
    assert item["outline"] is True
    assert item["outline_color"] == "#ffffff"
    assert item["outline_width"] == 1.5


def test_style_override_is_individual_per_block():
    state = {"target_render_states": {}}
    set_target_snapshot(
        state,
        "Arabic",
        {
            "text_items_state": [
                _item("cover-title", "مرحبا", "#222222", gradient=False, x=10),
                _item("subtitle", "العالم", "#333333", gradient=False, x=200),
            ]
        },
    )
    update_render_style_overrides(
        state,
        {"text_items_state": [_item("cover-title", "HELLO", "#ff00ff", gradient=True, x=10)]},
    )

    template_map = build_render_template_map(state, "Arabic")
    title = template_map[("cover-title", (), 0.0)]
    subtitle = template_map[("subtitle", (), 0.0)]

    assert title["text_color"] == "#ff00ff"
    assert title["text_gradient"] is True
    assert subtitle["text_color"] == "#333333"
    assert subtitle["text_gradient"] is False


def test_target_snapshot_applies_block_style_overrides_for_existing_language():
    state = {"target_render_states": {}}
    set_target_snapshot(state, "English", _snapshot("HELLO", "#111111", gradient=False))
    set_target_snapshot(state, "Arabic", _snapshot("مرحبا", "#222222", gradient=False))
    update_render_style_overrides(state, _snapshot("HELLO", "#ff00ff", gradient=True))

    snapshot = get_target_snapshot(state, "Arabic")
    item = snapshot["text_items_state"][0]

    assert item["text"] == "مرحبا"
    assert item["text_color"] == "#ff00ff"
    assert item["text_gradient"] is True
    assert state["target_render_states"]["Arabic"]["text_items_state"][0]["text_color"] == "#222222"


def test_target_snapshot_can_return_raw_language_state_without_overrides():
    state = {"target_render_states": {}}
    set_target_snapshot(state, "Arabic", _snapshot("مرحبا", "#222222", gradient=False))
    update_render_style_overrides(state, _snapshot("HELLO", "#ff00ff", gradient=True))

    raw_snapshot = get_target_snapshot(state, "Arabic", apply_style_overrides=False)
    item = raw_snapshot["text_items_state"][0]

    assert item["text"] == "مرحبا"
    assert item["text_color"] == "#222222"
    assert item["text_gradient"] is False


def test_target_snapshot_does_not_fallback_to_viewer_state_for_other_language():
    state = {
        "target_lang": "English",
        "viewer_state": _snapshot("HELLO", "#111111", gradient=False),
        "target_render_states": {},
    }

    assert get_target_snapshot(state, "Arabic") == {}


def test_auto_render_does_not_overwrite_existing_block_style_override():
    state = {"target_render_states": {}}
    update_render_style_overrides(
        state,
        {"text_items_state": [_item("cover-title", "HELLO", "#ff00ff", gradient=True, x=10)]},
    )
    update_render_style_overrides(
        state,
        {"text_items_state": [_item("cover-title", "مرحبا", "#222222", gradient=False, x=10)]},
        overwrite=False,
    )

    template = build_render_template_map(state, "Arabic")[("cover-title", (), 0.0)]

    assert template["text_color"] == "#ff00ff"
    assert template["text_gradient"] is True


def test_render_template_for_block_matches_uid_before_rect_fallback():
    state = {"target_render_states": {}}
    set_target_snapshot(
        state,
        "Arabic",
        {
            "text_items_state": [
                _item("cover-title", "مرحبا", "#ff00ff", gradient=True, x=10),
                _item("", "العالم", "#333333", gradient=False, x=200),
            ]
        },
    )

    template_map = build_render_template_map(state, "Arabic")
    uid_blk = SimpleNamespace(block_uid="cover-title", xyxy=(999, 999, 1000, 1000), angle=0.0)
    rect_blk = SimpleNamespace(block_uid="", xyxy=(200, 20, 320, 60), angle=0.0)

    assert get_render_template_for_block(template_map, uid_blk)["text_color"] == "#ff00ff"
    assert get_render_template_for_block(template_map, rect_blk)["text_color"] == "#333333"


def test_render_template_for_block_accepts_numpy_xyxy():
    state = {"target_render_states": {}}
    set_target_snapshot(
        state,
        "Arabic",
        {"text_items_state": [_item("", "العالم", "#333333", gradient=False, x=200)]},
    )

    template_map = build_render_template_map(state, "Arabic")
    rect_blk = SimpleNamespace(block_uid="", xyxy=np.array([200, 20, 320, 60]), angle=0.0)

    assert get_render_template_for_block(template_map, rect_blk)["text_color"] == "#333333"


def test_render_template_map_accepts_numpy_position():
    state = {"target_render_states": {}}
    item = _item("", "العالم", "#333333", gradient=False, x=200)
    item["position"] = np.array([200, 20])
    set_target_snapshot(state, "Arabic", {"text_items_state": [item]})

    template_map = build_render_template_map(state, "Arabic")

    assert template_map[("", (200, 20, 320, 60), 0.0)]["text_color"] == "#333333"


def test_language_switch_saves_current_scene_under_previous_target():
    class Combo:
        def currentText(self):
            return "Arabic"

    class ImageCtrl:
        saved_target = None

        def save_current_image_state(self, target_lang=None):
            self.saved_target = target_lang

    class TextOption:
        def setTextDirection(self, _direction):
            pass

    class Document:
        def __init__(self):
            self.option = TextOption()

        def defaultTextOption(self):
            return self.option

        def setDefaultTextOption(self, option):
            self.option = option

    class TextEdit:
        def __init__(self):
            self.doc = Document()

        def document(self):
            return self.doc

    state = {
        "target_lang": "English",
        "viewer_state": _snapshot("HELLO", "#ff00ff", gradient=True),
        "target_render_states": {},
    }
    main = SimpleNamespace(
        t_combo=Combo(),
        image_ctrl=ImageCtrl(),
        lang_mapping={"Arabic": "Arabic"},
        t_text_edit=TextEdit(),
        image_files=["page-1"],
        image_states={"page-1": state},
        curr_img_idx=0,
        stage_nav_ctrl=SimpleNamespace(restore_current_page_view=lambda: None),
        mark_project_dirty=lambda: None,
    )
    ctrl = TextStateMixin()
    ctrl.main = main
    ctrl._last_target_lang = "English"

    ctrl.save_src_trg()

    assert main.image_ctrl.saved_target == "English"
    assert state["target_lang"] == "Arabic"
    assert state["target_render_states"]["English"]["text_items_state"][0]["text_color"] == "#ff00ff"


def test_manual_render_all_uses_current_combo_target():
    _ensure_app()

    class Block:
        xyxy = np.array([0, 0, 120, 60])
        translation = "مرحبا"
        text = "source"
        angle = 0
        tr_origin_point = (0, 0)
        font_color = ()
        direction = ""
        min_font_size = 0
        max_font_size = 0
        font_size_px = 0
        block_uid = "title"

        @property
        def xywh(self):
            x1, y1, x2, y2 = self.xyxy
            return np.array([x1, y1, x2 - x1, y2 - y1])

    class Ctrl(TextRenderBatchMixin):
        def render_settings(self):
            return SimpleNamespace(
                upper_case=False,
                color="#000000",
                outline=False,
                outline_color="#ffffff",
                second_outline=False,
                second_outline_color="#000000",
                second_outline_width="0",
                text_gradient=False,
                text_gradient_start_color="#000000",
                text_gradient_end_color="#000000",
            )

    state = {
        "target_lang": "English",
        "blk_list": [Block()],
        "viewer_state": {},
        "target_render_states": {},
    }
    main = SimpleNamespace(
        image_states={"page-1.png": state},
        image_patches={},
        t_combo=SimpleNamespace(currentText=lambda: "Arabic"),
        lang_mapping={"English": "English", "Arabic": "Arabic"},
        line_spacing_dropdown=SimpleNamespace(currentText=lambda: "1.2"),
        font_dropdown=SimpleNamespace(currentText=lambda: "Arial"),
        outline_width_dropdown=SimpleNamespace(currentText=lambda: "0"),
        bold_button=SimpleNamespace(isChecked=lambda: False),
        italic_button=SimpleNamespace(isChecked=lambda: False),
        underline_button=SimpleNamespace(isChecked=lambda: False),
        alignment_tool_group=SimpleNamespace(get_dayu_checked=lambda: 0),
        button_to_alignment={0: Qt.AlignmentFlag.AlignCenter},
        settings_page=SimpleNamespace(
            get_max_font_size=lambda: 24,
            get_min_font_size=lambda: 8,
        ),
    )
    ctrl = Ctrl()
    ctrl.main = main

    updated = ctrl._render_selected_pages_worker(["page-1.png"])

    assert updated == {"page-1.png"}
    assert state["target_lang"] == "Arabic"
    assert "Arabic" in state["target_render_states"]
    assert "English" not in state["target_render_states"]
