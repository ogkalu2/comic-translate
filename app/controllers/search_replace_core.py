from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from PySide6 import QtCore, QtGui
from PySide6.QtGui import QTextCursor

from modules.utils.common_utils import is_close


@dataclass(frozen=True)
class BlockKey:
    file_path: str
    xyxy: tuple[int, int, int, int]
    angle: float


@dataclass(frozen=True)
class SearchOptions:
    query: str
    replace: str
    match_case: bool = False
    whole_word: bool = False
    regex: bool = False
    preserve_case: bool = False
    scope_all_images: bool = False
    in_target: bool = True


@dataclass(frozen=True)
class SearchMatch:
    key: BlockKey
    block_index_hint: int
    match_ordinal_in_block: int
    start: int
    end: int
    preview: str


def build_block_key(file_path: str, blk: object) -> BlockKey:
    return BlockKey(
        file_path=file_path,
        xyxy=(int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3])),
        angle=float(getattr(blk, "angle", 0.0) or 0.0),
    )


def _vscode_regex_replacement_to_python(repl: str) -> str:
    if not repl:
        return repl
    sentinel = "\u0000"
    repl = repl.replace("$$", sentinel)
    repl = repl.replace("$&", r"\g<0>")
    repl = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"\\g<\1>", repl)
    repl = re.sub(r"\$(\d+)", r"\\g<\1>", repl)
    return repl.replace(sentinel, "$")


def _apply_preserve_case(matched_text: str, replacement: str) -> str:
    if not matched_text or not replacement:
        return replacement
    if matched_text.islower():
        return replacement.lower()
    if matched_text.isupper():
        return replacement.upper()
    if matched_text.istitle():
        return replacement.title()
    if matched_text[0].isupper():
        return replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
    return replacement


def compile_search_pattern(opts: SearchOptions) -> re.Pattern[str]:
    query = (opts.query or "").strip()
    if not query:
        raise ValueError("Empty query")

    flags = re.UNICODE
    if not opts.match_case:
        flags |= re.IGNORECASE

    body = query if opts.regex else re.escape(query)
    if opts.whole_word:
        body = rf"(?<!\w)(?:{body})(?!\w)"
    return re.compile(body, flags=flags)


