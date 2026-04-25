from types import SimpleNamespace

from app.controllers.stage_navigation import StageNavigationController


def _main_for_stage_tests():
    save_calls = []
    dirty_calls = []
    return SimpleNamespace(
        image_files=["page-1.png", "page-2.png"],
        image_states={"page-1.png": {}, "page-2.png": {}},
        image_patches={},
        curr_img_idx=0,
        webtoon_mode=False,
        t_combo=SimpleNamespace(currentText=lambda: "English"),
        image_ctrl=SimpleNamespace(
            save_current_image_state=lambda: save_calls.append("save"),
            on_inpaint_patches_processed=lambda *_args, **_kwargs: None,
        ),
        image_viewer=SimpleNamespace(has_drawn_elements=lambda: False),
        text_ctrl=SimpleNamespace(clear_text_edits=lambda: None, render_all_pages=lambda: None),
        loading=SimpleNamespace(setVisible=lambda *_args, **_kwargs: None),
        disable_hbutton_group=lambda: None,
        run_threaded=lambda callback, result_callback, *_args, **_kwargs: result_callback(callback()),
        default_error_handler=lambda *_args, **_kwargs: None,
        on_manual_finished=lambda: None,
        pipeline=SimpleNamespace(
            prepare_text_stages=lambda _paths: [],
            prepare_clean_stages=lambda _paths: ([], []),
        ),
        mark_project_dirty=lambda: dirty_calls.append(True),
        _save_calls=save_calls,
        _dirty_calls=dirty_calls,
    )


def test_navigate_all_to_stage_marks_every_page_and_applies_current_view():
    main = _main_for_stage_tests()
    controller = StageNavigationController(main)
    applied = []
    controller.apply_stage_view = lambda file_path, ui_stage: applied.append((file_path, ui_stage))
    controller.refresh_stage_buttons = lambda *_args, **_kwargs: None

    controller.navigate_all_to_stage("text")

    assert main.image_states["page-1.png"]["ui_stage"] == "text"
    assert main.image_states["page-2.png"]["ui_stage"] == "text"
    assert applied == [("page-1.png", "text")]


def test_clean_button_runs_all_pages_clean_when_already_in_clean_stage():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"]["ui_stage"] = "clean"
    main.image_states["page-1.png"]["pipeline_state"] = {"page_validity": {"clean": True}}
    main.image_states["page-2.png"]["pipeline_state"] = {"page_validity": {"clean": True}}
    main.image_states["page-2.png"]["brush_strokes"] = [{"path": object()}]
    controller = StageNavigationController(main)
    calls = []
    controller._run_clean_for_all_pages = lambda: calls.append("clean-all")
    controller.navigate_all_to_stage = lambda ui_stage: calls.append(("navigate", ui_stage))

    controller.handle_stage_button(1)

    assert calls == ["clean-all"]


def test_paths_with_clean_input_does_not_reclean_patched_block_pages_when_strokes_exist():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"]["brush_strokes"] = [{"path": object()}]
    main.image_states["page-2.png"]["blk_list"] = [object()]
    main.image_patches["page-2.png"] = [{"bbox": [0, 0, 1, 1], "image": object()}]
    controller = StageNavigationController(main)

    assert controller._paths_with_clean_input() == ["page-1.png"]


def test_paths_with_clean_input_keeps_unpatched_block_pages_as_auto_clean_input():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"]["blk_list"] = [object()]
    main.image_states["page-2.png"]["blk_list"] = [object()]
    main.image_patches["page-2.png"] = [{"bbox": [0, 0, 1, 1], "image": object()}]
    controller = StageNavigationController(main)

    assert controller._paths_with_clean_input() == ["page-1.png"]


def test_render_button_renders_all_pages_when_blocks_exist():
    main = _main_for_stage_tests()
    main.image_states["page-2.png"]["blk_list"] = [object()]
    calls = []
    main.text_ctrl = SimpleNamespace(render_all_pages=lambda: calls.append("render-all"))
    controller = StageNavigationController(main)
    controller.navigate_all_to_stage = lambda ui_stage: calls.append(("navigate", ui_stage))

    controller.handle_stage_button(2)

    assert calls == ["render-all"]


