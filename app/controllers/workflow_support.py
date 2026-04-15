from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from pipeline.webtoon_utils import get_visible_text_items

if TYPE_CHECKING:
    from app.ui.canvas.text_item import TextBlockItem
    from controller import ComicTranslate


def prepare_multi_page_context(main: "ComicTranslate", selected_paths: Sequence[str]) -> dict[str, object]:
    current_file = None
    if 0 <= main.curr_img_idx < len(main.image_files):
        current_file = main.image_files[main.curr_img_idx]

    current_page_unloaded = False
    if main.webtoon_mode:
        manager = getattr(main.image_viewer, "webtoon_manager", None)
        scene_mgr = getattr(manager, "scene_item_manager", None) if manager is not None else None
        if scene_mgr is not None:
            scene_mgr.save_all_scene_items_to_states()
            if (
                current_file in selected_paths
                and 0 <= main.curr_img_idx < len(main.image_files)
                and main.curr_img_idx in manager.loaded_pages
            ):
                scene_mgr.unload_page_scene_items(main.curr_img_idx)
                current_page_unloaded = True
    else:
        main.image_ctrl.save_current_image_state()

    return {
        "current_file": current_file,
        "current_page_unloaded": current_page_unloaded,
    }


def reload_current_webtoon_page(main: "ComicTranslate") -> None:
    if not main.webtoon_mode:
        return
    manager = getattr(main.image_viewer, "webtoon_manager", None)
    if manager is None:
        return
    scene_mgr = getattr(manager, "scene_item_manager", None)
    if scene_mgr is None:
        return
    page_idx = main.curr_img_idx
    if not (0 <= page_idx < len(main.image_files)):
        return
    if page_idx not in manager.loaded_pages:
        return
    scene_mgr.load_page_scene_items(page_idx)
    main.text_ctrl.clear_text_edits()


def get_visible_text_items_for_main(main: "ComicTranslate") -> list["TextBlockItem"]:
    if not main.webtoon_mode:
        return list(main.image_viewer.text_items)
    return get_visible_text_items(
        main.image_viewer.text_items,
        main.image_viewer.webtoon_manager,
    )
