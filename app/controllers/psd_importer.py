from __future__ import annotations

import logging
import os
import re
import struct
import tempfile
from dataclasses import dataclass
from typing import Any

import imkit as imk
import numpy as np
import photoshopapi as psapi
from PySide6 import QtCore, QtGui

from app.ui.canvas.text_item import OutlineInfo, OutlineType

logger = logging.getLogger(__name__)

_ps_to_qt_font_cache: dict[str, tuple[str, str | None, bool, bool]] = {}
_font_catalog_built = False


@dataclass
class ImportedPsdPage:
    source_path: str
    image_path: str
    rgb_image: np.ndarray
    viewer_state: dict[str, Any]
    warning: str | None = None


@dataclass(frozen=True)
class PsdImportContext:
    is_app_export: bool
    warning: str | None


def import_psd_files(paths: list[str]) -> list[ImportedPsdPage]:
    if not paths:
        return []

    out_dir = tempfile.mkdtemp(prefix="comic_translate_psd_import_")
    used_names: set[str] = set()
    pages: list[ImportedPsdPage] = []

    for src_path in paths:
        rgb_image, text_items_state, context = _read_single_psd(src_path)
        file_name = _unique_png_name(_safe_stem(src_path), used_names)
        out_path = os.path.join(out_dir, file_name)
        imk.write_image(out_path, rgb_image)

        height, width, _ = rgb_image.shape
        viewer_state = {
            "rectangles": [],
            "transform": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            "center": (float(width) / 2.0, float(height) / 2.0),
            "scene_rect": (0.0, 0.0, float(width), float(height)),
            "text_items_state": text_items_state,
        }
        pages.append(
            ImportedPsdPage(
                source_path=src_path,
                image_path=out_path,
                rgb_image=rgb_image,
                viewer_state=viewer_state,
                warning=context.warning,
            )
        )

    return pages


def prepare_psd_font_catalog() -> None:
    _ensure_font_catalog()


def _read_single_psd(path: str) -> tuple[np.ndarray, list[dict[str, Any]], PsdImportContext]:
    document = psapi.LayeredFile.read(path)
    flat_layers = _flat_layers(document)
    context = _classify_psd_document(document, flat_layers)

    if context.is_app_export:
        base_layer = _find_named_image_layer(flat_layers, "Raw Image")
        if base_layer is None:
            base_layer = _find_base_image_layer(flat_layers)

        if base_layer is None:
            rgb_image = np.full((int(document.height), int(document.width), 3), 255, dtype=np.uint8)
        else:
            rgb_image = _image_layer_to_rgb(base_layer)
    else:
        rgb_image = _flatten_visible_image_layers(flat_layers, int(document.height), int(document.width))

    if context.is_app_export:
        for patch_layer in _patch_layers(document):
            _blend_image_layer(rgb_image, patch_layer)

    text_items_state: list[dict[str, Any]] = []
    for layer in _text_layers(document, flat_layers):
        try:
            imported = _import_text_layer(layer)
        except Exception:
            logger.exception("Failed to import text layer: %s", getattr(layer, "name", "<unnamed>"))
            imported = None
        if imported is not None:
            text_items_state.append(imported)

    return rgb_image, text_items_state, context


def _classify_psd_document(document: Any, flat_layers: list[Any]) -> PsdImportContext:
    has_raw_image = _find_named_image_layer(flat_layers, "Raw Image") is not None
    has_editable_text = _find_group_by_name(getattr(document, "layers", []), "Editable Text") is not None
    has_patch_group = _find_group_by_name(getattr(document, "layers", []), "Inpaint Patches") is not None
    is_app_export = has_raw_image or has_editable_text or has_patch_group
    if is_app_export:
        unsupported_features = _collect_unsupported_import_features(flat_layers)
        if unsupported_features:
            return PsdImportContext(
                is_app_export=True,
                warning=QtCore.QCoreApplication.translate(
                    "Messages",
                    "This PSD was exported by this application, but it now contains Photoshop features "
                    "that are not fully supported on import. It may not appear exactly as it did in Photoshop.",
                ),
            )
        return PsdImportContext(is_app_export=True, warning=None)
    return PsdImportContext(
        is_app_export=False,
        warning=QtCore.QCoreApplication.translate(
            "Messages",
            "Imported a PSD that was not exported by this application. Visible image layers were flattened, "
            "and unsupported Photoshop features may not match exactly.",
        ),
    )


