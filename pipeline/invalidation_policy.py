from __future__ import annotations

from pipeline.page_state import get_page_state, has_runtime_patches
from pipeline.stage_state import (
    finalize_render_stage,
    invalidate_after_box_edit,
    invalidate_after_segmentation_edit,
    invalidate_after_source_text_edit,
    invalidate_after_translated_text_edit,
)


def invalidate_page_for_box_edit(image_states: dict, image_patches: dict, file_path: str) -> tuple[dict, str]:
    state = get_page_state(image_states, file_path)
    invalidate_after_box_edit(
        state,
        has_runtime_patches=has_runtime_patches(state, image_patches, file_path),
    )
    return state, "text"


def invalidate_page_for_source_text_edit(image_states: dict, image_patches: dict, file_path: str) -> tuple[dict, str]:
    state = get_page_state(image_states, file_path)
    invalidate_after_source_text_edit(
        state,
        has_runtime_patches=has_runtime_patches(state, image_patches, file_path),
    )
    return state, "text"


def invalidate_page_for_translated_text_edit(
    image_states: dict,
    image_patches: dict,
    file_path: str,
    target_lang: str,
) -> tuple[dict, str]:
    state = get_page_state(image_states, file_path)
    invalidate_after_translated_text_edit(
        state,
        target_lang,
        has_runtime_patches=has_runtime_patches(state, image_patches, file_path),
    )
    return state, "text"


def invalidate_page_for_format_edit(
    image_states: dict,
    image_patches: dict,
    file_path: str,
    target_lang: str,
) -> tuple[dict, str]:
    state = get_page_state(image_states, file_path)
    finalize_render_stage(
        state,
        target_lang,
        has_runtime_patches=has_runtime_patches(state, image_patches, file_path),
        ui_stage="render",
    )
    return state, "render"


def invalidate_page_for_segmentation_edit(image_states: dict, image_patches: dict, file_path: str) -> tuple[dict, str]:
    state = get_page_state(image_states, file_path)
    invalidate_after_segmentation_edit(
        state,
        has_runtime_patches=has_runtime_patches(state, image_patches, file_path),
    )
    return state, "clean"
