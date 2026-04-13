from __future__ import annotations

from copy import deepcopy


PAGE_STAGE_KEYS = ("detect", "ocr", "segment", "clean")
TARGET_STAGE_KEYS = ("translate", "render")
STAGE_ORDER = ("detect", "ocr", "translate", "segment", "clean", "render")

LEGACY_COMPLETED_STAGE_MAP = {
    "detect": "detection",
    "ocr": "ocr",
    "clean": "inpaint",
    "translate": "translate",
    "render": "render",
}


def _default_page_validity() -> dict[str, bool]:
    return {stage: False for stage in PAGE_STAGE_KEYS}


def _default_target_validity() -> dict[str, bool]:
    return {stage: False for stage in TARGET_STAGE_KEYS}


def default_pipeline_state() -> dict:
    return {
        "completed_stages": [],
        "target_lang": "",
        "inpaint_hash": "",
        "translator_key": "",
        "extra_context_hash": "",
        "ocr_cache_key": "",
        "page_validity": _default_page_validity(),
        "target_validity": {},
        "current_stage": "",
    }


def _coerce_page_validity(value) -> dict[str, bool]:
    data = _default_page_validity()
    if isinstance(value, dict):
        for key in PAGE_STAGE_KEYS:
            data[key] = bool(value.get(key, False))
    return data


def _coerce_target_validity(value) -> dict[str, dict[str, bool]]:
    result: dict[str, dict[str, bool]] = {}
    if not isinstance(value, dict):
        return result
    for target_lang, target_state in value.items():
        if not isinstance(target_lang, str):
            continue
        validity = _default_target_validity()
        if isinstance(target_state, dict):
            for key in TARGET_STAGE_KEYS:
                validity[key] = bool(target_state.get(key, False))
        result[target_lang] = validity
    return result