def find_matches_in_text(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for match in pattern.finditer(text or ""):
        if match.start() == match.end():
            continue
        out.append((match.start(), match.end()))
    return out


def _make_preview(text: str, start: int, end: int, radius: int = 30) -> str:
    safe = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    left = max(0, start - radius)
    right = min(len(safe), end + radius)
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(safe) else ""
    return f"{prefix}{safe[left:right]}{suffix}"


def _looks_like_html(text: str) -> bool:
    return bool(text and re.search(r"<[^>]+>", text))


def _to_qt_plain(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\u2029")


def _qt_plain_to_user(text: str) -> str:
    return (text or "").replace("\u2029", "\n")


def _apply_replacements_to_html(
    existing_html: str,
    pattern: re.Pattern[str],
    replacement: str,
    *,
    regex_mode: bool,
    preserve_case: bool = False,
    nth: int | None = None,
) -> tuple[str, str, str, int]:
    doc = QtGui.QTextDocument()
    if _looks_like_html(existing_html):
        doc.setHtml(existing_html)
    else:
        doc.setPlainText(existing_html or "")

    old_plain = _qt_plain_to_user(doc.toPlainText())
    matches = [match for match in pattern.finditer(old_plain) if match.start() != match.end()]
    if nth is not None:
        if nth < 0 or nth >= len(matches):
            return old_plain, old_plain, doc.toHtml(), 0
        matches = [matches[nth]]
    if not matches:
        return old_plain, old_plain, doc.toHtml(), 0

    py_repl = _vscode_regex_replacement_to_python(replacement) if regex_mode else replacement
    for match in reversed(matches):
        start, end = match.start(), match.end()
        try:
            repl_text = match.expand(py_repl) if regex_mode else py_repl
        except Exception:
            repl_text = py_repl if isinstance(py_repl, str) else ""
        if preserve_case:
            repl_text = _apply_preserve_case(old_plain[start:end], repl_text)

        fmt_cur = QTextCursor(doc)
        fmt_cur.setPosition(start)
        fmt = fmt_cur.charFormat()

        cursor = QTextCursor(doc)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(_to_qt_plain(repl_text), fmt)
        cursor.endEditBlock()

    return old_plain, _qt_plain_to_user(doc.toPlainText()), doc.toHtml(), len(matches)


def _rect_area(rect: QtCore.QRectF) -> float:
    return max(0.0, float(rect.width())) * max(0.0, float(rect.height()))


def _apply_text_delta_to_document(doc: QtGui.QTextDocument, new_text: str) -> bool:
    old_text = doc.toPlainText()
    new_text_qt = _to_qt_plain(new_text)
    if old_text == new_text_qt:
        return False

    prefix = 0
    max_prefix = min(len(old_text), len(new_text_qt))
    while prefix < max_prefix and old_text[prefix] == new_text_qt[prefix]:
        prefix += 1

    suffix = 0
    max_suffix = min(len(old_text) - prefix, len(new_text_qt) - prefix)
    while suffix < max_suffix and old_text[-(suffix + 1)] == new_text_qt[-(suffix + 1)]:
        suffix += 1

    old_mid_end = len(old_text) - suffix
    new_mid_end = len(new_text_qt) - suffix
    old_mid = old_text[prefix:old_mid_end]
    new_mid = new_text_qt[prefix:new_mid_end]

    cursor = QTextCursor(doc)
    insert_format = None
    if old_text:
        if prefix < len(old_text):
            cursor.setPosition(prefix)
            insert_format = cursor.charFormat()
        elif prefix > 0:
            cursor.setPosition(prefix - 1)
            insert_format = cursor.charFormat()

    cursor.beginEditBlock()
    if old_mid:
        cursor.setPosition(prefix)
        cursor.setPosition(prefix + len(old_mid), QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
    if new_mid:
        cursor.setPosition(prefix)
        if insert_format is not None:
            cursor.setCharFormat(insert_format)
        cursor.insertText(new_mid)
    cursor.endEditBlock()
    return True


def replace_nth_match(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    n: int,
    regex_mode: bool,
) -> tuple[str, bool]:
    if n < 0:
        return text, False
    matches = [match for match in pattern.finditer(text or "") if match.start() != match.end()]
    if n >= len(matches):
        return text, False
    match = matches[n]
    repl_text = match.expand(_vscode_regex_replacement_to_python(replacement)) if regex_mode else replacement
    return text[: match.start()] + repl_text + text[match.end() :], True


def replace_all_matches(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    regex_mode: bool,
    preserve_case: bool = False,
) -> tuple[str, int]:
    if regex_mode:
        py_repl = _vscode_regex_replacement_to_python(replacement)
        if preserve_case:
            def repl_func(match):
                return _apply_preserve_case(match.group(0), match.expand(py_repl))
            return pattern.subn(repl_func, text or "")
        return pattern.subn(py_repl, text or "")

    if preserve_case:
        def repl_func(match):
            return _apply_preserve_case(match.group(0), replacement)
        return pattern.subn(repl_func, text or "")
    return pattern.subn(lambda _match: replacement, text or "")


def find_block_by_key(blks: list, key: BlockKey, *, angle_tolerance: float = 0.5) -> Optional[object]:
    for blk in blks or []:
        xyxy = (int(blk.xyxy[0]), int(blk.xyxy[1]), int(blk.xyxy[2]), int(blk.xyxy[3]))
        angle = float(getattr(blk, "angle", 0.0) or 0.0)
        if xyxy == key.xyxy and is_close(angle, key.angle, angle_tolerance):
            return blk
    return None


def find_matching_text_item_state(state: dict, key: BlockKey) -> Optional[dict]:
    viewer_state = state.get("viewer_state") or {}
    text_items_state = viewer_state.get("text_items_state") or []
    for text_item_state in text_items_state:
        pos = text_item_state.get("position") or (None, None)
        rot = float(text_item_state.get("rotation") or 0.0)
        if pos[0] is None:
            continue
        if (
            is_close(float(pos[0]), float(key.xyxy[0]), 5)
            and is_close(float(pos[1]), float(key.xyxy[1]), 5)
            and is_close(rot, key.angle, 1.0)
        ):
            return text_item_state
    return None