def _collect_unsupported_import_features(flat_layers: list[Any]) -> list[str]:
    features: list[str] = []
    has_unknown_layers = False
    for layer in flat_layers:
        if not bool(getattr(layer, "is_visible", True)):
            continue

        if _is_smart_object_layer(layer):
            _append_unique(features, "smart objects")
        if _layer_has_mask(layer):
            _append_unique(features, "pixel masks")
        if bool(getattr(layer, "clipping_mask", False)):
            _append_unique(features, "clipping masks")
        if _layer_has_non_default_blend_mode(layer):
            _append_unique(features, "blend modes")
        if _layer_has_non_default_opacity(layer):
            _append_unique(features, "layer opacity")
        if not (_is_group_layer(layer) or _is_image_layer(layer) or _is_text_layer(layer) or _is_smart_object_layer(layer)):
            has_unknown_layers = True

    if has_unknown_layers:
        _append_unique(features, "unsupported layer types")
    return features


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _flat_layers(document: Any) -> list[Any]:
    if hasattr(document, "flat_layers"):
        return list(document.flat_layers)
    if hasattr(document, "layers_flat"):
        return list(document.layers_flat)
    layers = list(getattr(document, "layers", []))
    group_types = tuple(type(layer) for layer in layers if hasattr(layer, "layers"))
    return list(_walk_layers(layers, group_types))


def _walk_layers(layers: list[Any], group_types: tuple[type, ...]):
    for layer in layers:
        yield layer
        if isinstance(layer, group_types):
            yield from _walk_layers(getattr(layer, "layers", []), group_types)


def _text_layers(document: Any, flat_layers: list[Any]) -> list[Any]:
    editable_group = _find_group_by_name(getattr(document, "layers", []), "Editable Text")
    if editable_group is not None:
        layers = [
            layer
            for layer in _walk_layers(editable_group.layers, _group_types())
            if _is_text_layer(layer)
        ]
    else:
        layers = [layer for layer in flat_layers if _is_text_layer(layer)]
    return [layer for layer in layers if bool(getattr(layer, "is_visible", True))]


def _patch_layers(document: Any) -> list[Any]:
    patch_group = _find_group_by_name(getattr(document, "layers", []), "Inpaint Patches")
    if patch_group is None:
        return []
    return [
        layer
        for layer in _walk_layers(patch_group.layers, _group_types())
        if _is_image_layer(layer) and bool(getattr(layer, "is_visible", True))
    ]


def _find_group_by_name(layers: list[Any], name: str) -> Any | None:
    group_types = _group_types()
    target = name.strip().lower()
    for layer in layers:
        if not isinstance(layer, group_types):
            continue
        if str(getattr(layer, "name", "")).strip().lower() == target:
            return layer
        nested = _find_group_by_name(getattr(layer, "layers", []), name)
        if nested is not None:
            return nested
    return None


def _find_named_image_layer(flat_layers: list[Any], name: str) -> Any | None:
    target = name.strip().lower()
    for layer in flat_layers:
        if _is_image_layer(layer) and str(getattr(layer, "name", "")).strip().lower() == target:
            return layer
    return None


def _find_base_image_layer(flat_layers: list[Any]) -> Any | None:
    for layer in reversed(flat_layers):
        if _is_image_layer(layer) and bool(getattr(layer, "is_visible", True)):
            return layer
    return None


def _flatten_visible_image_layers(flat_layers: list[Any], height: int, width: int) -> np.ndarray:
    base_rgb = np.full((height, width, 3), 255, dtype=np.uint8)
    visible_layers = [
        layer for layer in flat_layers
        if _is_image_layer(layer) and bool(getattr(layer, "is_visible", True))
    ]
    for layer in reversed(visible_layers):
        _blend_image_layer(base_rgb, layer)
    return base_rgb


def _layer_type_tuple(*names: str) -> tuple[type, ...]:
    return tuple(getattr(psapi, name) for name in names if hasattr(psapi, name))


def _group_types() -> tuple[type, ...]:
    return _layer_type_tuple("GroupLayer_8bit", "GroupLayer_16bit", "GroupLayer_32bit")


def _smart_object_types() -> tuple[type, ...]:
    return _layer_type_tuple("SmartObjectLayer_8bit", "SmartObjectLayer_16bit", "SmartObjectLayer_32bit")


def _is_group_layer(layer: Any) -> bool:
    return isinstance(layer, _group_types())


def _is_text_layer(layer: Any) -> bool:
    return isinstance(layer, _layer_type_tuple("TextLayer_8bit", "TextLayer_16bit", "TextLayer_32bit"))


def _is_image_layer(layer: Any) -> bool:
    return isinstance(layer, _layer_type_tuple("ImageLayer_8bit", "ImageLayer_16bit", "ImageLayer_32bit"))


def _is_smart_object_layer(layer: Any) -> bool:
    return isinstance(layer, _smart_object_types())


