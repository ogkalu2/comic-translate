from __future__ import annotations

from copy import deepcopy

RENDER_STYLE_KEYS = {
    "block_uid",
    "font_family",
    "text_color",
    "alignment",
    "line_spacing",
    "outline_color",
    "outline_width",
    "outline",
    "second_outline",
    "second_outline_color",
    "second_outline_width",
    "text_gradient",
    "text_gradient_start_color",
    "text_gradient_end_color",
    "bold",
    "italic",
    "underline",
    "position",
    "rotation",
    "scale",
    "transform_origin",
    "width",
    "height",
}

RENDER_STYLE_OVERRIDES_KEY = "render_style_overrides"


def _sequence_value(value, index: int, default=0):
    if value is None:
        return default
    try:
        return value[index]
    except (TypeError, IndexError, KeyError):
        return default


def _numeric_value(value, default=0):
    return default if value is None else value


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
    apply_style_overrides: bool = True,
) -> dict:
    if state is None or not target_lang:
        return {}

    target_render_states = get_target_render_states(state)
    snapshot = target_render_states.get(target_lang)
    if snapshot:
        if apply_style_overrides:
            return apply_render_style_overrides_to_snapshot(state, snapshot)
        return snapshot

    viewer_state = state.get("viewer_state") or {}
    if fallback_to_viewer_state and viewer_state.get("text_items_state"):
        if apply_style_overrides:
            return apply_render_style_overrides_to_snapshot(state, viewer_state)
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
        target_render_states[target_lang] = _clone_snapshot_for_new_target(source_snapshot)
        return target_render_states[target_lang]
    return {}


def _outline_type_value(outline) -> str:
    outline_type = outline.get("type") if isinstance(outline, dict) else getattr(outline, "type", None)
    if outline_type is None:
        return ""
    value = getattr(outline_type, "value", outline_type)
    return str(value or "").lower()


def _outline_attr(outline, name: str):
    if isinstance(outline, dict):
        return outline.get(name)
    return getattr(outline, name, None)


def _clone_text_item_for_new_target(item: dict) -> dict:
    cloned = deepcopy(item)
    selection_outlines = cloned.pop("selection_outlines", None) or []
    if cloned.get("outline"):
        return cloned

    for outline in selection_outlines:
        if _outline_type_value(outline) != "full_document":
            continue
        cloned["outline"] = True
        if cloned.get("outline_color") is None:
            cloned["outline_color"] = deepcopy(_outline_attr(outline, "color"))
        if not cloned.get("outline_width"):
            outline_width = _outline_attr(outline, "width")
            if outline_width is not None:
                cloned["outline_width"] = deepcopy(outline_width)
        break

    return cloned


def _clone_snapshot_for_new_target(snapshot: dict | None) -> dict:
    cloned = deepcopy(snapshot or {})
    items = cloned.get("text_items_state")
    if isinstance(items, list):
        cloned["text_items_state"] = [
            _clone_text_item_for_new_target(item) if isinstance(item, dict) else item
            for item in items
        ]
    return cloned


def _item_identity(item: dict) -> tuple[str, tuple[int, int, int, int], float]:
    position = item.get("position")
    x = _sequence_value(position, 0)
    y = _sequence_value(position, 1)
    width = _numeric_value(item.get("width"))
    height = _numeric_value(item.get("height"))
    block_uid = str(item.get("block_uid", "") or "")
    rect_key = (
        int(x),
        int(y),
        int(x + width),
        int(y + height),
    )
    return block_uid, rect_key, float(item.get("rotation", 0.0) or 0.0)


def _style_override_key(item: dict) -> str:
    block_uid, rect_key, rotation = _item_identity(item)
    if block_uid:
        return f"uid:{block_uid}"
    x1, y1, x2, y2 = rect_key
    return f"rect:{x1}:{y1}:{x2}:{y2}:{rotation:g}"


def _style_patch(item: dict) -> dict:
    return {key: deepcopy(item[key]) for key in RENDER_STYLE_KEYS if key in item}


def _matching_item_indexes(items: list[dict], source_item: dict) -> list[int]:
    source_uid, source_rect, source_rotation = _item_identity(source_item)
    matches = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        uid, rect, rotation = _item_identity(item)
        if source_uid and uid == source_uid:
            matches.append(index)
            continue
        if not source_uid and rect == source_rect and rotation == source_rotation:
            matches.append(index)
    return matches


def _merge_render_styles_into_snapshot(target_snapshot: dict, source_snapshot: dict) -> None:
    source_items = (source_snapshot or {}).get("text_items_state", []) or []
    target_items = (target_snapshot or {}).get("text_items_state", []) or []
    if not source_items or not target_items:
        return

    for source_item in source_items:
        if not isinstance(source_item, dict):
            continue
        patch = _style_patch(source_item)
        if not patch:
            continue
        for index in _matching_item_indexes(target_items, source_item):
            target_items[index].update(deepcopy(patch))


def get_render_style_overrides(state: dict | None) -> dict[str, dict]:
    if state is None:
        return {}
    overrides = state.get(RENDER_STYLE_OVERRIDES_KEY)
    if not isinstance(overrides, dict):
        overrides = {}
        state[RENDER_STYLE_OVERRIDES_KEY] = overrides
    return overrides


def update_render_style_overrides(
    state: dict,
    snapshot: dict | None,
    *,
    overwrite: bool = True,
) -> dict[str, dict]:
    overrides = get_render_style_overrides(state)
    for item in (snapshot or {}).get("text_items_state", []) or []:
        if not isinstance(item, dict):
            continue
        patch = _style_patch(item)
        if patch:
            key = _style_override_key(item)
            if overwrite or key not in overrides:
                overrides[key] = patch
    return overrides


def _apply_style_overrides(snapshot: dict, overrides: dict[str, dict]) -> None:
    target_items = (snapshot or {}).get("text_items_state", []) or []
    for item in target_items:
        if not isinstance(item, dict):
            continue
        patch = overrides.get(_style_override_key(item))
        if patch:
            item.update(deepcopy(patch))


def apply_render_style_overrides_to_snapshot(state: dict | None, snapshot: dict | None) -> dict:
    styled_snapshot = deepcopy(snapshot or {})
    _apply_style_overrides(styled_snapshot, get_render_style_overrides(state))
    return styled_snapshot


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
        position = item.get("position")
        x = _sequence_value(position, 0)
        y = _sequence_value(position, 1)
        width = _numeric_value(item.get("width"))
        height = _numeric_value(item.get("height"))
        rect_key = (
            "",
            (
                int(x),
                int(y),
                int(x + width),
                int(y + height),
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
    template_map = build_render_template_map_from_snapshot(snapshot)
    for patch in get_render_style_overrides(state).values():
        for key, template in build_render_template_map_from_snapshot({"text_items_state": [patch]}).items():
            template_map.setdefault(key, template)
    return template_map


def get_render_template_for_block(
    template_map: dict[tuple[str, tuple[int, int, int, int], float], dict],
    blk,
) -> dict:
    block_uid = str(getattr(blk, "block_uid", "") or "")
    if block_uid:
        template = template_map.get((block_uid, (), 0.0))
        if template:
            return template

    xyxy = getattr(blk, "xyxy", None)
    return template_map.get(
        (
            "",
            (
                int(_sequence_value(xyxy, 0)),
                int(_sequence_value(xyxy, 1)),
                int(_sequence_value(xyxy, 2)),
                int(_sequence_value(xyxy, 3)),
            ),
            float(getattr(blk, "angle", 0.0) or 0.0),
        ),
        {},
    )
