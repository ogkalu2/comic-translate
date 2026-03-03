import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import List

import imkit as imk

from app.path_materialization import ensure_path_materialized
from ..virtual_page import PageStatus

logger = logging.getLogger(__name__)


class FlowMixin:
    def webtoon_batch_process(self, selected_paths: List[str] = None):
        """
        Main webtoon batch processing method. Saves physical pages as soon as they
        and their neighbors' live data is finalized, allowing for correct handling
        of spanning text items.
        """
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        image_list = selected_paths if selected_paths is not None else self.main_page.image_files
        total_images = len(image_list)
        try:
            if self.main_page.file_handler.should_pre_materialize(image_list):
                count = self.main_page.file_handler.pre_materialize(image_list)
                logger.info(
                    "Webtoon batch pre-materialized %d paths before full-run processing.",
                    count,
                )
        except Exception:
            logger.debug(
                "Webtoon batch pre-materialization failed; continuing lazily.",
                exc_info=True,
            )

        if total_images < 1:
            logger.warning("No images to process")
            return

        logger.info(
            "Starting EAGER webtoon batch processing for %d images with spanning item support.",
            total_images,
        )

        # Reset and initialize per-run state.
        self.virtual_chunk_results.clear()
        self.virtual_page_processing_count.clear()
        self.finalized_virtual_pages.clear()
        self.physical_page_status.clear()
        self.final_patches_for_save.clear()
        self.processed_chunks = set()
        self.virtual_page_to_chunks = defaultdict(list)

        all_virtual_pages = []
        physical_to_virtual_mapping = {}
        # Step 1: Create virtual pages for all physical pages.
        for physical_idx, image_path in enumerate(image_list):
            state = self.main_page.image_states.get(image_path, {})
            if state.get("skip", False):
                logger.info("Skipping physical page %d due to user setting.", physical_idx)
                self.physical_page_status[physical_idx] = PageStatus.RENDERED

                base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
                extension = os.path.splitext(image_path)[1]
                directory = os.path.dirname(image_path)
                archive_bname = ""
                for archive in self.main_page.file_handler.archive_info:
                    if image_path in archive["extracted_images"]:
                        archive_path = archive["archive_path"]
                        directory = os.path.dirname(archive_path)
                        archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                        break

                ensure_path_materialized(image_path)
                image = imk.read_image(image_path)
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.log_skipped_image(directory, timestamp, image_path, "User-skipped")
                continue

            ensure_path_materialized(image_path)
            image = imk.read_image(image_path)
            if image is None:
                logger.error("Failed to load image: %s", image_path)
                continue

            virtual_pages = self.virtual_page_creator.create_virtual_pages(
                physical_idx,
                image_path,
                image,
            )
            all_virtual_pages.extend(virtual_pages)
            physical_to_virtual_mapping[physical_idx] = virtual_pages

        if not all_virtual_pages:
            logger.error("No virtual pages were created from the provided images.")
            return

        # Step 2: Create virtual chunk pairs and lookup maps.
        virtual_chunk_pairs = self.virtual_page_creator.get_virtual_chunk_pairs(all_virtual_pages)
        for chunk_idx, (vpage1, vpage2) in enumerate(virtual_chunk_pairs):
            chunk_id = f"chunk_{chunk_idx}_{vpage1.virtual_id}_{vpage2.virtual_id}"
            self.virtual_page_to_chunks[vpage1.virtual_id].append(chunk_id)
            # Avoid duplicate chunk registration for self-paired chunks.
            if vpage1.virtual_id != vpage2.virtual_id:
                self.virtual_page_to_chunks[vpage2.virtual_id].append(chunk_id)

        total_chunks = len(virtual_chunk_pairs)
        logger.info(
            "Created %d virtual pages and %d chunks to process.",
            len(all_virtual_pages),
            total_chunks,
        )

        physical_page_first_chunk = {}
        physical_page_last_chunk = {}

        # Map each physical page to its first and last chunk index.
        for chunk_idx, (vpage1, vpage2) in enumerate(virtual_chunk_pairs):
            physical_pages_in_chunk = {vpage1.physical_page_index, vpage2.physical_page_index}
            for p_idx in physical_pages_in_chunk:
                if p_idx not in physical_page_first_chunk:
                    physical_page_first_chunk[p_idx] = chunk_idx
                physical_page_last_chunk[p_idx] = chunk_idx

        # Step 3: Process chunks and progressively finalize/render pages.
        for chunk_idx, (vpage1, vpage2) in enumerate(virtual_chunk_pairs):
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                break

            chunk_id = f"chunk_{chunk_idx}_{vpage1.virtual_id}_{vpage2.virtual_id}"
            physical_pages_in_chunk = {vpage1.physical_page_index, vpage2.physical_page_index}

            is_first_chunk_for_any_page = any(
                physical_page_first_chunk[p_idx] == chunk_idx for p_idx in physical_pages_in_chunk
            )
            if is_first_chunk_for_any_page:
                # If multiple pages start on this chunk, use the smallest page index for naming.
                starting_page = min(
                    p_idx
                    for p_idx in physical_pages_in_chunk
                    if physical_page_first_chunk[p_idx] == chunk_idx
                )
                self.main_page.progress_update.emit(starting_page, total_images, 0, 10, True)

            try:
                chunk_results = self._process_virtual_chunk(
                    vpage1,
                    vpage2,
                    chunk_id,
                    timestamp,
                    physical_pages_in_chunk,
                    total_images,
                )
                if chunk_results:
                    self.virtual_chunk_results[chunk_id] = chunk_results
                self.processed_chunks.add(chunk_id)
            except Exception as e:
                logger.exception("Error processing virtual chunk %s: %s", chunk_id, e, exc_info=True)
                self.processed_chunks.add(chunk_id)

            # Live UI and state finalization.
            newly_finalized_physical_pages = set()
            unique_vpages = {vpage1.virtual_id: vpage1, vpage2.virtual_id: vpage2}
            for vpage in unique_vpages.values():
                if vpage.virtual_id in self.finalized_virtual_pages:
                    continue

                required_chunks = self.virtual_page_to_chunks[vpage.virtual_id]
                if all(c_id in self.processed_chunks for c_id in required_chunks):
                    self._finalize_and_emit_for_virtual_page(vpage)
                    self.finalized_virtual_pages.add(vpage.virtual_id)

                    p_idx = vpage.physical_page_index
                    if (
                        self.physical_page_status.get(p_idx, PageStatus.UNPROCESSED)
                        == PageStatus.UNPROCESSED
                    ):
                        vpages_for_physical = physical_to_virtual_mapping.get(p_idx, [])
                        if all(vp.virtual_id in self.finalized_virtual_pages for vp in vpages_for_physical):
                            logger.info("All live data for physical page %d is now finalized.", p_idx)
                            self.physical_page_status[p_idx] = PageStatus.LIVE_DATA_FINALIZED
                            newly_finalized_physical_pages.add(p_idx)
                            image_path = image_list[p_idx]
                            page_state = self.main_page.image_states.get(image_path)
                            if page_state is not None:
                                viewer_state = page_state.setdefault("viewer_state", {})
                                viewer_state["push_to_stack"] = True
                            self.main_page.render_state_ready.emit(image_path)

            # Trigger render checks for newly finalized pages and immediate neighbors.
            pages_to_check_for_render = set(newly_finalized_physical_pages)
            for p_idx in newly_finalized_physical_pages:
                if p_idx > 0:
                    pages_to_check_for_render.add(p_idx - 1)
                if p_idx < total_images - 1:
                    pages_to_check_for_render.add(p_idx + 1)

            for p_idx in sorted(list(pages_to_check_for_render)):
                self._check_and_render_page(
                    p_idx,
                    total_images,
                    image_list,
                    timestamp,
                    physical_to_virtual_mapping,
                )

            for p_idx in physical_pages_in_chunk:
                if physical_page_last_chunk[p_idx] == chunk_idx:
                    self.main_page.progress_update.emit(p_idx, total_images, 10, 10, False)
                    logger.info(
                        "Physical page %d processing completed (last chunk: %d)",
                        p_idx,
                        chunk_idx,
                    )

        logger.info(
            "Main processing loop finished. Running final cleanup render check for any remaining pages."
        )
        # Final cleanup loop: catch any page that reached LIVE_DATA_FINALIZED late.
        for p_idx in range(total_images):
            if self.physical_page_status.get(p_idx) == PageStatus.LIVE_DATA_FINALIZED:
                self._check_and_render_page(
                    p_idx,
                    total_images,
                    image_list,
                    timestamp,
                    physical_to_virtual_mapping,
                )

        logger.info("Eager webtoon batch processing completed.")