def _layer_has_mask(layer: Any) -> bool:
    has_mask = getattr(layer, "has_mask", None)
    if callable(has_mask):
        try:
            return bool(has_mask("mask"))
        except Exception:
            try:
                return bool(has_mask(""))
            except Exception:
                pass
    try:
        mask = getattr(layer, "mask", None)
        if mask is None:
            return False
        return bool(np.asarray(mask).size)
    except Exception:
        return False


def _layer_has_non_default_blend_mode(layer: Any) -> bool:
    blend_mode = getattr(layer, "blend_mode", None)
    enum_cls = getattr(getattr(psapi, "enum", None), "BlendMode", None)
    if enum_cls is None or blend_mode is None:
        return False
    if _is_group_layer(layer):
        return not (_enum_eq(blend_mode, enum_cls, "normal") or _enum_eq(blend_mode, enum_cls, "passthrough"))
    return not _enum_eq(blend_mode, enum_cls, "normal")


def _layer_has_non_default_opacity(layer: Any) -> bool:
    try:
        opacity = float(getattr(layer, "opacity", 1.0))
    except Exception:
        return False
    return abs(opacity - 1.0) > 1e-6


def _image_layer_to_rgb(layer: Any) -> np.ndarray:
    rgba = _image_layer_to_rgba(layer)
    return np.ascontiguousarray(rgba[:, :, :3])


def _image_layer_to_rgba(layer: Any) -> np.ndarray:
    height = int(getattr(layer, "height", 0))
    width = int(getattr(layer, "width", 0))
    if height <= 0 or width <= 0:
        return np.zeros((0, 0, 4), dtype=np.uint8)

    get_image_data = getattr(layer, "get_image_data", None)
    data: dict[int, np.ndarray] = {}
    if callable(get_image_data):
        try:
            data = dict(get_image_data())
        except Exception:
            data = {}

    channel_enum = getattr(getattr(psapi, "enum", None), "ChannelID", None)
    red_id = getattr(channel_enum, "red", 0)
    green_id = getattr(channel_enum, "green", 1)
    blue_id = getattr(channel_enum, "blue", 2)
    alpha_id = getattr(channel_enum, "alpha", -1)

    red = _read_channel(layer, data, red_id, 0, height, width)
    green = _read_channel(layer, data, green_id, 1, height, width)
    blue = _read_channel(layer, data, blue_id, 2, height, width)
    alpha = _read_channel(layer, data, alpha_id, -1, height, width)

    if red is None and green is None and blue is None:
        return np.zeros((height, width, 4), dtype=np.uint8)

    if red is None:
        red = np.copy(green if green is not None else blue)
    if green is None:
        green = np.copy(red)
    if blue is None:
        blue = np.copy(red)
    if alpha is None:
        alpha = np.full((height, width), 255, dtype=np.uint8)

    return np.dstack((red, green, blue, alpha))


def _read_channel(
    layer: Any,
    data: dict[int, np.ndarray],
    channel_id: Any,
    channel_index: int,
    height: int,
    width: int,
) -> np.ndarray | None:
    if channel_id in data:
        return _to_uint8_2d(data[channel_id], height, width)
    if channel_index in data:
        return _to_uint8_2d(data[channel_index], height, width)

    get_by_id = getattr(layer, "get_channel_by_id", None)
    if callable(get_by_id):
        try:
            return _to_uint8_2d(get_by_id(channel_id), height, width)
        except Exception:
            pass

    get_by_index = getattr(layer, "get_channel_by_index", None)
    if callable(get_by_index):
        try:
            return _to_uint8_2d(get_by_index(channel_index), height, width)
        except Exception:
            pass

    return None


def _to_uint8_2d(channel: Any, height: int, width: int) -> np.ndarray:
    array = np.asarray(channel)
    if array.ndim > 2:
        array = np.squeeze(array)
    if array.ndim != 2:
        array = np.resize(array, (height, width))

    if array.shape == (width, height):
        array = np.transpose(array, (1, 0))
    elif array.shape != (height, width):
        array = np.resize(array, (height, width))

    if array.dtype == np.uint8:
        return np.ascontiguousarray(array)
    if np.issubdtype(array.dtype, np.bool_):
        return np.ascontiguousarray(array.astype(np.uint8) * 255)
    if np.issubdtype(array.dtype, np.integer):
        info = np.iinfo(array.dtype)
        if info.max <= 255:
            return np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))
        scaled = np.clip((array.astype(np.float32) / float(info.max)) * 255.0, 0.0, 255.0)
        return np.ascontiguousarray(scaled.astype(np.uint8))
    if np.issubdtype(array.dtype, np.floating):
        finite = np.nan_to_num(array, nan=0.0, posinf=255.0, neginf=0.0).astype(np.float32)
        min_v = float(np.min(finite)) if finite.size else 0.0
        max_v = float(np.max(finite)) if finite.size else 0.0
        if 0.0 <= min_v and max_v <= 1.0:
            finite *= 255.0
        return np.ascontiguousarray(np.clip(finite, 0.0, 255.0).astype(np.uint8))
    return np.ascontiguousarray(np.clip(array.astype(np.float32), 0.0, 255.0).astype(np.uint8))


