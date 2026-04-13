from __future__ import annotations

from copy import deepcopy


def get_target_render_states(state: dict | None) -> dict[str, dict]:
    if state is None:
        return {}
    target_render_states = state.get("target_render_states")
    if not isinstance(target_render_states, dict):
        target_render_states = {}
        state["target_render_states"] = target_render_states
    return target_render_states


def get_target_snapshot(
    state: dict | None,
    target_lang: str,
    *,
    fallback_to_viewer_state: bool = True,
) -> dict:
    if state is None or not target_lang:
        return {}

    target_render_states = get_target_render_states(state)
    snapshot = target_render_states.get(target_lang)
    if snapshot:
        return snapshot

    viewer_state = state.get("viewer_state") or {}
    if fallback_to_viewer_state and viewer_state.get("text_items_state"):
        return viewer_state
    return {}


def ensure_target_snapshot(
    state: dict,
    target_lang: str,
    *,
    source_target: str = "",
    fallback_snapshot: dict | None = None,
) -> dict:
    if not target_lang:
        return {}

    target_render_states = get_target_render_states(state)
    existing = target_render_states.get(target_lang)
    if existing:
        return existing

    source_snapshot = target_render_states.get(source_target) if source_target else None
    if not source_snapshot:
        source_snapshot = fallback_snapshot
    if not source_snapshot:
        source_snapshot = state.get("viewer_state") or {}

    if source_snapshot:
        target_render_states[target_lang] = deepcopy(source_snapshot)
        return target_render_states[target_lang]
    return {}


def set_target_snapshot(state: dict, target_lang: str, snapshot: dict | None) -> dict:
    if not target_lang:
        return {}
    target_render_states = get_target_render_states(state)
    target_render_states[target_lang] = deepcopy(snapshot or {})
    return target_render_states[target_lang]


def build_render_template_map_from_snapshot(snapshot: dict | None) -> dict[tuple[str, tuple[int, int, int, int], float], dict]:
    template_map: dict[tuple[str, tuple[int, int, int, int], float], dict] = {}
    for item in (snapshot or {}).get("text_items_state", []) or []:
        if not isinstance(item, dict):
            continue
        position = item.get("position") or (0, 0)
        width = item.get("width") or 0
        height = item.get("height") or 0
        rect_key = (
            "",
            (
                int(position[0]),
                int(position[1]),
                int(position[0] + width),
                int(position[1] + height),
            ),
            float(item.get("rotation", 0.0) or 0.0),
        )
        template_map[rect_key] = dict(item)
        block_uid = str(item.get("block_uid", "") or "")
        if block_uid:
            template_map[(block_uid, (), 0.0)] = dict(item)
    return template_map


def build_render_template_map(
    state: dict | None,
    target_lang: str,
    *,
    fallback_to_viewer_state: bool = True,
) -> dict[tuple[str, tuple[int, int, int, int], float], dict]:
    snapshot = get_target_snapshot(
        state,
        target_lang,
        fallback_to_viewer_state=fallback_to_viewer_state,
    )
    return build_render_template_map_from_snapshot(snapshot)
