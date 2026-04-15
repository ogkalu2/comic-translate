from __future__ import annotations

import logging
from typing import List

from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.translator_utils import format_translations
from ..virtual_page import VirtualPage

logger = logging.getLogger(__name__)


class RenderPagePrepareMixin:
    def _prepare_physical_page_for_render(
        self,
        physical_page_index: int,
        image_path: str,
        virtual_pages: List[VirtualPage],
    ):
        logger.info("Preparing final block list for physical page %s", physical_page_index)

        all_physical_blocks = []
        for vpage in virtual_pages:
            merged_virtual_blocks = self._merge_virtual_page_results(vpage.virtual_id)
            for block in merged_virtual_blocks:
                physical_block = block.deep_copy()
                physical_block.xyxy = vpage.virtual_to_physical_coords(block.xyxy)
                if block.bubble_xyxy:
                    physical_block.bubble_xyxy = vpage.virtual_to_physical_coords(block.bubble_xyxy)
                all_physical_blocks.append(physical_block)

        final_blocks = self._deduplicate_physical_blocks(all_physical_blocks)
        if not final_blocks:
            logger.warning("No final blocks found for physical page %s. Marking for skip.", physical_page_index)
            self.main_page.image_states[image_path]["blk_list"] = []
            self.main_page.image_states[image_path]["skip_render"] = True
            return

        self.main_page.image_states[image_path]["skip_render"] = False
        logger.info("Prepared physical page %s with %s final blocks.", physical_page_index, len(final_blocks))

        render_settings = self.main_page.render_settings()
        target_lang = self.main_page.image_states[image_path]["target_lang"]
        target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
        trg_lng_cd = get_language_code(target_lang_en)
        format_translations(final_blocks, trg_lng_cd, upper_case=render_settings.upper_case)

        if is_no_space_lang(trg_lng_cd):
            for blk in final_blocks:
                if blk.translation:
                    blk.translation = blk.translation.replace(" ", "")

        page_state = self.main_page.image_states[image_path]
        page_state.update({"blk_list": final_blocks, "target_lang": target_lang})
        if "viewer_state" in page_state:
            page_state["viewer_state"]["push_to_stack"] = False