def _blend_image_layer(base_rgb: np.ndarray, patch_layer: Any) -> None:
    patch_rgba = _image_layer_to_rgba(patch_layer)
    if patch_rgba.size == 0:
        return

    patch_h, patch_w, _ = patch_rgba.shape
    cx = float(getattr(patch_layer, "center_x", 0.0))
    cy = float(getattr(patch_layer, "center_y", 0.0))
    x = int(round(cx - patch_w / 2.0))
    y = int(round(cy - patch_h / 2.0))

    dst_h, dst_w, _ = base_rgb.shape
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(dst_w, x + patch_w)
    y1 = min(dst_h, y + patch_h)
    if x1 <= x0 or y1 <= y0:
        return

    src_x0 = x0 - x
    src_y0 = y0 - y
    src_x1 = src_x0 + (x1 - x0)
    src_y1 = src_y0 + (y1 - y0)

    src_rgb = patch_rgba[src_y0:src_y1, src_x0:src_x1, :3].astype(np.float32)
    src_alpha = patch_rgba[src_y0:src_y1, src_x0:src_x1, 3:4].astype(np.float32) / 255.0
    dst_rgb = base_rgb[y0:y1, x0:x1].astype(np.float32)

    base_rgb[y0:y1, x0:x1] = np.clip(src_rgb * src_alpha + dst_rgb * (1.0 - src_alpha), 0.0, 255.0).astype(np.uint8)


def _u16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _import_text_layer(layer: Any) -> dict[str, Any] | None:
    text_value = getattr(layer, "text", None)
    if callable(text_value):
        text_value = text_value()
    if not text_value:
        return None

    plain_text = _normalize_text(str(text_value))
    if not plain_text:
        return None

    text_u16_len = _u16_len(plain_text)
    doc_end = _document_char_end(plain_text)
    style_runs = _read_style_runs(layer, text_u16_len)
    paragraph_runs = _read_paragraph_runs(layer, text_u16_len)
    html = _build_html_from_runs(plain_text, style_runs, paragraph_runs)
    outlines = _outline_infos(style_runs, text_u16_len, doc_end)
    full_outline = _find_full_outline(outlines, doc_end)
    primary = style_runs[0] if style_runs else _default_style(layer)
    alignment = paragraph_runs[0]["alignment"] if paragraph_runs else QtCore.Qt.AlignmentFlag.AlignLeft

    pos_x, pos_y = _position(layer)
    margin = _document_margin()
    box_w, box_h = _box_size(layer)
    if box_w is not None and box_w > 0:
        box_w += 2.0 * margin
    else:
        box_w = None
    if box_h is not None and box_h > 0:
        box_h += 2.0 * margin
    else:
        box_h = None

    rotation = _as_float(getattr(layer, "rotation_angle", None), 0.0)
    scale_x = _as_float(getattr(layer, "scale_x", None), 1.0)
    scale_y = _as_float(getattr(layer, "scale_y", None), scale_x)
    scale = scale_x if abs(scale_x - scale_y) < 1e-3 else (scale_x + scale_y) / 2.0

    return {
        "text": html,
        "font_family": primary["font_family"],
        "font_size": primary["font_size"],
        "text_color": QtGui.QColor(primary["fill_color"]),
        "alignment": alignment,
        "line_spacing": _line_spacing(primary),
        "outline_color": QtGui.QColor(full_outline.color) if full_outline is not None else None,
        "outline_width": float(full_outline.width) if full_outline is not None else 1.0,
        "outline": bool(full_outline is not None),
        "bold": bool(primary["bold"]),
        "italic": bool(primary["italic"]),
        "underline": bool(primary["underline"]),
        "direction": _direction(layer, primary.get("character_direction")),
        "position": (float(pos_x - margin), float(pos_y - margin)),
        "rotation": float(rotation),
        "scale": float(scale),
        "transform_origin": None,
        "width": box_w,
        "height": box_h,
        "vertical": _is_vertical(layer),
        "selection_outlines": outlines,
    }