def test_render_button_shows_existing_snapshot_for_current_target():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"] = {
        "target_lang": "English",
        "blk_list": [object()],
        "target_render_states": {
            "English": {
                "text_items_state": [
                    {
                        "block_uid": "title",
                        "text": "Hello",
                    }
                ]
            }
        },
        "pipeline_state": {
            "target_lang": "English",
            "target_validity": {
                "English": {
                    "translate": True,
                    "render": True,
                }
            },
        },
    }
    calls = []
    main.text_ctrl = SimpleNamespace(render_all_pages=lambda: calls.append("render-all"))
    controller = StageNavigationController(main)
    controller.navigate_all_to_stage = lambda ui_stage: calls.append(("navigate", ui_stage))

    controller.handle_stage_button(2)

    assert calls == [("navigate", "render")]


def test_all_pages_clean_result_applies_patches_and_clears_saved_strokes():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"]["brush_strokes"] = [{"path": object()}]
    patch_calls = []
    main.image_ctrl = SimpleNamespace(
        on_inpaint_patches_processed=lambda patches, file_path: patch_calls.append((file_path, patches))
    )
    dirty = []
    main.mark_project_dirty = lambda: dirty.append(True)
    controller = StageNavigationController(main)
    controller.apply_stage_view = lambda *_args, **_kwargs: None

    patches = [{"bbox": [0, 0, 2, 2], "image": object()}]
    controller._on_all_pages_clean_ready([("page-1.png", patches)])

    assert patch_calls == [("page-1.png", patches)]
    assert main.image_states["page-1.png"]["brush_strokes"] == []
    assert dirty == [True]


def test_text_button_precomputes_all_pages_before_translation():
    main = _main_for_stage_tests()
    main.pipeline = SimpleNamespace(prepare_text_stages=lambda paths: list(paths))
    controller = StageNavigationController(main)
    applied = []
    controller.apply_stage_view = lambda file_path, ui_stage: applied.append((file_path, ui_stage))
    controller.refresh_stage_buttons = lambda *_args, **_kwargs: None

    controller.handle_stage_button(0)

    assert main._save_calls == ["save"]
    assert main.image_states["page-1.png"]["ui_stage"] == "text"
    assert main.image_states["page-2.png"]["ui_stage"] == "text"
    assert applied == [("page-1.png", "text")]
    assert main._dirty_calls == [True]


def test_clean_button_precomputes_and_inpaints_all_pages_before_translation():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"]["blk_list"] = [object()]
    patches = [{"bbox": [0, 0, 2, 2], "image": object()}]
    patch_calls = []
    main.image_ctrl = SimpleNamespace(
        save_current_image_state=lambda: main._save_calls.append("save"),
        on_inpaint_patches_processed=lambda applied_patches, file_path: patch_calls.append((file_path, applied_patches)),
    )
    main.pipeline = SimpleNamespace(
        prepare_text_stages=lambda _paths: ["page-1.png"],
        prepare_clean_stages=lambda _paths: (["page-1.png"], [("page-1.png", patches)]),
    )
    controller = StageNavigationController(main)
    applied = []
    controller.apply_stage_view = lambda file_path, ui_stage: applied.append((file_path, ui_stage))
    controller.refresh_stage_buttons = lambda *_args, **_kwargs: None

    controller.handle_stage_button(1)

    assert main._save_calls == ["save"]
    assert main.image_states["page-1.png"]["ui_stage"] == "clean"
    assert main.image_states["page-2.png"]["ui_stage"] == "clean"
    assert patch_calls == [("page-1.png", patches)]
    assert applied == [("page-1.png", "clean")]
    assert main._dirty_calls == [True]


def test_text_button_only_navigates_after_translation_exists():
    main = _main_for_stage_tests()
    main.image_states["page-1.png"] = {
        "blk_list": [SimpleNamespace(translation="Hello")],
        "pipeline_state": {
            "target_validity": {
                "English": {
                    "translate": True,
                    "render": False,
                }
            }
        },
    }
    calls = []
    controller = StageNavigationController(main)
    controller.navigate_all_to_stage = lambda ui_stage: calls.append(("navigate", ui_stage))
    controller._run_text_for_all_pages = lambda: calls.append("precompute")

    controller.handle_stage_button(0)

    assert calls == [("navigate", "text")]
