from __future__ import annotations

import logging
import os
import re
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

import imkit as imk
import numpy as np
import photoshopapi as psapi
from PySide6 import QtCore, QtGui

from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.path_materialization import ensure_path_materialized


def _u16_len(text: str) -> int:
	"""Return the length of the string in UTF-16 code units."""
	return len(text.encode("utf-16-le")) // 2


@dataclass
class PsdPageData:
	file_path: str
	rgb_image: np.ndarray
	viewer_state: dict[str, Any]
	patches: list[dict[str, Any]]


@dataclass
class TextStyleRun:
	start: int
	end: int
	font: str
	font_size: float
	fill_color: list[float]
	bold: bool
	italic: bool
	underline: bool


@dataclass
class ParagraphStyleRun:
	start: int
	end: int
	alignment: Any


@dataclass
class OutlineStyleSpan:
	start: int
	end: int
	color: Any
	width: float


def export_psd_pages(
	output_folder: str,
	pages: list[PsdPageData],
	bundle_name: str,
	single_file_path: str | None = None,
	archive_path: str | None = None,
	archive_single_page: bool = False,
) -> str:
	if not pages:
		raise ValueError("No images available to export.")

	os.makedirs(output_folder, exist_ok=True)

	if len(pages) == 1 and not archive_single_page:
		page = pages[0]
		out_path = single_file_path or os.path.join(output_folder, f"{_safe_stem(page.file_path)}.psd")
		_write_page_psd(page, out_path)
		return out_path

	tmp_dir = tempfile.mkdtemp(prefix="comic_translate_psd_")
	try:
		for page in pages:
			out_path = os.path.join(tmp_dir, f"{_safe_stem(page.file_path)}.psd")
			_write_page_psd(page, out_path)

		final_archive_path = archive_path or os.path.join(
			output_folder,
			f"{_safe_name(bundle_name) or 'comic_translate_export'}.zip",
		)
		os.makedirs(os.path.dirname(final_archive_path) or output_folder, exist_ok=True)
		with zipfile.ZipFile(final_archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
			for file_name in sorted(os.listdir(tmp_dir)):
				file_path = os.path.join(tmp_dir, file_name)
				if os.path.isfile(file_path):
					zf.write(file_path, arcname=file_name)
		return final_archive_path
	finally:
		shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_page_psd(page: PsdPageData, out_path: str) -> None:
	image = _ensure_rgb_uint8(page.rgb_image)
	height, width, _ = image.shape
	doc = psapi.LayeredFile_8bit(psapi.enum.ColorMode.rgb, width, height)
	doc.dpi = 300.0

	# PhotoshopAPI add_layer() puts first-added at top of the stack.
	# Desired visual order (top→bottom): Editable Text → Inpaint Patches → Raw Image

	# Editable Text group (topmost)
	text_items = page.viewer_state.get("text_items_state", []) or []
	text_group = psapi.GroupLayer_8bit("Editable Text")
	doc.add_layer(text_group)
	for idx, text_state in enumerate(text_items, start=1):
		try:
			text_layer = _build_text_layer(text_state, idx)
		except Exception:
			logger.exception("Failed to build text layer %d", idx)
			text_layer = None
		if text_layer is not None:
			text_group.add_layer(doc, text_layer)
		else:
			logger.warning("Text layer %d returned None", idx)

	# Inpaint Patches group (middle)
	patch_group = psapi.GroupLayer_8bit("Inpaint Patches")
	doc.add_layer(patch_group)
	for idx, patch in enumerate(page.patches, start=1):
		try:
			patch_layer = _build_patch_layer(patch, idx)
		except Exception:
			logger.exception("Failed to build patch layer %d", idx)
			patch_layer = None
		if patch_layer is not None:
			patch_group.add_layer(doc, patch_layer)
		else:
			logger.warning("Patch %d returned None", idx)

	# Raw Image (bottom)
	base_layer = psapi.ImageLayer_8bit(
		_to_psapi_image_data(image),
		"Raw Image",
		width=width,
		height=height,
		pos_x=width / 2,
		pos_y=height / 2,
	)
	doc.add_layer(base_layer)

	# Force Photoshop to re-render all text layers on open
	invalidate = getattr(doc, "invalidate_text_cache", None)
	if callable(invalidate):
		invalidate()

	doc.write(out_path, force_overwrite=True)


def _build_patch_layer(patch: dict[str, Any], index: int) -> Any | None:
	bbox = patch.get("bbox")
	if not bbox or len(bbox) != 4:
		return None
	x, y, w, h = [int(round(v)) for v in bbox]
	if w <= 0 or h <= 0:
		return None

	if "png_path" in patch and patch["png_path"]:
		png_path = patch["png_path"]
		ensure_path_materialized(png_path)
		if not os.path.isfile(png_path):
			logger.warning("Patch %d: png_path does not exist: %s", index, png_path)
			return None
		patch_img = imk.read_image(png_path)
	else:
		patch_img = patch.get("image")
	if patch_img is None:
		logger.warning("Patch %d: no image data available", index)
		return None

	patch_img = _ensure_rgb_uint8(patch_img)
	ph, pw, _ = patch_img.shape
	# PhotoshopAPI positions layers by center, so offset by half dimensions
	return psapi.ImageLayer_8bit(
		_to_psapi_image_data(patch_img),
		f"Patch {index}",
		width=pw,
		height=ph,
		pos_x=x + pw / 2,
		pos_y=y + ph / 2,
	)


def _build_text_layer(state: dict[str, Any], index: int) -> Any | None:
	props = TextItemProperties.from_dict(state)
	plain_text, style_runs, paragraph_runs, doc_margin = _extract_text_runs(props)
	if not plain_text:
		logger.warning("Text %d: empty plain_text, skipping", index)
		return None

	pos_x, pos_y = props.position
	box_width = float(props.width) if props.width else 0.0
	box_height = float(props.height) if props.height else 0.0
	base_font, default_faux_bold, default_faux_italic = _resolve_postscript_font_and_faux(
		props.font_family or "Arial",
		bool(props.bold),
		bool(props.italic),
	)

	# Qt's QTextDocument applies a documentMargin that pads text inward from the
	# bounding rect. Photoshop has no such padding, so we shift the origin by that
	# margin and shrink the box accordingly so text placement matches the app canvas.
	pos_x = float(pos_x) + doc_margin
	pos_y = float(pos_y) + doc_margin
	if box_width > 0:
		box_width = max(0.0, box_width - 2.0 * doc_margin)
	if box_height > 0:
		box_height = max(0.0, box_height - 2.0 * doc_margin)

	# TextLayer position_x/position_y use top-left coordinates (no center offset)
	layer = psapi.TextLayer_8bit(
		layer_name=f"Text {index}",
		text=plain_text,
		font=base_font,
		font_size=float(props.font_size),
		fill_color=_to_argb_floats(props.text_color),
		position_x=pos_x,
		position_y=pos_y,
		box_width=box_width,
		box_height=box_height,
	)
	# Prefer non-soft anti-aliasing so text doesn't look washed out in PSD.
	_set_text_antialias(layer)

	# PhotoshopAPI always appends a trailing '\r' to the EngineData text payload.
	text_u16_length = _u16_len(plain_text)
	text_cxx_length = text_u16_length + 1

	outline_spans = _extract_outline_spans(props, text_cxx_length)
	_apply_default_text_style(layer, props, None, default_faux_bold, default_faux_italic)

	applied_ranges = _apply_style_runs(layer, style_runs, outline_spans, props)
	if not applied_ranges:
		fallback_outline = _find_full_document_outline(outline_spans, text_cxx_length)
		if fallback_outline is not None:
			_apply_default_text_style(layer, props, fallback_outline, default_faux_bold, default_faux_italic)

	_apply_paragraph_styles(layer, paragraph_runs, props)
	# Apply text direction after style/paragraph edits.
	_apply_text_direction(layer, props)
	_apply_text_rotation(layer, props)

	return layer


def _extract_text_runs(props: TextItemProperties) -> tuple[str, list[TextStyleRun], list[ParagraphStyleRun], float]:
	html_value = props.text or ""
	default_color = _to_argb_floats(props.text_color)
	default_size = float(props.font_size)
	default_font, default_faux_bold, default_faux_italic = _resolve_postscript_font_and_faux(
		props.font_family or "Arial",
		bool(props.bold),
		bool(props.italic),
	)

	if not html_value:
		return "", [], [], 4.0

	doc = QtGui.QTextDocument()
	doc.setHtml(html_value)
	doc_margin = doc.documentMargin()

	plain_text = doc.toPlainText().replace("\u2028", "\n").replace("\u2029", "\n").replace("\r\n", "\n").replace("\r", "\n")
	if not plain_text:
		return "", [], [], doc_margin

	text_u16_length = _u16_len(plain_text)
	# PhotoshopAPI appends a trailing \r.
	text_cxx_length = text_u16_length + 1

	runs: list[TextStyleRun] = []
	paragraph_runs: list[ParagraphStyleRun] = []
	char_index = 0
	block = doc.begin()

	while block.isValid():
		block_start = char_index
		iterator = block.begin()
		while not iterator.atEnd():
			fragment = iterator.fragment()
			if fragment.isValid():
				frag_text = fragment.text() or ""
				if frag_text:
					char_fmt = fragment.charFormat()
					start = char_index
					end = char_index + _u16_len(frag_text)
					is_bold = char_fmt.fontWeight() >= int(QtGui.QFont.Weight.DemiBold)
					is_italic = bool(char_fmt.fontItalic())
					raw_font = char_fmt.font().family() if char_fmt.font().family() else ""
					font_name, faux_bold, faux_italic = _resolve_postscript_font_and_faux(
						raw_font or (props.font_family or "Arial"),
						is_bold,
						is_italic,
					)
					runs.append(
						TextStyleRun(
							start=start,
							end=end,
							font=font_name,
							font_size=float(char_fmt.fontPointSize() or default_size),
							fill_color=_char_format_color_or_default(char_fmt, default_color),
							bold=faux_bold,
							italic=faux_italic,
							underline=bool(char_fmt.fontUnderline()),
						)
					)
					char_index = end
			iterator += 1

		if block.next().isValid():
			char_index += _u16_len("\n")

		# Extend the paragraph run to encompass the newline (or the implicit trailing \r for the last block)
		block_end = char_index if block.next().isValid() else char_index + 1

		if block_end > block_start:
			paragraph_runs.append(
				ParagraphStyleRun(
					start=block_start,
					end=block_end,
					alignment=block.blockFormat().alignment(),
				)
			)

		block = block.next()

	normalized = _coalesce_runs(
		runs,
		text_cxx_length,
		default_size,
		default_color,
		default_font,
		default_faux_bold,
		default_faux_italic,
		bool(props.underline),
	)
	return plain_text, normalized, paragraph_runs, doc_margin


def _char_format_color_or_default(char_fmt: QtGui.QTextCharFormat, default_color: list[float]) -> list[float]:
	try:
		brush = char_fmt.foreground()
		color = brush.color() if brush.style() != QtCore.Qt.BrushStyle.NoBrush else QtGui.QColor()
		if color.isValid():
			return _to_argb_floats(color)
	except Exception:
		pass
	return default_color


def _coalesce_runs(
	runs: list[TextStyleRun],
	text_len: int,
	default_size: float,
	default_color: list[float],
	default_font: str,
	default_bold: bool,
	default_italic: bool,
	default_underline: bool,
) -> list[TextStyleRun]:
	if text_len <= 0:
		return []

	if not runs:
		return [
			TextStyleRun(
				start=0,
				end=text_len,
				font=default_font,
				font_size=default_size,
				fill_color=default_color,
				bold=default_bold,
				italic=default_italic,
				underline=default_underline,
			)
		]

	merged: list[TextStyleRun] = []
	for run in runs:
		if run.end <= run.start:
			continue
		if run.start >= text_len:
			continue
		if run.end > text_len:
			run = TextStyleRun(
				start=run.start,
				end=text_len,
				font=run.font,
				font_size=run.font_size,
				fill_color=run.fill_color,
				bold=run.bold,
				italic=run.italic,
				underline=run.underline,
			)

		if not merged:
			if run.start > 0:
				merged.append(
					TextStyleRun(
						start=0,
						end=run.start,
						font=default_font,
						font_size=default_size,
						fill_color=default_color,
						bold=default_bold,
						italic=default_italic,
						underline=default_underline,
					)
				)
			merged.append(run)
			continue

		prev = merged[-1]
		if run.start > prev.end:
			# Gap detected (e.g. newline or missing block).
			# Do NOT inject default_font! If we inject default font, newlines
			# get a completely different size/color, completely destroying the bounding box
			# line heights in Photoshop.
			# Instead, just extend the previous block to cover the gap.
			prev.end = run.start

		if _same_style(prev, run) and run.start <= prev.end:
			merged[-1] = TextStyleRun(
				start=prev.start,
				end=max(prev.end, run.end),
				font=prev.font,
				font_size=prev.font_size,
				fill_color=prev.fill_color,
				bold=prev.bold,
				italic=prev.italic,
				underline=prev.underline,
			)
		else:
			merged.append(run)

	last = merged[-1]
	if last.end < text_len:
		last.end = text_len

	return merged


def _same_style(a: TextStyleRun, b: TextStyleRun) -> bool:
	return (
		a.font == b.font
		and
		a.bold == b.bold
		and a.italic == b.italic
		and a.underline == b.underline
		and abs(a.font_size - b.font_size) < 1e-6
		and all(abs(x - y) < 1e-6 for x, y in zip(a.fill_color, b.fill_color))
	)


def _apply_style_runs(
	layer: Any,
	runs: list[TextStyleRun],
	outline_spans: list[OutlineStyleSpan],
	props: TextItemProperties,
) -> bool:
	if not runs:
		return False
	style_range = getattr(layer, "style_range", None)
	if not callable(style_range):
		return False

	for run in runs:
		segments = _split_run_by_outline(run, outline_spans)
		for segment, segment_outline in segments:
			try:
				editor = style_range(int(segment.start), int(segment.end))
			except Exception:
				continue
			_apply_editor_style(editor, segment, segment_outline, props)
	return True


def _split_run_by_outline(
	run: TextStyleRun,
	outline_spans: list[OutlineStyleSpan],
) -> list[tuple[TextStyleRun, OutlineStyleSpan | None]]:
	if run.end <= run.start:
		return []

	if not outline_spans:
		return [(run, None)]

	boundaries = {int(run.start), int(run.end)}
	for outline in outline_spans:
		if outline.end <= run.start or outline.start >= run.end:
			continue
		boundaries.add(max(int(run.start), int(outline.start)))
		boundaries.add(min(int(run.end), int(outline.end)))

	points = sorted(boundaries)
	segments: list[tuple[TextStyleRun, OutlineStyleSpan | None]] = []
	for idx in range(len(points) - 1):
		start = int(points[idx])
		end = int(points[idx + 1])
		if end <= start:
			continue
		segment = TextStyleRun(
			start=start,
			end=end,
			font=run.font,
			font_size=run.font_size,
			fill_color=run.fill_color,
			bold=run.bold,
			italic=run.italic,
			underline=run.underline,
		)
		segments.append((segment, _outline_for_index(start, outline_spans)))
	return segments


def _outline_for_index(index: int, outline_spans: list[OutlineStyleSpan]) -> OutlineStyleSpan | None:
	active: OutlineStyleSpan | None = None
	for span in outline_spans:
		if span.start <= index < span.end:
			active = span
	return active


def _extract_outline_spans(props: TextItemProperties, text_len: int) -> list[OutlineStyleSpan]:
	if text_len <= 0:
		return []

	outlines = getattr(props, "selection_outlines", None) or []
	spans: list[OutlineStyleSpan] = []
	for raw_outline in outlines:
		span = _parse_outline_span(raw_outline, text_len)
		if span is not None:
			spans.append(span)

	return spans


def _parse_outline_span(raw_outline: Any, text_len: int) -> OutlineStyleSpan | None:
	if raw_outline is None:
		return None

	outline_data = raw_outline
	if isinstance(outline_data, dict) and outline_data.get("type") == "selection_outline_info":
		outline_data = outline_data.get("data", {})

	start = _outline_field(outline_data, "start", 0)
	end = _outline_field(outline_data, "end", 0)
	width = _outline_field(outline_data, "width", 0.0)
	color = _outline_field(outline_data, "color", None)

	try:
		start_i = max(0, int(start))
		end_i = min(int(end), int(text_len))
		width_f = float(width)
	except Exception:
		return None

	if end_i <= start_i or width_f <= 0:
		return None

	qcolor = _coerce_qcolor(color)
	if qcolor is None:
		return None

	return OutlineStyleSpan(
		start=start_i,
		end=end_i,
		color=qcolor,
		width=width_f,
	)


def _outline_field(outline_data: Any, name: str, default: Any) -> Any:
	if isinstance(outline_data, dict):
		return outline_data.get(name, default)
	return getattr(outline_data, name, default)


def _coerce_qcolor(value: Any) -> QtGui.QColor | None:
	if value is None:
		return None
	if isinstance(value, dict) and value.get("type") == "qcolor":
		value = value.get("data")
	qcolor = value if isinstance(value, QtGui.QColor) else QtGui.QColor(value)
	return qcolor if qcolor.isValid() else None


def _find_full_document_outline(outline_spans: list[OutlineStyleSpan], text_len: int) -> OutlineStyleSpan | None:
	if text_len <= 0:
		return None
	full_doc_span: OutlineStyleSpan | None = None
	for span in outline_spans:
		if span.start <= 0 and span.end >= text_len:
			full_doc_span = span
	return full_doc_span


def _apply_default_text_style(
	layer: Any,
	props: TextItemProperties,
	outline_span: OutlineStyleSpan | None,
	default_faux_bold: bool,
	default_faux_italic: bool,
) -> None:
	style_all = getattr(layer, "style_all", None)
	if not callable(style_all):
		return
	try:
		editor = style_all()
	except Exception:
		return

	default_font, _, _ = _resolve_postscript_font_and_faux(
		props.font_family or "Arial",
		bool(props.bold),
		bool(props.italic),
	)
	default_run = TextStyleRun(
		start=0,
		end=0,
		font=default_font,
		font_size=float(props.font_size),
		fill_color=_to_argb_floats(props.text_color),
		bold=default_faux_bold,
		italic=default_faux_italic,
		underline=bool(props.underline),
	)
	_apply_editor_style(editor, default_run, outline_span, props)


def _apply_editor_style(
	editor: Any,
	run: TextStyleRun,
	outline_span: OutlineStyleSpan | None,
	props: TextItemProperties,
) -> None:
	_set_if_exists(editor, "set_font", str(run.font or ""))
	_set_if_exists(editor, "set_font_size", float(run.font_size))
	_set_if_exists(editor, "set_fill_color", list(run.fill_color))
	_set_if_exists(editor, "set_bold", bool(run.bold))
	_set_if_exists(editor, "set_italic", bool(run.italic))
	_set_if_exists(editor, "set_underline", bool(run.underline))

	font = QtGui.QFont(run.font or "Arial")
	font.setPointSizeF(max(1.0, float(run.font_size)))
	if run.bold:
		font.setBold(True)
	if run.italic:
		font.setItalic(True)

	fm = QtGui.QFontMetricsF(font)
	base_line_height = fm.lineSpacing()

	_set_if_exists(editor, "set_auto_leading", False)
	_set_if_exists(editor, "set_leading", base_line_height)

	has_outline = outline_span is not None
	_set_if_exists(editor, "set_stroke_flag", has_outline)
	if has_outline:
		_set_if_exists(editor, "set_stroke_color", _to_argb_floats(outline_span.color))
		_set_if_exists(editor, "set_outline_width", float(outline_span.width))


def _apply_paragraph_justification(layer: Any, justification: Any) -> None:
	paragraph_all = getattr(layer, "paragraph_all", None)
	if callable(paragraph_all):
		try:
			editor = paragraph_all()
			_set_if_exists(editor, "set_justification", justification)
			return
		except Exception:
			pass

	set_paragraph_normal_justification = getattr(layer, "set_paragraph_normal_justification", None)
	if callable(set_paragraph_normal_justification):
		try:
			set_paragraph_normal_justification(justification)
		except Exception:
			pass


def _apply_paragraph_styles(
	layer: Any,
	paragraph_runs: list[ParagraphStyleRun],
	props: TextItemProperties,
) -> None:
	if not paragraph_runs:
		justification = _map_justification(props.alignment)
		if justification is not None:
			_apply_paragraph_justification(layer, justification)
		return

	paragraph_range = getattr(layer, "paragraph_range", None)
	if callable(paragraph_range):
		for run in paragraph_runs:
			if run.end <= run.start:
				continue
			justification = _map_justification(run.alignment)
			if justification is None:
				continue
			try:
				editor = paragraph_range(int(run.start), int(run.end))
			except Exception:
				continue
			_set_if_exists(editor, "set_justification", justification)
		return

	justification = _map_justification(props.alignment)
	if justification is not None:
		_apply_paragraph_justification(layer, justification)


def _set_text_antialias(layer: Any) -> None:
	anti_alias_enum = getattr(getattr(psapi, "enum", None), "AntiAliasMethod", None)
	if anti_alias_enum is None:
		return
	for name in ("Sharp", "Strong", "Crisp", "Smooth"):
		anti_alias_value = getattr(anti_alias_enum, name, None)
		if anti_alias_value is not None:
			_set_if_exists(layer, "set_anti_alias", anti_alias_value)
			return


def _set_if_exists(obj: Any, method_name: str, *args: Any) -> bool:
	method = getattr(obj, method_name, None)
	if callable(method):
		try:
			method(*args)
			return True
		except Exception:
			pass
	return False


def _apply_text_direction(layer: Any, props: TextItemProperties) -> None:
	# Vertical vs horizontal writing direction
	target_vertical = bool(props.vertical)
	writing_direction_enum = getattr(psapi.enum, "WritingDirection", None)
	if writing_direction_enum is not None:
		wd_value = getattr(writing_direction_enum, "Vertical" if target_vertical else "Horizontal", None)
		if wd_value is not None:
			applied = _set_if_exists(layer, "set_orientation", wd_value)
			# Compatibility fallback for builds that accept raw integer enum values.
			if not applied and hasattr(wd_value, "value"):
				_set_if_exists(layer, "set_orientation", int(getattr(wd_value, "value")))

	# RTL / LTR character direction (not applicable for vertical writing)
	character_direction_enum = getattr(psapi.enum, "CharacterDirection", None)
	if character_direction_enum is not None and not target_vertical:
		# direction may be a Qt.LayoutDirection enum or a plain int (after JSON round-trip).
		direction = props.direction
		is_rtl = (
			direction == QtCore.Qt.LayoutDirection.RightToLeft
			or (isinstance(direction, int) and direction == QtCore.Qt.LayoutDirection.RightToLeft.value)
		)
		if is_rtl:
			dir_value = getattr(character_direction_enum, "RightToLeft", None)
		else:
			dir_value = getattr(character_direction_enum, "LeftToRight", None)
		if dir_value is not None:
			# Set on the normal/default style (DefaultRunData).
			_set_if_exists(layer, "set_style_normal_character_direction", dir_value)
			# Photoshop reads CharacterDirection from each RunArray entry, not from
			# DefaultRunData alone.  Apply it to every per-character run using
			# set_style_run_character_direction(), which is bound directly on the layer.
			set_srcd = getattr(layer, "set_style_run_character_direction", None)
			run_count = getattr(layer, "style_run_count", None)
			if callable(set_srcd) and run_count is not None:
				for i in range(run_count):
					try:
						set_srcd(i, dir_value)
					except Exception:
						pass


def _apply_text_rotation(layer: Any, props: TextItemProperties) -> None:
	rotation = _float_or_default(getattr(props, "rotation", 0.0), 0.0)
	if abs(rotation) < 1e-6:
		return

	if _set_if_exists(layer, "set_rotation_angle", rotation):
		return
	if _set_if_exists(layer, "set_rotation", rotation):
		return

	# Some bindings expose this as a writable property instead of a setter.
	try:
		setattr(layer, "rotation_angle", rotation)
		return
	except Exception:
		pass

	logger.debug("Text layer rotation %.3f was not applied: no compatible API found.", rotation)


def _float_or_default(value: Any, default: float) -> float:
	try:
		return float(value)
	except Exception:
		return default


def _map_justification(alignment: Any) -> Any | None:
	try:
		alignment_value = int(alignment)
	except Exception:
		alignment_value = int(QtCore.Qt.AlignmentFlag.AlignLeft)

	if alignment_value & int(QtCore.Qt.AlignmentFlag.AlignHCenter):
		name_candidates = ["Center", "center", "CENTER"]
	elif alignment_value & int(QtCore.Qt.AlignmentFlag.AlignRight):
		name_candidates = ["Right", "right", "RIGHT"]
	else:
		name_candidates = ["Left", "left", "LEFT"]

	enum_obj = getattr(psapi.enum, "Justification", None)
	if enum_obj is None:
		return None

	for name in name_candidates:
		if hasattr(enum_obj, name):
			return getattr(enum_obj, name)
	return None


def _to_psapi_image_data(rgb_image: np.ndarray) -> np.ndarray:
	"""Convert HWC uint8 image to CHW with opaque alpha for Photoshop layer compositing."""
	img = np.asarray(rgb_image)
	if img.ndim != 3:
		raise ValueError("Expected an image array with shape (H, W, C)")
	if img.shape[2] == 3:
		# Add fully opaque alpha channel so Photoshop composites layers correctly
		alpha = np.full((img.shape[0], img.shape[1], 1), 255, dtype=np.uint8)
		img = np.concatenate([img, alpha], axis=2)
	# Now shape is (H, W, 4) -> transpose to (4, H, W)
	return np.ascontiguousarray(np.transpose(img, (2, 0, 1)))


# Cache for PostScript font name lookups
_ps_name_cache: dict[tuple[str, bool, bool], str] = {}


def _resolve_postscript_font_and_faux(
	family: str,
	bold: bool = False,
	italic: bool = False,
) -> tuple[str, bool, bool]:
	"""Return best PostScript font face plus faux style flags when no matching face exists."""
	base_family = family or "Arial"
	font_name = _to_postscript_name(base_family, bold, italic)

	# Faux styles should only be used when switching this axis does not change the resolved face.
	has_real_bold_face = _to_postscript_name(base_family, True, italic) != _to_postscript_name(base_family, False, italic)
	has_real_italic_face = _to_postscript_name(base_family, bold, True) != _to_postscript_name(base_family, bold, False)

	return (
		font_name,
		bool(bold and not has_real_bold_face),
		bool(italic and not has_real_italic_face),
	)


def _to_postscript_name(family: str, bold: bool = False, italic: bool = False) -> str:
	"""Resolve the PostScript name of an installed font using Qt's QRawFont.

	Photoshop requires PostScript font names (e.g. 'ArialMT' not 'Arial').
	This reads nameID 6 from the font's OpenType name table, so it works
	for any font installed on the system.
	"""
	if not family:
		return "ArialMT"
	# If it already looks like a PostScript name, keep it
	if "-" in family or family.endswith("MT"):
		return family

	key = (family, bold, italic)
	if key in _ps_name_cache:
		return _ps_name_cache[key]

	ps_name = _read_postscript_name_from_font(family, bold, italic)
	_ps_name_cache[key] = ps_name
	return ps_name


def _read_postscript_name_from_font(family: str, bold: bool, italic: bool) -> str:
	"""Read PostScript name (nameID 6) from the font's OpenType name table via QRawFont."""

	font = QtGui.QFont(family)
	if bold:
		font.setBold(True)
	if italic:
		font.setItalic(True)

	try:
		raw_font = QtGui.QRawFont.fromFont(font)
		name_table = raw_font.fontTable("name")
		if not name_table or len(name_table) < 6:
			return _postscript_name_fallback(family, bold, italic)

		data = bytes(name_table)
		_format, count, string_offset = struct.unpack_from(">HHH", data, 0)

		for i in range(count):
			offset = 6 + i * 12
			if offset + 12 > len(data):
				break
			platform_id, encoding_id, _lang_id, name_id, length, str_offset = (
				struct.unpack_from(">HHHHHH", data, offset)
			)
			if name_id != 6:  # 6 = PostScript name
				continue

			str_start = string_offset + str_offset
			if str_start + length > len(data):
				continue

			raw = data[str_start : str_start + length]
			# Platform 3 (Windows) / 1 (Mac Unicode) use UTF-16BE
			if platform_id in (0, 3):
				ps_name = raw.decode("utf-16-be", errors="replace").strip("\x00")
			else:
				# Platform 1 (Macintosh) uses latin-1
				ps_name = raw.decode("latin-1", errors="replace").strip("\x00")

			if ps_name:
				return ps_name
	except Exception:
		pass

	return _postscript_name_fallback(family, bold, italic)


def _postscript_name_fallback(family: str, bold: bool, italic: bool) -> str:
	"""Fallback: remove spaces and append style suffix."""
	ps_name = family.replace(" ", "")
	if bold and italic:
		ps_name += "-BoldItalic"
	elif bold:
		ps_name += "-Bold"
	elif italic:
		ps_name += "-Italic"
	return ps_name


def _ensure_rgb_uint8(image: np.ndarray) -> np.ndarray:
	img = np.asarray(image)
	if img.dtype != np.uint8:
		img = np.clip(img, 0, 255).astype(np.uint8)
	if img.ndim != 3:
		raise ValueError("Expected an RGB image array with shape (H, W, C)")
	if img.shape[2] == 4:
		img = img[:, :, :3]
	if img.shape[2] != 3:
		raise ValueError("Expected an RGB image array with 3 channels")
	return img


def _to_argb_floats(color: Any | None) -> list[float]:
	if color is None:
		return [1.0, 0.0, 0.0, 0.0]
	if isinstance(color, QtGui.QColor):
		qcolor = color
	else:
		qcolor = QtGui.QColor(color)
	return [
		qcolor.alphaF(),
		qcolor.redF(),
		qcolor.greenF(),
		qcolor.blueF(),
	]


def _safe_stem(path: str) -> str:
	stem = os.path.splitext(os.path.basename(path))[0]
	return _safe_name(stem)


def _safe_name(name: str) -> str:
	cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name or "")
	cleaned = cleaned.strip().strip(".")
	return cleaned or "untitled"