def _read_style_runs(layer: Any, text_u16_len: int) -> list[dict[str, Any]]:
    lengths_fn = getattr(layer, "style_run_lengths", None)
    lengths = list(lengths_fn() or []) if callable(lengths_fn) else []
    runs: list[dict[str, Any]] = []
    cursor = 0

    for idx, length in enumerate(lengths):
        start = cursor
        cursor += max(0, int(length))
        end = min(cursor, text_u16_len)
        if end <= start:
            continue
        run = _style_run(layer, idx)
        run["start"] = start
        run["end"] = end
        runs.append(run)

    if not runs and text_u16_len > 0:
        base = _default_style(layer)
        base["start"] = 0
        base["end"] = text_u16_len
        runs.append(base)
    elif runs and runs[-1]["end"] < text_u16_len:
        runs[-1]["end"] = text_u16_len

    return runs


def _style_run(layer: Any, idx: int) -> dict[str, Any]:
    font_idx = _call_idx(layer, "style_run_font", idx, None)
    font_ps = _font_name(layer, font_idx) or _safe_text(getattr(layer, "primary_font_name", None)) or "ArialMT"
    family, style_name, ps_bold, ps_italic = _resolve_font_face_from_postscript(font_ps)

    fill = _argb_to_qcolor(_call_idx(layer, "style_run_fill_color", idx, None))
    if fill is None:
        fill = _argb_to_qcolor(_call(layer, "style_normal_fill_color", None)) or QtGui.QColor("#ff000000")
    stroke = _argb_to_qcolor(_call_idx(layer, "style_run_stroke_color", idx, None))
    if stroke is None:
        stroke = _argb_to_qcolor(_call(layer, "style_normal_stroke_color", None))

    bold_faux = _bool_or_default(_call_idx(layer, "style_run_faux_bold", idx, None), _bool_or_default(_call(layer, "style_normal_faux_bold", None), False))
    italic_faux = _bool_or_default(_call_idx(layer, "style_run_faux_italic", idx, None), _bool_or_default(_call(layer, "style_normal_faux_italic", None), False))

    return {
        "font_postscript": font_ps,
        "font_family": family,
        "font_style_name": style_name,
        "font_size": float(_as_float(_call_idx(layer, "style_run_font_size", idx, None), _as_float(_call(layer, "style_normal_font_size", None), 20.0))),
        "fill_color": fill,
        "bold": bool(bold_faux or ps_bold or _font_implies_bold(font_ps)),
        "italic": bool(italic_faux or ps_italic or _font_implies_italic(font_ps)),
        "underline": bool(_bool_or_default(_call_idx(layer, "style_run_underline", idx, None), _bool_or_default(_call(layer, "style_normal_underline", None), False))),
        "leading": _as_float(_call_idx(layer, "style_run_leading", idx, None), None),
        "stroke_flag": bool(_bool_or_default(_call_idx(layer, "style_run_stroke_flag", idx, None), _bool_or_default(_call(layer, "style_normal_stroke_flag", None), False))),
        "stroke_color": stroke,
        "stroke_width": float(_as_float(_call_idx(layer, "style_run_outline_width", idx, None), _as_float(_call(layer, "style_normal_outline_width", None), 0.0))),
        "character_direction": _call_idx(layer, "style_run_character_direction", idx, _call(layer, "style_normal_character_direction", None)),
    }


def _default_style(layer: Any) -> dict[str, Any]:
    font_ps = _safe_text(getattr(layer, "primary_font_name", None)) or "ArialMT"
    family, style_name, ps_bold, ps_italic = _resolve_font_face_from_postscript(font_ps)
    fill = _argb_to_qcolor(_call(layer, "style_normal_fill_color", None)) or QtGui.QColor("#ff000000")
    stroke = _argb_to_qcolor(_call(layer, "style_normal_stroke_color", None))
    return {
        "font_postscript": font_ps,
        "font_family": family,
        "font_style_name": style_name,
        "font_size": float(_as_float(_call(layer, "style_normal_font_size", None), 20.0)),
        "fill_color": fill,
        "bold": bool(_bool_or_default(_call(layer, "style_normal_faux_bold", None), False) or ps_bold or _font_implies_bold(font_ps)),
        "italic": bool(_bool_or_default(_call(layer, "style_normal_faux_italic", None), False) or ps_italic or _font_implies_italic(font_ps)),
        "underline": bool(_bool_or_default(_call(layer, "style_normal_underline", None), False)),
        "leading": _as_float(_call(layer, "style_normal_leading", None), None),
        "stroke_flag": bool(_bool_or_default(_call(layer, "style_normal_stroke_flag", None), False)),
        "stroke_color": stroke,
        "stroke_width": float(_as_float(_call(layer, "style_normal_outline_width", None), 0.0)),
        "character_direction": _call(layer, "style_normal_character_direction", None),
    }


