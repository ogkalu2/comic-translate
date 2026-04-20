from __future__ import annotations

import json
from typing import Any


DEFAULT_PREVIOUS_PAGE_LINES = 6
MAX_DIALOGUE_LINE_CHARS = 160
MAX_SCENE_MEMORY_CHARS = 280


def translation_context_requires_ordering(llm_settings: dict | None) -> bool:
    settings = llm_settings or {}
    return bool(
        settings.get("use_previous_page_context")
        or settings.get("use_scene_memory")
    )


def build_translation_prompt_context(
    main_page,
    file_path: str | None,
    target_lang: str,
    *,
    llm_settings: dict | None = None,
) -> tuple[str, str]:
    settings = llm_settings or {}
    sections: list[str] = []

    user_context = (settings.get("extra_context") or "").strip()
    if user_context:
        sections.append(f"Additional context:\n{user_context}")

    if settings.get("use_previous_page_context"):
        previous_snapshot = _get_previous_page_snapshot(
            main_page,
            file_path,
            target_lang,
            llm_settings=settings,
        )
        if previous_snapshot:
            sections.append(
                "Previous page dialogue tail.\n"
                "Use it only to resolve references, ellipsis, sarcasm, and speaker intent for the current page:\n"
                f"{previous_snapshot}"
            )

    if settings.get("use_scene_memory"):
        scene_memory = _get_previous_scene_memory(main_page, file_path, target_lang)
        if scene_memory:
            sections.append(
                "Scene memory from the previous page.\n"
                "Use it only as soft continuity context and do not invent unsupported details:\n"
                f"{scene_memory}"
            )

    prompt_context = "\n\n".join(section for section in sections if section.strip())
    cache_signature = json.dumps(
        {
            "prompt_context": prompt_context,
            "use_page_image_context": bool(
                settings.get(
                    "use_page_image_context",
                    settings.get("image_input_enabled", False),
                )
            ),
            "use_previous_page_context": bool(settings.get("use_previous_page_context")),
            "use_scene_memory": bool(settings.get("use_scene_memory")),
            "interpret_then_translate": bool(settings.get("interpret_then_translate")),
            "previous_page_lines": _resolve_previous_page_lines(settings),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return prompt_context, cache_signature


def store_page_translation_context(
    image_states: dict,
    file_path: str,
    target_lang: str,
    blk_list: list | None,
    *,
    scene_memory: str = "",
    llm_settings: dict | None = None,
) -> None:
    if not file_path or not isinstance(image_states, dict):
        return

    settings = llm_settings or {}
    page_snapshot = _build_page_dialogue_snapshot(
        blk_list,
        max_lines=_resolve_previous_page_lines(settings),
    )
    if not page_snapshot and not scene_memory:
        return

    state = image_states.setdefault(file_path, {})
    translation_context = state.setdefault("translation_context", {})
    if not isinstance(translation_context, dict):
        translation_context = {}
        state["translation_context"] = translation_context

    fallback_memory = _build_fallback_scene_memory(blk_list)
    translation_context[target_lang or ""] = {
        "page_snapshot": page_snapshot,
        "scene_memory": (scene_memory or fallback_memory).strip()[:MAX_SCENE_MEMORY_CHARS],
    }


def _resolve_previous_page_lines(llm_settings: dict | None) -> int:
    settings = llm_settings or {}
    raw_value = settings.get("previous_page_lines", settings.get("context_tail_turns", DEFAULT_PREVIOUS_PAGE_LINES))
    try:
        return max(1, min(20, int(raw_value)))
    except (TypeError, ValueError):
        return DEFAULT_PREVIOUS_PAGE_LINES


def _get_previous_file_path(image_files: list[str], file_path: str | None) -> str:
    if not file_path:
        return ""
    try:
        index = image_files.index(file_path)
    except ValueError:
        return ""
    if index <= 0:
        return ""
    return image_files[index - 1]


def _get_previous_page_snapshot(
    main_page,
    file_path: str | None,
    target_lang: str,
    *,
    llm_settings: dict | None = None,
) -> str:
    previous_file = _get_previous_file_path(getattr(main_page, "image_files", []) or [], file_path)
    if not previous_file:
        return ""

    image_states = getattr(main_page, "image_states", {}) or {}
    state = image_states.get(previous_file) or {}
    lines_limit = _resolve_previous_page_lines(llm_settings)

    entry = _get_target_translation_context_entry(state, target_lang)
    if entry:
        return (entry.get("page_snapshot") or "").strip()

    if state.get("target_lang") != target_lang:
        return ""

    return _build_page_dialogue_snapshot(state.get("blk_list"), max_lines=lines_limit)


def _get_previous_scene_memory(main_page, file_path: str | None, target_lang: str) -> str:
    previous_file = _get_previous_file_path(getattr(main_page, "image_files", []) or [], file_path)
    if not previous_file:
        return ""

    image_states = getattr(main_page, "image_states", {}) or {}
    state = image_states.get(previous_file) or {}
    entry = _get_target_translation_context_entry(state, target_lang)
    if entry:
        return (entry.get("scene_memory") or "").strip()

    if state.get("target_lang") != target_lang:
        return ""

    return _build_fallback_scene_memory(state.get("blk_list"))


def _get_target_translation_context_entry(state: dict | None, target_lang: str) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    translation_context = state.get("translation_context")
    if not isinstance(translation_context, dict):
        return {}
    entry = translation_context.get(target_lang or "")
    if isinstance(entry, dict):
        return entry
    return {}


def _build_page_dialogue_snapshot(blk_list: list | None, *, max_lines: int) -> str:
    snapshot_lines: list[str] = []
    for blk in list(blk_list or [])[-max_lines:]:
        source_text = _compact_text(getattr(blk, "text", "") or "")
        translated_text = _compact_text(getattr(blk, "translation", "") or "")
        if not source_text and not translated_text:
            continue
        if translated_text:
            snapshot_lines.append(f"- src: {source_text}\n  trg: {translated_text}")
        else:
            snapshot_lines.append(f"- src: {source_text}")
    return "\n".join(snapshot_lines)


def _build_fallback_scene_memory(blk_list: list | None) -> str:
    parts: list[str] = []
    for blk in blk_list or []:
        text = _compact_text(
            (getattr(blk, "translation", "") or "").strip()
            or (getattr(blk, "text", "") or "").strip()
        )
        if text:
            parts.append(text)
        if len(parts) >= 3:
            break
    return " | ".join(parts)[:MAX_SCENE_MEMORY_CHARS]


def _compact_text(text: str) -> str:
    compact = " ".join(str(text).split())
    if len(compact) > MAX_DIALOGUE_LINE_CHARS:
        return compact[: MAX_DIALOGUE_LINE_CHARS - 3].rstrip() + "..."
    return compact