def ensure_pipeline_state(
    state: dict | None,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> dict:
    if state is None:
        state = {}

    ps = state.get("pipeline_state")
    raw_page_validity = ps.get("page_validity") if isinstance(ps, dict) else None
    raw_target_validity = ps.get("target_validity") if isinstance(ps, dict) else None
    if not isinstance(ps, dict):
        ps = default_pipeline_state()
        state["pipeline_state"] = ps

    defaults = default_pipeline_state()
    for key, value in defaults.items():
        if key not in ps:
            ps[key] = deepcopy(value)

    ps["page_validity"] = _coerce_page_validity(ps.get("page_validity"))
    ps["target_validity"] = _coerce_target_validity(ps.get("target_validity"))
    page_validity_explicit = isinstance(raw_page_validity, dict) and any(
        key in raw_page_validity for key in PAGE_STAGE_KEYS
    )
    explicit_target_validity_keys = {
        key
        for key, value in (raw_target_validity.items() if isinstance(raw_target_validity, dict) else [])
        if isinstance(value, dict) and any(stage in value for stage in TARGET_STAGE_KEYS)
    }

    completed = set(ps.get("completed_stages", []) or [])
    blk_list = state.get("blk_list") or []
    inpaint_cache = state.get("inpaint_cache") or []
    brush_strokes = state.get("brush_strokes") or []

    if not page_validity_explicit:
        if blk_list or "detection" in completed:
            ps["page_validity"]["detect"] = True
        if "ocr" in completed:
            ps["page_validity"]["ocr"] = True
        if "inpaint" in completed or inpaint_cache or has_runtime_patches:
            ps["page_validity"]["clean"] = True
        if brush_strokes or any(getattr(blk, "inpaint_bboxes", None) is not None for blk in blk_list):
            ps["page_validity"]["segment"] = True

    active_target = target_lang or state.get("target_lang") or ps.get("target_lang") or ""
    if active_target:
        target_state = ps["target_validity"].setdefault(active_target, _default_target_validity())
        if active_target not in explicit_target_validity_keys:
            if "translate" in completed and ps.get("target_lang") in ("", active_target):
                target_state["translate"] = True

            target_render_states = state.get("target_render_states") or {}
            target_snapshot = target_render_states.get(active_target)
            if target_snapshot is None and ps.get("target_lang") in ("", active_target):
                viewer_state = state.get("viewer_state") or {}
                if viewer_state.get("text_items_state"):
                    target_snapshot = viewer_state
            if target_snapshot is not None and "render" in completed and ps.get("target_lang") in ("", active_target):
                target_state["render"] = True

    current_stage = ps.get("current_stage") or ""
    if current_stage not in STAGE_ORDER or not _is_stage_available_from_ps(
        state,
        ps,
        current_stage,
        target_lang=active_target,
    ):
        ps["current_stage"] = _best_available_stage_from_ps(
            state,
            ps,
            target_lang=active_target,
        )

    sync_legacy_completed_stages(
        state,
        target_lang=active_target,
        has_runtime_patches=has_runtime_patches,
    )
    return ps


def ensure_target_validity(ps: dict, target_lang: str) -> dict[str, bool]:
    target_validity = _coerce_target_validity(ps.get("target_validity"))
    ps["target_validity"] = target_validity
    return target_validity.setdefault(target_lang, _default_target_validity())


def _resolve_target_lang(state: dict | None, ps: dict, target_lang: str = "") -> str:
    if target_lang:
        return target_lang
    if isinstance(state, dict) and state.get("target_lang"):
        return state.get("target_lang") or ""
    if isinstance(ps, dict) and ps.get("target_lang"):
        return ps.get("target_lang") or ""
    return ""


def resolve_target_lang(
    state: dict | None,
    *,
    preferred_target: str = "",
    pipeline_state: dict | None = None,
) -> str:
    ps = pipeline_state if isinstance(pipeline_state, dict) else {}
    return _resolve_target_lang(state, ps, preferred_target)


def activate_target_lang(
    state: dict,
    target_lang: str = "",
    *,
    has_runtime_patches: bool = False,
) -> tuple[dict, str]:
    resolved_target = resolve_target_lang(state, preferred_target=target_lang)
    ps = ensure_pipeline_state(
        state,
        target_lang=resolved_target,
        has_runtime_patches=has_runtime_patches,
    )
    if resolved_target:
        state["target_lang"] = resolved_target
        ps["target_lang"] = resolved_target
    return ps, resolved_target


def finalize_render_stage(
    state: dict,
    target_lang: str = "",
    *,
    has_runtime_patches: bool = False,
    ui_stage: str = "render",
) -> tuple[dict, str]:
    ps, resolved_target = activate_target_lang(
        state,
        target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    if not resolved_target:
        return ps, resolved_target

    target_state = ensure_target_validity(ps, resolved_target)
    target_state["translate"] = True
    target_state["render"] = True
    sync_legacy_completed_stages(
        state,
        target_lang=resolved_target,
        has_runtime_patches=has_runtime_patches,
    )

    if _is_stage_available_from_ps(
        state,
        ps,
        "render",
        target_lang=resolved_target,
    ):
        ps["current_stage"] = "render"
    else:
        ps["current_stage"] = _best_available_stage_from_ps(
            state,
            ps,
            target_lang=resolved_target,
        )

    if ui_stage:
        state["ui_stage"] = ui_stage
    return ps, resolved_target


def _is_stage_available_from_ps(
    state: dict | None,
    ps: dict,
    stage: str,
    *,
    target_lang: str = "",
) -> bool:
    if state is None or stage not in STAGE_ORDER:
        return False

    page_validity = ps["page_validity"]
    if stage == "detect":
        return bool(page_validity["detect"])
    if stage == "ocr":
        return bool(page_validity["detect"] and page_validity["ocr"])
    if stage == "segment":
        return bool(page_validity["detect"] and page_validity["segment"])
    if stage == "clean":
        return bool(page_validity["clean"])

    resolved_target = _resolve_target_lang(state, ps, target_lang)
    if not resolved_target:
        return False

    target_state = ensure_target_validity(ps, resolved_target)
    if stage == "translate":
        return bool(page_validity["detect"] and page_validity["ocr"] and target_state["translate"])
    if stage == "render":
        return bool(target_state["render"])
    return False


def _best_available_stage_from_ps(
    state: dict | None,
    ps: dict,
    *,
    target_lang: str = "",
) -> str:
    if state is None:
        return ""
    for stage in ("render", "clean", "translate", "segment", "ocr", "detect"):
        if _is_stage_available_from_ps(
            state,
            ps,
            stage,
            target_lang=target_lang,
        ):
            return stage
    return ""


def is_stage_available(
    state: dict | None,
    stage: str,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> bool:
    if state is None or stage not in STAGE_ORDER:
        return False

    ps = ensure_pipeline_state(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    return _is_stage_available_from_ps(
        state,
        ps,
        stage,
        target_lang=target_lang,
    )


def best_available_stage(
    state: dict | None,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> str:
    if state is None:
        return ""
    ps = ensure_pipeline_state(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    return _best_available_stage_from_ps(
        state,
        ps,
        target_lang=target_lang,
    )


def set_page_stage_validity(
    state: dict,
    stage: str,
    valid: bool,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> dict:
    ps = ensure_pipeline_state(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    if stage in PAGE_STAGE_KEYS:
        ps["page_validity"][stage] = bool(valid)
    sync_legacy_completed_stages(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    return ps


def set_target_stage_validity(
    state: dict,
    target_lang: str,
    stage: str,
    valid: bool,
    *,
    has_runtime_patches: bool = False,
) -> dict:
    ps = ensure_pipeline_state(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    if target_lang and stage in TARGET_STAGE_KEYS:
        ensure_target_validity(ps, target_lang)[stage] = bool(valid)
    sync_legacy_completed_stages(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    return ps


def set_current_stage(
    state: dict,
    stage: str,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    if stage and _is_stage_available_from_ps(
        state,
        ps,
        stage,
        target_lang=target_lang,
    ):
        ps["current_stage"] = stage
    else:
        ps["current_stage"] = _best_available_stage_from_ps(
            state,
            ps,
            target_lang=target_lang,
        )
    return ps["current_stage"]


def get_current_stage(
    state: dict,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(
        state,
        target_lang=target_lang,
        has_runtime_patches=has_runtime_patches,
    )
    return ps.get("current_stage") or _best_available_stage_from_ps(
        state,
        ps,
        target_lang=target_lang,
    )


def sync_legacy_completed_stages(
    state: dict,
    *,
    target_lang: str = "",
    has_runtime_patches: bool = False,
) -> dict:
    ps = state.get("pipeline_state")
    if not isinstance(ps, dict):
        ps = default_pipeline_state()
        state["pipeline_state"] = ps

    completed: set[str] = set()
    page_validity = _coerce_page_validity(ps.get("page_validity"))
    if page_validity["detect"]:
        completed.add(LEGACY_COMPLETED_STAGE_MAP["detect"])
    if page_validity["ocr"]:
        completed.add(LEGACY_COMPLETED_STAGE_MAP["ocr"])
    if page_validity["clean"]:
        completed.add(LEGACY_COMPLETED_STAGE_MAP["clean"])

    resolved_target = target_lang or state.get("target_lang") or ps.get("target_lang") or ""
    if resolved_target:
        target_state = ensure_target_validity(ps, resolved_target)
        if target_state["translate"]:
            completed.add(LEGACY_COMPLETED_STAGE_MAP["translate"])
        if target_state["render"] and page_validity["clean"]:
            completed.add(LEGACY_COMPLETED_STAGE_MAP["render"])

    ps["completed_stages"] = sorted(completed)
    return ps


def invalidate_after_box_edit(
    state: dict,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, has_runtime_patches=has_runtime_patches)
    ps["page_validity"]["detect"] = bool(state.get("blk_list"))
    ps["page_validity"]["ocr"] = False
    ps["page_validity"]["segment"] = False
    ps["page_validity"]["clean"] = False
    for target_state in ps["target_validity"].values():
        target_state["translate"] = False
        target_state["render"] = False
    sync_legacy_completed_stages(state, has_runtime_patches=has_runtime_patches)
    ps["current_stage"] = "detect" if ps["page_validity"]["detect"] else ""
    return ps["current_stage"]


def invalidate_after_source_text_edit(
    state: dict,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, has_runtime_patches=has_runtime_patches)
    for target_state in ps["target_validity"].values():
        target_state["translate"] = False
        target_state["render"] = False
    sync_legacy_completed_stages(state, has_runtime_patches=has_runtime_patches)
    ps["current_stage"] = "ocr" if ps["page_validity"]["ocr"] else best_available_stage(state, has_runtime_patches=has_runtime_patches)
    return ps["current_stage"]


def invalidate_after_translated_text_edit(
    state: dict,
    target_lang: str,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    ensure_target_validity(ps, target_lang)["render"] = False
    sync_legacy_completed_stages(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    ps["current_stage"] = "translate" if is_stage_available(state, "translate", target_lang=target_lang, has_runtime_patches=has_runtime_patches) else best_available_stage(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    return ps["current_stage"]


def invalidate_after_format_edit(
    state: dict,
    target_lang: str,
    *,
    has_runtime_patches: bool = False,
) -> str:
    return invalidate_after_translated_text_edit(
        state,
        target_lang,
        has_runtime_patches=has_runtime_patches,
    )


def invalidate_after_segmentation_edit(
    state: dict,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, has_runtime_patches=has_runtime_patches)
    ps["page_validity"]["segment"] = True
    ps["page_validity"]["clean"] = False
    sync_legacy_completed_stages(state, has_runtime_patches=has_runtime_patches)
    ps["current_stage"] = "segment"
    return ps["current_stage"]


def mark_clean_ready(
    state: dict,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, has_runtime_patches=has_runtime_patches)
    ps["page_validity"]["clean"] = True
    sync_legacy_completed_stages(state, has_runtime_patches=has_runtime_patches)
    if not ps.get("current_stage"):
        ps["current_stage"] = best_available_stage(state, has_runtime_patches=has_runtime_patches)
    return ps["current_stage"]


def mark_ocr_ready(
    state: dict,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, has_runtime_patches=has_runtime_patches)
    ps["page_validity"]["detect"] = bool(state.get("blk_list"))
    ps["page_validity"]["ocr"] = True
    sync_legacy_completed_stages(state, has_runtime_patches=has_runtime_patches)
    return ps.get("current_stage") or best_available_stage(state, has_runtime_patches=has_runtime_patches)


def mark_translate_ready(
    state: dict,
    target_lang: str,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    ensure_target_validity(ps, target_lang)["translate"] = True
    sync_legacy_completed_stages(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    return ps.get("current_stage") or best_available_stage(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)


def mark_render_ready(
    state: dict,
    target_lang: str,
    *,
    has_runtime_patches: bool = False,
) -> str:
    ps = ensure_pipeline_state(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    target_state = ensure_target_validity(ps, target_lang)
    target_state["translate"] = True
    target_state["render"] = True
    sync_legacy_completed_stages(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
    return ps.get("current_stage") or best_available_stage(state, target_lang=target_lang, has_runtime_patches=has_runtime_patches)