def _read_paragraph_runs(layer: Any, text_u16_len: int) -> list[dict[str, Any]]:
    lengths_fn = getattr(layer, "paragraph_run_lengths", None)
    lengths = list(lengths_fn() or []) if callable(lengths_fn) else []
    runs: list[dict[str, Any]] = []
    cursor = 0

    for idx, length in enumerate(lengths):
        start = cursor
        cursor += max(0, int(length))
        end = min(cursor, text_u16_len)
        if end <= start:
            continue
        just = _call_idx(layer, "paragraph_run_justification", idx, _call(layer, "paragraph_normal_justification", None))
        runs.append({"start": start, "end": end, "alignment": _alignment_from_justification(just)})

    if not runs and text_u16_len > 0:
        just = _call(layer, "paragraph_normal_justification", None)
        runs.append({"start": 0, "end": text_u16_len, "alignment": _alignment_from_justification(just)})
    elif runs and runs[-1]["end"] < text_u16_len:
        runs[-1]["end"] = text_u16_len

    return runs


def _build_html_from_runs(text: str, style_runs: list[dict[str, Any]], paragraph_runs: list[dict[str, Any]]) -> str:
    doc = QtGui.QTextDocument()
    doc.setPlainText(text)
    max_pos = max(0, doc.characterCount() - 1)
    cursor = QtGui.QTextCursor(doc)

    for run in style_runs:
        start = max(0, min(int(run["start"]), max_pos))
        end = max(start, min(int(run["end"]), max_pos))
        if end <= start:
            continue
        cursor.setPosition(start)
        cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        fmt = QtGui.QTextCharFormat()
        font = QtGui.QFont(run.get("font_family") or "Arial")
        style_name = run.get("font_style_name")
        if style_name:
            try:
                font.setStyleName(str(style_name))
            except Exception:
                pass
        font.setPointSizeF(max(1.0, float(run.get("font_size", 20.0))))
        font.setBold(bool(run.get("bold")))
        font.setItalic(bool(run.get("italic")))
        font.setUnderline(bool(run.get("underline")))
        fmt.setFont(font)
        fill_color = run.get("fill_color")
        if isinstance(fill_color, QtGui.QColor) and fill_color.isValid():
            fmt.setForeground(fill_color)
        cursor.mergeCharFormat(fmt)

    for run in paragraph_runs:
        start = max(0, min(int(run["start"]), max_pos))
        end = max(start, min(int(run["end"]), max_pos))
        if end <= start:
            continue
        cursor.setPosition(start)
        cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        block_fmt = QtGui.QTextBlockFormat()
        block_fmt.setAlignment(run["alignment"])
        cursor.mergeBlockFormat(block_fmt)

    return doc.toHtml()


def _outline_infos(style_runs: list[dict[str, Any]], text_u16_len: int, doc_end: int) -> list[OutlineInfo]:
    spans: list[tuple[int, int, QtGui.QColor, float]] = []
    for run in style_runs:
        if not run.get("stroke_flag"):
            continue
        color = run.get("stroke_color")
        if not isinstance(color, QtGui.QColor) or not color.isValid():
            continue
        width = float(run.get("stroke_width", 0.0))
        if width <= 0.0:
            continue
        start = int(run["start"])
        end = int(run["end"])
        if end > start:
            spans.append((start, end, QtGui.QColor(color), width))

    merged: list[tuple[int, int, QtGui.QColor, float]] = []
    for span in spans:
        if not merged:
            merged.append(span)
            continue
        ps, pe, pc, pw = merged[-1]
        cs, ce, cc, cw = span
        if cs <= pe and abs(pw - cw) < 1e-6 and pc.name(QtGui.QColor.HexArgb) == cc.name(QtGui.QColor.HexArgb):
            merged[-1] = (ps, max(pe, ce), pc, pw)
        else:
            merged.append(span)

    if _has_full_stroke_coverage(style_runs, text_u16_len) and merged:
        _, _, color, width = merged[0]
        return [
            OutlineInfo(
                start=0,
                end=max(0, doc_end),
                color=QtGui.QColor(color),
                width=float(width),
                type=OutlineType.Full_Document,
            )
        ]

    outlines: list[OutlineInfo] = []
    for start, end, color, width in merged:
        start_c = max(0, int(start))
        end_c = min(int(end), max(0, doc_end))
        if end_c <= start_c:
            continue
        outlines.append(
            OutlineInfo(
                start=start_c,
                end=end_c,
                color=QtGui.QColor(color),
                width=float(width),
                type=OutlineType.Selection,
            )
        )
    return outlines


def _find_full_outline(outlines: list[OutlineInfo], doc_end: int) -> OutlineInfo | None:
    for outline in outlines:
        if outline.start <= 0 and outline.end >= doc_end:
            return outline
    return None


