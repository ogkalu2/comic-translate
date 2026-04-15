from __future__ import annotations

import logging
import os
import shutil
import tempfile
from typing import TYPE_CHECKING

from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import TextBlockItem
from modules.utils.archives import make

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from controller import ComicTranslate


class ProjectExportMixin:
    def save_and_make(self, output_path: str):
        self.main.loading.setVisible(True)
        self.main.run_threaded(
            self.save_and_make_worker,
            None,
            self.main.default_error_handler,
            lambda: self.main.loading.setVisible(False),
            output_path,
        )

    def save_and_make_worker(self, output_path: str):
        self.main.image_ctrl.save_current_image_state()
        all_pages_current_state = self._build_all_pages_current_state()
        try:
            if self.main.file_handler.should_pre_materialize(self.main.image_files):
                count = self.main.file_handler.pre_materialize(self.main.image_files)
                logger.info("Export pre-materialized %d paths before save-and-make.", count)
        except Exception:
            logger.debug("Export pre-materialization failed; continuing lazily.", exc_info=True)
        temp_dir = tempfile.mkdtemp()
        try:
            temp_main_page_context = None
            if self.main.webtoon_mode:
                temp_main_page_context = type(
                    "TempMainPage",
                    (object,),
                    {"image_files": self.main.image_files, "image_states": all_pages_current_state},
                )()

            for page_idx, file_path in enumerate(self.main.image_files):
                bname = os.path.basename(file_path)
                rgb_img = self.main.load_image(file_path)
                renderer = ImageSaveRenderer(rgb_img)
                viewer_state = all_pages_current_state[file_path]["viewer_state"]

                renderer.apply_patches(self.main.image_patches.get(file_path, []))
                if self.main.webtoon_mode and temp_main_page_context is not None:
                    renderer.add_state_to_image(viewer_state, page_idx, temp_main_page_context)
                else:
                    renderer.add_state_to_image(viewer_state)

                sv_pth = os.path.join(temp_dir, bname)
                renderer.save_image(sv_pth)

            make(temp_dir, output_path)
        finally:
            shutil.rmtree(temp_dir)

    def _build_all_pages_current_state(self) -> dict[str, dict]:
        all_pages_current_state: dict[str, dict] = {}

        if self.main.webtoon_mode:
            loaded_pages = self.main.image_viewer.webtoon_manager.loaded_pages
            for page_idx, file_path in enumerate(self.main.image_files):
                if page_idx in loaded_pages:
                    viewer_state = self._create_text_items_state_from_scene(page_idx)
                else:
                    viewer_state = self.main.image_states.get(file_path, {}).get("viewer_state", {}).copy()
                all_pages_current_state[file_path] = {"viewer_state": viewer_state}
            return all_pages_current_state

        for file_path in self.main.image_files:
            viewer_state = self.main.image_states.get(file_path, {}).get("viewer_state", {}).copy()
            all_pages_current_state[file_path] = {"viewer_state": viewer_state}

        return all_pages_current_state

    def _create_text_items_state_from_scene(self, page_idx: int) -> dict:
        webtoon_manager = self.main.image_viewer.webtoon_manager
        page_y_start = webtoon_manager.image_positions[page_idx]

        if page_idx < len(webtoon_manager.image_positions) - 1:
            page_y_end = webtoon_manager.image_positions[page_idx + 1]
        else:
            file_path = self.main.image_files[page_idx]
            rgb_img = self.main.load_image(file_path)
            page_y_end = page_y_start + rgb_img.shape[0]

        text_items_data = []

        for item in self.main.image_viewer._scene.items():
            if isinstance(item, TextBlockItem):
                text_item = item
                text_y = text_item.pos().y()

                if text_y >= page_y_start and text_y < page_y_end:
                    scene_pos = text_item.pos()
                    page_local_x = scene_pos.x()
                    page_local_y = scene_pos.y() - page_y_start

                    text_props = TextItemProperties.from_text_item(text_item)
                    text_props.position = (page_local_x, page_local_y)

                    text_items_data.append(text_props.to_dict())

        return {
            "text_items_state": text_items_data,
            "push_to_stack": False,
        }
