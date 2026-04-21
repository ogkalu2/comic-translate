from __future__ import annotations

from dataclasses import dataclass

from .render_state import get_target_snapshot
from .stage_state import activate_target_lang, ensure_pipeline_state, resolve_target_lang


@dataclass(slots=True)
class PageStateContext:
    file_path: str
    state: dict
    target_lang: str
    has_runtime_patches: bool

    @property
    def pipeline_state(self) -> dict:
        return self.state.setdefault("pipeline_state", {})


def get_page_state(image_states: dict, file_path: str) -> dict:
    return image_states.setdefault(file_path, {})


def get_runtime_patches(
    state: dict | None,
    image_patches: dict | None,
    file_path: str,
) -> list[dict]:
    if isinstance(image_patches, dict) and file_path:
        patches = image_patches.get(file_path, []) or []
        if patches:
            return patches
    if isinstance(state, dict):
        inpaint_cache = state.get("inpaint_cache") or []
        if inpaint_cache:
            return inpaint_cache
    return []


def has_runtime_patches(
    state: dict | None,
    image_patches: dict | None,
    file_path: str,
) -> bool:
    return bool(get_runtime_patches(state, image_patches, file_path))


def sync_inpaint_cache_from_image_patches(
    image_states: dict | None,
    image_patches: dict | None,
) -> None:
    """Keep serialized page state aligned with materialized patch paths."""
    if not isinstance(image_states, dict) or not isinstance(image_patches, dict):
        return

    for file_path, state in image_states.items():
        if not isinstance(state, dict):
            continue
        patches = image_patches.get(file_path) or []
        if patches:
            state["inpaint_cache"] = [dict(patch) for patch in patches]


def resolve_page_target_lang(
    state: dict | None,
    *,
    preferred_target: str = "",
    pipeline_state: dict | None = None,
) -> str:
    return resolve_target_lang(
        state,
        preferred_target=preferred_target,
        pipeline_state=pipeline_state,
    )


def build_page_state_context(
    image_states: dict,
    image_patches: dict | None,
    file_path: str,
    *,
    preferred_target: str = "",
    ensure_state: bool = False,
    activate_target: bool = False,
) -> PageStateContext:
    state = get_page_state(image_states, file_path)
    runtime_patches = has_runtime_patches(state, image_patches, file_path)

    if activate_target:
        _pipeline_state, target_lang = activate_target_lang(
            state,
            preferred_target,
            has_runtime_patches=runtime_patches,
        )
    else:
        target_lang = resolve_page_target_lang(
            state,
            preferred_target=preferred_target,
            pipeline_state=state.get("pipeline_state"),
        )
        if ensure_state:
            ensure_pipeline_state(
                state,
                target_lang=target_lang,
                has_runtime_patches=runtime_patches,
            )

    return PageStateContext(
        file_path=file_path,
        state=state,
        target_lang=target_lang,
        has_runtime_patches=runtime_patches,
    )


def get_active_viewer_state(
    state: dict | None,
    *,
    target_lang: str = "",
    preferred_target: str = "",
    fallback_to_viewer_state: bool = True,
) -> dict:
    if not isinstance(state, dict):
        return {}

    resolved_target = resolve_page_target_lang(
        state,
        preferred_target=target_lang or preferred_target,
        pipeline_state=state.get("pipeline_state"),
    )
    if resolved_target:
        snapshot = get_target_snapshot(
            state,
            resolved_target,
            fallback_to_viewer_state=fallback_to_viewer_state,
        )
        if snapshot:
            return snapshot
    return state.get("viewer_state") or {}