def _has_full_stroke_coverage(style_runs: list[dict[str, Any]], text_u16_len: int) -> bool:
    if text_u16_len <= 0:
        return False
    cursor = 0
    for run in style_runs:
        start = int(run.get("start", 0))
        end = int(run.get("end", 0))
        if end <= start:
            continue
        if start > cursor:
            return False
        if not run.get("stroke_flag"):
            return False
        cursor = max(cursor, end)
        if cursor >= text_u16_len:
            return True
    return cursor >= text_u16_len


def _normalize_text(text: str) -> str:
    return text.replace("\u2028", "\n").replace("\u2029", "\n").replace("\r\n", "\n").replace("\r", "\n")


def _document_char_end(text: str) -> int:
    try:
        doc = QtGui.QTextDocument()
        doc.setPlainText(text)
        return max(0, int(doc.characterCount()) - 1)
    except Exception:
        return max(0, _u16_len(text))


def _position(layer: Any) -> tuple[float, float]:
    fn = getattr(layer, "position", None)
    if callable(fn):
        try:
            x, y = fn()
            return float(x), float(y)
        except Exception:
            pass
    return (
        _as_float(getattr(layer, "transform_tx", None), 0.0),
        _as_float(getattr(layer, "transform_ty", None), 0.0),
    )


def _box_size(layer: Any) -> tuple[float | None, float | None]:
    width = _as_float(_call(layer, "box_width", None), None)
    height = _as_float(_call(layer, "box_height", None), None)
    return width, height


def _document_margin() -> float:
    try:
        return float(QtGui.QTextDocument().documentMargin())
    except Exception:
        return 4.0


def _line_spacing(style: dict[str, Any]) -> float:
    leading = _as_float(style.get("leading"), None)
    if leading is None or leading <= 0.0:
        return 1.2
    try:
        font = QtGui.QFont(style.get("font_family") or "Arial")
        font.setPointSizeF(max(1.0, float(style.get("font_size", 20.0))))
        base = QtGui.QFontMetricsF(font).lineSpacing()
        if base <= 0.0:
            return 1.2
        return float(min(4.0, max(0.5, leading / base)))
    except Exception:
        return 1.2


def _is_vertical(layer: Any) -> bool:
    try:
        if bool(getattr(layer, "is_vertical", False)):
            return True
    except Exception:
        pass
    orientation = _call(layer, "orientation", None)
    enum_cls = getattr(getattr(psapi, "enum", None), "WritingDirection", None)
    return _enum_eq(orientation, enum_cls, "Vertical")


def _direction(layer: Any, run_dir: Any) -> QtCore.Qt.LayoutDirection:
    value = _call(layer, "style_normal_character_direction", run_dir)
    enum_cls = getattr(getattr(psapi, "enum", None), "CharacterDirection", None)
    if _enum_eq(value, enum_cls, "RightToLeft"):
        return QtCore.Qt.LayoutDirection.RightToLeft
    return QtCore.Qt.LayoutDirection.LeftToRight


def _alignment_from_justification(value: Any) -> QtCore.Qt.AlignmentFlag:
    enum_cls = getattr(getattr(psapi, "enum", None), "Justification", None)
    if _enum_eq(value, enum_cls, "Right") or _enum_eq(value, enum_cls, "JustifyLastRight"):
        return QtCore.Qt.AlignmentFlag.AlignRight
    if _enum_eq(value, enum_cls, "Center") or _enum_eq(value, enum_cls, "JustifyLastCenter"):
        return QtCore.Qt.AlignmentFlag.AlignHCenter
    if _enum_eq(value, enum_cls, "JustifyAll"):
        return QtCore.Qt.AlignmentFlag.AlignJustify
    return QtCore.Qt.AlignmentFlag.AlignLeft


def _enum_eq(value: Any, enum_cls: Any, member: str) -> bool:
    if value is None or enum_cls is None or not hasattr(enum_cls, member):
        return False
    target = getattr(enum_cls, member)
    try:
        return int(value) == int(target)
    except Exception:
        return value == target


def _font_name(layer: Any, index: Any) -> str | None:
    if index is None:
        return None
    fn = getattr(layer, "font_postscript_name", None)
    if callable(fn):
        try:
            return _safe_text(fn(int(index)))
        except Exception:
            return None
    return None


def _resolve_font_face_from_postscript(postscript_name: str) -> tuple[str, str | None, bool, bool]:
    if _can_build_font_catalog_in_current_thread():
        _ensure_font_catalog()
    key = (postscript_name or "").strip()
    if key and key in _ps_to_qt_font_cache:
        return _ps_to_qt_font_cache[key]
    family = _display_family(key)
    return family, None, _font_implies_bold(key), _font_implies_italic(key)


