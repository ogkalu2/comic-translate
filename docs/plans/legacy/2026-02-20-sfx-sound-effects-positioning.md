# SFX Sound Effects — Preserve Original Position

**Date:** 2026-02-20
**Branch:** feature/sfx-positioning (proposed)
**Status:** Plan

---

## Problem

Comic sound effects (SFX) like "BOOM", "POW", "ドカン" are free-floating text drawn directly on the artwork — not inside speech bubbles. The current pipeline:

1. Detects them as `text_free` blocks
2. Inpaints (erases) the original SFX from the image
3. Renders the translated SFX in the inpainted region

This loses the original artistic positioning and styling. The translated SFX should be rendered **at or near the original position**, ideally overlaid on the artwork without erasing it (or with minimal inpainting).

---

## Goals

- Identify SFX blocks reliably during the pipeline
- Skip or minimise inpainting for SFX (preserve the art)
- Render translated SFX overlaid at the original position
- Allow per-block user override (keep/skip inpaint, reposition)

---

## Approach

### 1. SFX Classification on `TextBlock`

Add an `is_sfx: bool` field to `TextBlock` (default `False`).

**File:** `modules/utils/textblock.py`

```python
self.is_sfx: bool = False
```

Also add to `deep_copy()`:
```python
new_block.is_sfx = self.is_sfx
```

### 2. SFX Detection — Two Signals

#### Signal A: Geometric (fast, no LLM)

A `text_free` block is a strong SFX candidate when:
- `text_class == 'text_free'` (outside any bubble)
- Large font relative to block area (single word / short text)
- High angle variance or diagonal orientation (`abs(angle) > 10°`)
- Aspect ratio is wide or square (not a caption box)

Implement in `pipeline/segmentation_handler.py` or a new `pipeline/sfx_classifier.py`:

```python
def classify_sfx_blocks(blk_list: list[TextBlock]) -> None:
    for blk in blk_list:
        if blk.text_class != 'text_free':
            continue
        word_count = len(blk.text.split()) if blk.text else 0
        if word_count <= 3 and abs(blk.angle) > 5:
            blk.is_sfx = True
```

#### Signal B: Glossary (batch mode, post-OCR)

The existing `DiscoveryPass` already asks the LLM to identify SFX terms. After the discovery pass populates `ComicGlossary`, mark any block whose OCR text matches a glossary SFX entry:

```python
# In pipeline/ocr_handler.py, after OCR + noise filter
for blk in blk_list:
    if comic_session and comic_session.glossary.is_sfx_term(blk.text):
        blk.is_sfx = True
```

Add `is_sfx_term(text)` to `ComicGlossary`:
```python
def is_sfx_term(self, text: str) -> bool:
    for entry in self._entries.values():
        if entry.category == GlossaryCategory.SFX and entry.source.lower() in text.lower():
            return True
    return False
```

### 3. Inpainting — Skip for SFX

**File:** `modules/utils/image_utils.py` — `generate_mask()`

```python
for blk in blk_list:
    if getattr(blk, 'is_sfx', False):
        continue  # Don't erase original SFX art
    # ... existing mask generation
```

This preserves the original artwork under the SFX.

### 4. Rendering — Overlay at Original Position

**File:** `modules/rendering/render.py` — `render_text_blocks()`

For SFX blocks, render the translated text **directly over** the (non-inpainted) original position using:
- Same bounding box (`blk.xyxy`) as the original
- Outline/stroke on the text to ensure readability over artwork
- Font color matched to original (`blk.font_color`) or white+black outline
- Angle preserved (`blk.angle`)

```python
if getattr(blk, 'is_sfx', False):
    # Use original image (not inpainted) as base for this block
    # Render with outline for legibility
    render_sfx_overlay(img, blk, settings)
else:
    # Existing render path
    render_text_block(inpainted_img, blk, settings)
```

`render_sfx_overlay` draws text at `blk.xyxy` with a stroke outline, rotated by `blk.angle`, on the original image layer.

### 5. UI — Per-block SFX Toggle

**File:** `app/ui/canvas/text_item.py` and `app/controllers/text.py`

Add a right-click context menu option on text blocks:
- "Mark as SFX (preserve position)" — sets `blk.is_sfx = True`, skips inpaint
- "Treat as dialogue" — sets `blk.is_sfx = False`, normal inpaint+render

This lets users correct misclassifications.

### 6. Project Serialisation

**File:** `app/projects/project_state.py` and `app/projects/parsers.py`

Add `is_sfx` to the serialised TextBlock fields so it survives save/load.

---

## Data Flow (Updated)

```
Detection
  └─ text_free blocks → SFX geometric classifier → blk.is_sfx = True (candidates)

OCR
  └─ After OCR: glossary SFX match → blk.is_sfx = True (confirmed)

Inpainting
  └─ is_sfx=True → skip mask generation (art preserved)
  └─ is_sfx=False → normal inpaint

Translation
  └─ All blocks translated (no change)

Rendering
  └─ is_sfx=True → overlay on original image at blk.xyxy with outline
  └─ is_sfx=False → render on inpainted image (existing path)
```

---

## Files to Change

| File | Change |
|------|--------|
| `modules/utils/textblock.py` | Add `is_sfx` field + `deep_copy` |
| `pipeline/sfx_classifier.py` | New — geometric SFX classifier |
| `pipeline/comic_glossary.py` | Add `is_sfx_term()` method |
| `pipeline/ocr_handler.py` | Call glossary SFX match after OCR |
| `pipeline/segmentation_handler.py` | Call geometric classifier after segmentation |
| `modules/utils/image_utils.py` | Skip mask for `is_sfx` blocks |
| `modules/rendering/render.py` | Add `render_sfx_overlay()`, branch on `is_sfx` |
| `app/ui/canvas/text_item.py` | Right-click SFX toggle |
| `app/controllers/text.py` | Handle SFX toggle command |
| `app/projects/project_state.py` | Serialise `is_sfx` |
| `app/projects/parsers.py` | Encode/decode `is_sfx` |

---

## Out of Scope (Future)

- Automatic SFX font matching (matching the original hand-lettered style)
- SFX-specific translation prompt tuning (already partially handled by story context)
- Webtoon-mode SFX handling (separate virtual page considerations)
