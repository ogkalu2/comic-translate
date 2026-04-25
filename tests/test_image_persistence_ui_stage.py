from types import SimpleNamespace

from app.controllers.image_persistence_mixin import ImagePersistenceMixin


class _FakeImagePersistence(ImagePersistenceMixin):
    def __init__(self, main):
        self.main = main


def test_save_image_state_prefers_active_clean_tool_for_current_page():
    file_path = "page-1.png"
    main = SimpleNamespace(
        curr_img_idx=0,
        image_files=[file_path],
        image_states={file_path: {"ui_stage": "text"}},
        image_patches={},
        blk_list=[],
        t_combo=SimpleNamespace(currentText=lambda: "English"),
        image_viewer=SimpleNamespace(
            hasPhoto=lambda: True,
            current_tool="brush",
            save_state=lambda: {},
            save_brush_strokes=lambda: [],
        ),
        stage_nav_ctrl=SimpleNamespace(
            get_ui_stage=lambda _file_path: "text",
            _serialize_rectangles_from_blocks=lambda _blk_list: [],
        ),
    )

    controller = _FakeImagePersistence(main)
    controller.save_image_state(file_path)

    assert main.image_states[file_path]["ui_stage"] == "clean"