def _ensure_font_catalog() -> None:
    global _font_catalog_built
    if _font_catalog_built:
        return
    _font_catalog_built = True

    try:
        db = QtGui.QFontDatabase()
        for family in db.families():
            styles = db.styles(family) or [""]
            for style in styles:
                try:
                    font = db.font(family, style, 12)
                except Exception:
                    font = QtGui.QFont(family, 12)

                ps_name = _postscript_name_from_qfont(font)
                if not ps_name:
                    continue
                bold = False
                italic = False
                try:
                    bold = bool(db.bold(family, style))
                except Exception:
                    bold = bool(font.bold()) or ("bold" in style.lower())
                try:
                    italic = bool(db.italic(family, style))
                except Exception:
                    italic = bool(font.italic()) or ("italic" in style.lower() or "oblique" in style.lower())
                style_name = style.strip() or None
                _ps_to_qt_font_cache.setdefault(ps_name, (family, style_name, bold, italic))
    except Exception:
        pass


def _can_build_font_catalog_in_current_thread() -> bool:
    try:
        app = QtCore.QCoreApplication.instance()
        if app is None:
            return False
        return QtCore.QThread.currentThread() == app.thread()
    except Exception:
        return False


def _postscript_name_from_qfont(font: QtGui.QFont) -> str | None:
    try:
        raw = QtGui.QRawFont.fromFont(font)
        table = raw.fontTable("name")
        if not table:
            return None
        return _parse_postscript_name(bytes(table))
    except Exception:
        return None


def _parse_postscript_name(table: bytes) -> str | None:
    if len(table) < 6:
        return None
    try:
        _format, count, string_offset = struct.unpack_from(">HHH", table, 0)
    except Exception:
        return None

    for i in range(int(count)):
        offset = 6 + i * 12
        if offset + 12 > len(table):
            break
        try:
            platform_id, _encoding_id, _lang_id, name_id, length, str_offset = struct.unpack_from(">HHHHHH", table, offset)
        except Exception:
            continue
        if int(name_id) != 6:
            continue
        start = int(string_offset) + int(str_offset)
        end = start + int(length)
        if start < 0 or end > len(table):
            continue
        raw_name = table[start:end]
        try:
            if int(platform_id) in (0, 3):
                name = raw_name.decode("utf-16-be", errors="ignore").strip("\x00").strip()
            else:
                name = raw_name.decode("latin-1", errors="ignore").strip("\x00").strip()
        except Exception:
            name = ""
        if name:
            return name
    return None


def _display_family(postscript_name: str) -> str:
    ps_name = (postscript_name or "").strip()
    if not ps_name:
        return "Arial"
    base = ps_name[:-2] if ps_name.endswith("MT") and len(ps_name) > 2 else ps_name
    if "-" in base:
        base = base.split("-", 1)[0]
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base).strip()
    return spaced or ps_name


def _font_implies_bold(name: str) -> bool:
    lowered = (name or "").lower()
    return "bold" in lowered or "black" in lowered or "heavy" in lowered


def _font_implies_italic(name: str) -> bool:
    lowered = (name or "").lower()
    return "italic" in lowered or "oblique" in lowered


def _call(obj: Any, name: str, default: Any) -> Any:
    fn = getattr(obj, name, None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            return default
    return default


def _call_idx(obj: Any, name: str, idx: int, default: Any) -> Any:
    fn = getattr(obj, name, None)
    if callable(fn):
        try:
            return fn(idx)
        except Exception:
            return default
    return default


def _bool_or_default(value: Any, default: bool) -> bool:
    return default if value is None else bool(value)


def _argb_to_qcolor(values: Any) -> QtGui.QColor | None:
    if values is None:
        return None
    try:
        alpha, red, green, blue = [float(v) for v in list(values)]
    except Exception:
        return None
    color = QtGui.QColor()
    color.setRgbF(
        min(1.0, max(0.0, red)),
        min(1.0, max(0.0, green)),
        min(1.0, max(0.0, blue)),
        min(1.0, max(0.0, alpha)),
    )
    return color if color.isValid() else None


def _as_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    if callable(value):
        try:
            value = value()
        except Exception:
            return None
    text = str(value).strip()
    return text or None


def _unique_png_name(stem: str, used: set[str]) -> str:
    base = stem or "imported_page"
    candidate = f"{base}.png"
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}.png"
        suffix += 1
    used.add(candidate)
    return candidate


def _safe_stem(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", stem)
    cleaned = cleaned.strip().strip(".")
    return cleaned or "imported_page"
