# Manga Auto-Translation System — Detailed Technical Plan

---

## Overview

This document consolidates and refines the design discussions into a cohesive architecture for an automated manga/comic translation pipeline. The system covers six major subsystems:

1. OCR Error Handling
2. Translation Cache (v2 Data Structure)
3. Parallel API Translation with Free/Paid Fallback
4. Text Positioning & Collision Resolution
5. Bubble-Aware Text Expansion
6. **Cross-Page Consistency — Comic-Level Glossary & Story Context** ← new

---

## 1. OCR Error Handling

### Problem

OCR engines produce two categories of errors when scanning manga panels:

- **Phantom Characters (幻覺字元)** — Characters that do not exist in the image but are hallucinated by the OCR engine (e.g., `21,"0~(!!","川"`).
- **Misread Characters (辨識錯誤)** — Characters that exist in the image but are read incorrectly (e.g., `"lve"` instead of `"I've"`, `"%."` instead of `"?."`).

To avoid inconsistent terminology across the codebase and documentation, use a **single unified term**:

> **OCR Noise** — umbrella term covering both phantom characters and misread characters.

Sub-types:
- `ocr_noise.phantom` — hallucinated, not in image
- `ocr_noise.misread` — present in image but incorrectly decoded

### Detection Strategy

```
Raw OCR Output
     │
     ▼
┌─────────────────────────────────┐
│  Confidence Score Filter        │  → Reject tokens below threshold (e.g. < 0.4)
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  Symbol/Gibberish Pattern Check │  → Regex: non-printable, mixed symbol runs
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  Dictionary / Language Model    │  → Validate token against known vocabulary
│  Validation                     │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  Output: Clean Token List       │  → Only pass validated tokens downstream
└─────────────────────────────────┘
```

### Implementation Notes

- Store OCR confidence scores alongside each token in the extraction phase.
- Flag tokens with confidence < 0.5 as `suspect`; do not translate them until manually reviewed or reprocessed.
- Maintain a **noise log** per image for later audit.

---

## 2. Translation Cache — v2 Data Structure

### Problem

The old flat key-value cache (`"sees you~": "sees you~"`) had three critical flaws:

1. When the API failed, untranslated text was stored as if it were a valid translation (source == target), polluting the cache with non-translations.
2. No metadata — no quality signal, no timestamps, no model attribution.
3. No versioning — old and new cache formats co-exist, causing silent errors.

### v2 Schema (enforced)

```json
{
  "version": "2.0",
  "saved_at": 1738000000.0,
  "stats": {
    "total_entries": 0,
    "total_hits": 0,
    "total_misses": 0,
    "total_updates": 0,
    "failed_api_fallbacks": 0
  },
  "entries": {
    "<source_lang>:<target_lang>:<source_text>": {
      "source_text": "string",
      "translated_text": "string",
      "source_lang": "string",
      "target_lang": "string",
      "created_at": 0.0,
      "updated_at": 0.0,
      "model": "string",
      "confidence": 0.0,
      "usage_count": 0,
      "last_used": 0.0,
      "quality_score": 0.0,
      "verified": false,
      "translation_status": "success",
      "version": 1,
      "previous_translation": null
    }
  }
}
```

### Key Field: `translation_status`

This is the most important new field to prevent cache pollution:

| Value | Meaning |
|-------|---------|
| `"success"` | API returned a valid translation |
| `"api_failed"` | API call failed; entry should NOT be used as translation |
| `"untranslatable"` | Confirmed proper noun / no translation needed |
| `"pending_review"` | Low quality score, awaiting human review |

**Rule:** Only entries with `translation_status == "success"` or `"untranslatable"` may be served as translations. Entries with `"api_failed"` are stored for retry tracking only.

### Cache Lookup Flow

```
Request translation for text T
        │
        ▼
  Cache entry exists?
   ├── No  → Call API → Store result → Return
   └── Yes
        │
        ▼
  translation_status == "success"?
   ├── Yes → Return cached translated_text; increment usage_count
   └── No (api_failed / pending_review)
        │
        ▼
  Try API again
   ├── Success → Update entry (new translation, status=success, version++)
   └── Fail    → Return source_text as fallback (display original, not fake translation)
```

### Cache Eviction (using metadata)

Evict entries when cache exceeds size limit using this priority:

1. `translation_status == "api_failed"` (lowest value)
2. Lowest `quality_score`
3. Oldest `last_used`
4. Lowest `usage_count`

Never evict entries where `verified == true`.

### Version Migration

On startup, detect old v1 cache (flat key-value or no `version` field) and migrate automatically:

```python
def migrate_cache(old_cache: dict) -> dict:
    """Migrate flat KV cache to v2 schema."""
    new_entries = {}
    for key, value in old_cache.items():
        # Detect untranslated entries (source == target)
        status = "untranslatable" if key == value else "success"
        new_entries[f"en:zh-hk:{key}"] = {
            "source_text": key,
            "translated_text": value,
            "translation_status": status,
            "quality_score": 0.5,  # unknown quality, conservative default
            "verified": False,
            # ... fill remaining fields with defaults
        }
    return build_v2_cache(new_entries)
```

---

## 3. Parallel API Translation with Free/Paid Fallback

### Provider Configuration

Define providers as a structured config, not hardcoded strings. This allows multiple API keys per provider and easy model tier management.

```python
PROVIDER_CONFIG = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_keys": ["key_A", "key_B", "key_C"],  # Round-robin / parallel allowed
        "free_models": [
            "mistralai/mistral-7b-instruct:free",
            "google/gemma-7b-it:free",
            "meta-llama/llama-3-8b-instruct:free",
        ],
        "paid_models": [
            "anthropic/claude-3-haiku",
            "openai/gpt-4o-mini",
        ],
        "rate_limit_rpm": 60,
    },
    "deepl": {
        "base_url": "https://api-free.deepl.com/v2",
        "api_keys": ["deepl_key_1"],
        "free_models": ["deepl-free"],
        "paid_models": ["deepl-pro"],
        "rate_limit_rpm": 30,
    },
}

# Priority order: try free models first, escalate to paid on failure
TRANSLATION_PRIORITY = [
    ("openrouter", "free"),
    ("deepl", "free"),
    ("openrouter", "paid"),
    ("deepl", "paid"),
]
```

### Parallel Translation Pipeline

```
Story Text
    │
    ▼
┌──────────────────────────┐
│  Text Segmenter          │  Split into sentences / dialogue bubbles
│  (preserve order index)  │
└──────────────────────────┘
    │  [(idx=0, "Hello"), (idx=1, "World"), ...]
    ▼
┌──────────────────────────┐
│  Cache Filter            │  Remove already-cached valid translations
└──────────────────────────┘
    │  Uncached segments only
    ▼
┌──────────────────────────────────────────────────────────┐
│  asyncio.gather() — parallel translation tasks           │
│                                                          │
│  Task 0 ──► Provider Router ──► Free API ──► Result 0   │
│  Task 1 ──► Provider Router ──► Free API ──► Result 1   │
│  Task 2 ──► Provider Router ──► Free API ──► Result 2   │
│  ...                                                     │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Results Merger          │  Re-order by original index
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Cache Writer            │  Store all successful translations
└──────────────────────────┘
    │
    ▼
Final Translated Story
```

### Provider Router Logic (per task)

```python
async def translate_with_fallback(text: str, src: str, tgt: str) -> TranslationResult:
    for (provider_name, tier) in TRANSLATION_PRIORITY:
        provider = PROVIDER_CONFIG[provider_name]
        models = provider["free_models"] if tier == "free" else provider["paid_models"]

        # Rotate through available API keys for this provider
        api_key = next_api_key(provider_name)

        for model in models:
            try:
                result = await call_api(
                    base_url=provider["base_url"],
                    api_key=api_key,
                    model=model,
                    text=text,
                    src=src,
                    tgt=tgt,
                )
                return TranslationResult(
                    text=result,
                    model=model,
                    provider=provider_name,
                    status="success"
                )
            except RateLimitError:
                rotate_api_key(provider_name)  # Try next key
                continue
            except APIError:
                continue  # Try next model

    # All providers exhausted
    return TranslationResult(text=text, status="api_failed")
```

### Concurrency Controls

- Set a max concurrency semaphore (e.g. `asyncio.Semaphore(10)`) to avoid flooding free-tier rate limits.
- Track per-provider request counts within a rolling 60-second window.
- Prefer distributing segments across multiple API keys simultaneously rather than sequentially.

---

## 4. Text Positioning & Collision Resolution

### Core Principle

> The translated text must be rendered at the **exact same coordinates** as the original OCR-detected text bounding box. The translation does not move the anchor; it only replaces the content.

### Translated Text Box Schema

```python
@dataclass
class TextBox:
    id: str
    original_text: str
    translated_text: str
    x: int           # Top-left X (pixels), from OCR — immutable
    y: int           # Top-left Y (pixels), from OCR — immutable
    width: int       # Original bounding box width — soft constraint
    height: int      # Original bounding box height — soft constraint
    font_size: float
    collision_resolved: bool = False
    expansion_applied: bool = False
```

### Collision Resolver

When multiple translated text boxes overlap (common after translation since target text length differs from source), the `collision_resolver` must fix them **without moving boxes away from their original anchor points**.

Resolution priority (in order):

1. **Font size reduction** — Shrink font until text fits within original box.
2. **Line wrapping** — Wrap text to multiple lines within original width.
3. **Box expansion inward** — Expand the rendering box toward the bubble center (not outward past the bubble boundary — see Section 5).
4. **Vertical overflow allowed** — Allow height to grow downward if no sibling box exists below.
5. **Flag for manual review** — If none of the above resolve the collision, mark the box `needs_review = True` and render at reduced opacity.

```python
def resolve_collisions(boxes: list[TextBox], bubble_masks: dict) -> list[TextBox]:
    """
    Resolve overlapping translated text boxes.
    Never changes x, y (anchor position).
    """
    sorted_boxes = sort_by_reading_order(boxes)  # Top-to-bottom, right-to-left for manga

    for i, box in enumerate(sorted_boxes):
        siblings = [b for b in sorted_boxes if b.id != box.id]
        
        if not has_collision(box, siblings):
            continue

        # Step 1: Reduce font
        if try_fit_by_font_reduction(box):
            continue

        # Step 2: Wrap text
        if try_fit_by_line_wrap(box):
            continue

        # Step 3: Expand within bubble
        bubble_mask = bubble_masks.get(box.id)
        if bubble_mask and try_expand_within_bubble(box, bubble_mask):
            box.expansion_applied = True
            continue

        # Step 4: Flag
        box.needs_review = True

    return sorted_boxes
```

---

## 5. Bubble-Aware Text Expansion

### Objective

When translated text is longer than the original and needs more space, expand the text rendering area **only within the speech bubble boundary** — never past it.

### Processing Pipeline

```
Input Image
    │
    ▼
┌──────────────────────────────┐
│  1. Preprocessing            │
│   - Grayscale conversion     │
│   - Gaussian blur (denoise)  │
│   - Otsu binarization        │
│   - Canny edge detection     │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│  2. Contour Detection        │
│   - cv2.findContours()       │
│   - Filter by:               │
│     • area > min_bubble_px   │
│     • solidity > 0.7         │
│     • aspect_ratio in [0.3,3]│
│     • convexity (closed)     │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│  3. Bubble Classification    │
│   - Reject contours with     │
│     high internal texture    │
│     (likely artwork, not     │
│     bubble)                  │
│   - Score remaining contours │
│     as bubble candidates     │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│  4. OCR Box → Bubble Mapping │
│   - For each OCR text box,   │
│     find the bubble contour  │
│     that contains its center │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│  5. Bubble Mask Generation   │
│   - Create binary mask per   │
│     bubble contour           │
│   - Erode mask by padding    │
│     to create safe zone      │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│  6. Box Expansion            │
│   - Expand text box outward  │
│     from anchor (x, y)       │
│   - Clip to bubble mask      │
│   - Verify no overlap with   │
│     other text boxes         │
└──────────────────────────────┘
    │
    ▼
Expanded Text Boxes (bubble-constrained)
```

### Bubble Classifier Thresholds (tunable per art style)

```python
BUBBLE_DETECTION_PARAMS = {
    "min_area_px": 2000,
    "max_area_ratio": 0.4,     # Bubble should not cover > 40% of image
    "min_solidity": 0.70,
    "max_texture_variance": 50, # Low = smooth bubble interior
    "aspect_ratio_min": 0.3,
    "aspect_ratio_max": 3.0,
    "canny_low": 50,
    "canny_high": 150,
    "mask_erosion_px": 8,       # Inner padding to keep text away from bubble edge
}
```

### Art Style Profiles

Different manga styles need different tuning. Pre-define profiles:

| Profile | `min_solidity` | `max_texture_variance` | Use case |
|---------|---------------|----------------------|----------|
| `clean_digital` | 0.85 | 30 | Modern webtoon / digital manga |
| `classic_screentone` | 0.70 | 80 | Traditional screentone manga |
| `rough_sketch` | 0.60 | 120 | Doujinshi / rough art styles |

Apply profile at runtime based on image analysis or user configuration.

---

## 6. Cross-Page Consistency — Comic-Level Glossary & Story Context

### Problem

Translating each page independently means the model has **no memory** of decisions made on previous pages. This causes:

- Character names translated differently across pages (e.g. "艾倫" on page 1, "愛倫" on page 20)
- Proper nouns (locations, spells, weapons, titles) inconsistently rendered
- Tone and speech style of characters drifting (a formal character suddenly speaking casually)
- Story-critical terms (e.g. a power system's name) that must stay fixed throughout

### Solution Architecture: Comic Session Layer

Introduce a **Comic Session** object that lives above the per-page translation pipeline. It owns two things:

1. A **Glossary** — locked translations for proper nouns, character names, and story terms
2. A **Story Context Window** — a rolling summary of recent dialogue/narration passed to the API as system context

```
┌───────────────────────────────────────────────────────────┐
│                     Comic Session                         │
│                                                           │
│  ┌──────────────────┐    ┌────────────────────────────┐  │
│  │     Glossary      │    │   Story Context Window     │  │
│  │  (locked terms)   │    │  (rolling page summaries)  │  │
│  └──────────────────┘    └────────────────────────────┘  │
│            │                          │                   │
│            └──────────┬───────────────┘                   │
│                       │ injected into every API call      │
└───────────────────────┼───────────────────────────────────┘
                        │
            ┌───────────▼───────────┐
            │   Per-Page Pipeline   │  (OCR → Translate → Render)
            └───────────────────────┘
```

### 6.1 Comic Glossary

The glossary is a scoped, versioned lookup table that maps source terms to their locked translations. It is **comic-specific**, stored alongside the comic project, and separate from the general translation cache.

#### Glossary Schema

```json
{
  "comic_id": "my_comic_001",
  "source_lang": "en",
  "target_lang": "zh-hk",
  "version": 1,
  "last_updated": 1738000000.0,
  "entries": {
    "Eren": {
      "translated": "艾倫",
      "category": "character_name",
      "first_seen_page": 1,
      "locked": true,
      "notes": "Main protagonist"
    },
    "Titan": {
      "translated": "巨人",
      "category": "story_term",
      "first_seen_page": 1,
      "locked": true,
      "notes": null
    },
    "Survey Corps": {
      "translated": "調查兵團",
      "category": "faction_name",
      "first_seen_page": 3,
      "locked": true,
      "notes": null
    }
  }
}
```

#### Glossary Entry Categories

| Category | Examples | Behaviour |
|----------|----------|-----------|
| `character_name` | Eren, Mikasa, Naruto | Always locked; never re-translated |
| `faction_name` | Survey Corps, Akatsuki | Locked after first confirmed translation |
| `location_name` | Wall Maria, Konoha | Locked after first confirmed translation |
| `story_term` | Titan, chakra, Stand | Locked; may have style notes |
| `sfx` | BOOM, CRASH, BAM | Flexible; can have style override per scene |
| `title_honorific` | -san, -kun, -senpai | Policy decision: keep or translate |

#### Glossary Population — Two-Phase Approach

**Phase 1 — Auto-discovery (before translating any page):**

Run a pre-scan pass over all pages' OCR output. Feed the raw text to the LLM with a prompt specifically asking it to identify proper nouns, character names, and recurring terms, without translating yet.

```python
DISCOVERY_PROMPT = """
You are analyzing raw OCR text from a comic. 
Identify ALL of the following without translating them:
- Character names
- Location names  
- Organization/faction names
- Special terms, powers, or story-specific vocabulary
- Sound effects (SFX)

Return as JSON: {"terms": [{"text": "...", "category": "...", "confidence": 0.0}]}
Only return the JSON, no explanation.

OCR Text from all pages:
{all_ocr_text}
"""
```

**Phase 2 — Human confirmation (optional but recommended):**

Present discovered terms to the user for confirmation and manual translation before starting the main translation pass. Any term confirmed here gets `"locked": true` immediately.

For fully automated pipelines, skip Phase 2 and use Phase 1 results with `"locked": false` — these can still be overridden if the model returns a different translation for the same term.

### 6.2 Story Context Window

The context window solves the **coherence** problem — ensuring the model understands who is speaking, what has happened, and what the emotional tone is.

#### Context Window Schema

```python
@dataclass
class StoryContextWindow:
    comic_id: str
    max_pages: int = 5          # How many previous pages to keep in context
    max_chars: int = 2000       # Hard cap on total context characters (token budget)
    pages: list[PageSummary]    # Rolling buffer, oldest dropped when full
```

```python
@dataclass  
class PageSummary:
    page_number: int
    key_events: str             # 1-3 sentence summary of what happened
    speakers_on_page: list[str] # Character names who appeared
    emotional_tone: str         # e.g. "tense", "comedic", "sad"
```

#### Context Injection into API Calls

Every translation API call receives a system prompt that includes:

```python
def build_translation_system_prompt(
    glossary: ComicGlossary,
    context_window: StoryContextWindow,
    target_lang: str
) -> str:
    glossary_block = "\n".join(
        f'- "{e.source}" → "{e.translated}" ({e.category})'
        for e in glossary.locked_entries()
    )
    
    context_block = "\n".join(
        f'Page {p.page_number}: {p.key_events} [Tone: {p.emotional_tone}]'
        for p in context_window.pages[-3:]  # Last 3 pages max
    )
    
    return f"""You are translating a comic from English to {target_lang}.

LOCKED GLOSSARY — use these translations exactly, never deviate:
{glossary_block}

RECENT STORY CONTEXT:
{context_block}

RULES:
1. Preserve each character's consistent speech style and personality.
2. Never retranslate any term in the locked glossary.
3. Keep SFX punchy and short.
4. Translate each bubble independently but with awareness of the scene context above.
5. Return only the translated text, no explanation.
"""
```

#### Context Window Update (after each page)

After a page is translated, generate a page summary and append it to the context window:

```python
PAGE_SUMMARY_PROMPT = """
In 1-3 sentences, summarize what happened on this comic page.
Include: who spoke, what key events occurred, and the emotional tone.
Be brief — this will be used as context for translating the next page.

Translated dialogue from page {page_num}:
{translated_dialogue}
"""
```

This summary generation can run in parallel with rendering the current page (it doesn't block the pipeline).

### 6.3 Conflict Resolution — Glossary vs Cache

The glossary and the translation cache can conflict. The priority order is:

```
1. Glossary (locked=true)     ← always wins
2. Glossary (locked=false)    ← wins unless cache entry is verified=true
3. Cache (verified=true)      ← human-confirmed, high trust
4. Cache (success, high QS)   ← auto translation, good quality
5. Live API call              ← no cache hit
```

If a live API call returns a translation that **contradicts** a locked glossary term, the response is post-processed to enforce the glossary before storing in cache:

```python
def enforce_glossary(raw_translation: str, glossary: ComicGlossary) -> str:
    """Replace any glossary violations in the raw API output."""
    result = raw_translation
    for entry in glossary.locked_entries():
        # Replace any known variant spellings with the locked translation
        for variant in entry.known_variants:
            result = result.replace(variant, entry.translated)
    return result
```

### 6.4 Two-Pass Comic Processing Pipeline

The full comic pipeline now has **two passes** instead of one:

```
PASS 1 — Discovery Pass (fast, no translation)
══════════════════════════════════════════════
For each page (can be parallel):
  ├── OCR
  ├── OCR Noise Filter
  └── Extract raw text → accumulate

After all pages:
  ├── Run Glossary Discovery (LLM prompt on all OCR text)
  ├── [Optional] Human confirmation of glossary
  └── Save comic_glossary.json

PASS 2 — Translation Pass (sequential by page for context continuity)
══════════════════════════════════════════════════════════════════════
For each page (in order, page 1 → last):
  ├── Bubble Detection
  ├── Glossary Lookup (pre-filter known terms)
  ├── Cache Lookup (v2)
  ├── Parallel API Translation (with glossary + context injected)
  ├── Glossary Enforcement (post-process API output)
  ├── Cache Write
  ├── Collision Resolution + Bubble Expansion
  ├── Render Page
  └── Generate Page Summary → append to Context Window
```

**Why Pass 2 is sequential (not parallel across pages):**

Pages must be translated in order because each page's context window depends on the summary of the previous page. However, within a page, individual bubbles are still translated in parallel.

---

## 7. End-to-End System Flow (Updated)

```
╔══════════════════════════════════════════════════════════════╗
║                 PASS 1 — DISCOVERY (parallel OK)             ║
╠══════════════════════════════════════════════════════════════╣
║  [All Pages] → OCR → Noise Filter → Accumulate Raw Text      ║
║       │                                                       ║
║       ▼                                                       ║
║  [Glossary Discovery LLM] → Comic Glossary JSON              ║
║       │                                                       ║
║       ▼                                                       ║
║  [Optional: Human Review] → Lock terms                       ║
╚══════════════════════════════════════════════════════════════╝
                        │
                        ▼
╔══════════════════════════════════════════════════════════════╗
║           PASS 2 — TRANSLATION (sequential by page)          ║
╠══════════════════════════════════════════════════════════════╣
║  For each page in order:                                      ║
║                                                               ║
║  [Bubble Detection] ────────────────► Bubble Masks           ║
║       │                                                       ║
║       ▼                                                       ║
║  [Glossary Pre-filter] ◄──── Comic Glossary                  ║
║       │  known terms resolved instantly                       ║
║       ▼                                                       ║
║  [Cache Lookup v2] ◄──── Translation Cache                   ║
║       │  uncached texts only                                  ║
║       ▼                                                       ║
║  [Build API Prompt]                                           ║
║   = Glossary block + Context Window + bubbles                 ║
║       │                                                       ║
║       ▼                                                       ║
║  [Parallel API Translation] ◄── Provider Config              ║
║   (free-first, multi-key, per-bubble parallel)                ║
║       │                                                       ║
║       ▼                                                       ║
║  [Glossary Enforcement] — fix any glossary violations        ║
║       │                                                       ║
║       ▼                                                       ║
║  [Cache Write v2]                                             ║
║       │                                                       ║
║       ▼                                                       ║
║  [Text Box Builder] → [Collision Resolver] → [Bubble Expander]║
║       │                                                       ║
║       ▼                                                       ║
║  [Render Page Output]                                         ║
║       │                                                       ║
║       ▼                                                       ║
║  [Generate Page Summary] → append to Context Window ──┐      ║
║                                                        │      ║
║  Next page ◄───────────────────────────────────────────┘      ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 8. UI Bug — Post-Translation Text Colour Collision (Python Qt)

### Problem

After translating a block of text inside a `QTextEdit`, any new characters typed by the user become invisible — either black text on a black background, or white text on a white background. The UI's font colour picker correctly shows black, meaning the bug is **not** in the foreground colour setting.

### Root Cause — `QTextCursor` Inherits `QTextCharFormat` from Inserted Text

In Qt's rich text engine, every cursor position carries a `QTextCharFormat` that defines the formatting of text typed at that position. When translated text is inserted with a `QTextCharFormat` that has `background-color` set (explicitly or accidentally), the cursor **inherits that format**. All subsequent keystrokes are painted with the same `background-color` until something resets it.

```
User selects original text → cursor format = {color: black, bg: transparent}

Translation inserted via setHtml() or insertHtml():
  → Qt parses the HTML and applies its inline styles to the block
  → cursor now sits at end of inserted block
  → cursor format = {color: black, bg: white}   ← rogue bg inherited

User types new characters:
  → Qt uses cursor's current QTextCharFormat for new chars
  → new chars get bg: white
  → if editor palette background is also white → invisible (white on white)
  → if editor palette background is dark      → invisible (white on dark... 
      unless color also flipped to white)
```

The UI's colour picker calls `setTextColor()` which sets `color` only — it has no knowledge of the hidden `background-color` sitting in the cursor's format.

### Three Root Causes & Fixes

**Root Cause A — Using `setHtml()` or `insertHtml()` to insert translation result**

`insertHtml()` is the most common culprit. If the translation API returns any HTML (even `<p>` tags with default styles), Qt's HTML parser will apply `background-color: white` from the default HTML body background. This contaminates the cursor format.

```python
# ❌ Wrong — Qt applies HTML default background-color to cursor format
self.text_edit.insertHtml(translated_text)
self.text_edit.setHtml(translated_text)

# ✅ Correct — plain text insertion, no format contamination
cursor = self.text_edit.textCursor()
cursor.insertText(translated_text)       # inherits CURRENT cursor format only

# ✅ Also correct — strip HTML to plain text before inserting
import re
plain = re.sub(r'<[^>]+>', '', translated_text).strip()
cursor.insertText(plain)
```

**Root Cause B — Inserting text with an explicit `QTextCharFormat` that has background set**

If the code builds a `QTextCharFormat` to style the translated text, a missing reset on `background` will carry it forward:

```python
# ❌ Wrong — fmt has background set; cursor inherits it after insertion
fmt = QTextCharFormat()
fmt.setForeground(QColor("black"))
fmt.setBackground(QColor("white"))   # ← this is the bug; omitting reset is enough
cursor.insertText(translated_text, fmt)

# ✅ Correct — explicitly use transparent / invalid background
fmt = QTextCharFormat()
fmt.setForeground(QColor("black"))
fmt.setBackground(Qt.GlobalColor.transparent)  # or QColor(0, 0, 0, 0)
cursor.insertText(translated_text, fmt)
```

**Root Cause C — Cursor format not reset after insertion**

Even if the insertion itself is clean, if the cursor ends up inside a block that has a `background-color` applied at the block level (`QTextBlockFormat`), subsequent typing will still inherit it. The fix is to explicitly reset the cursor's char format after every translation insertion:

```python
def reset_cursor_format(self):
    """
    Call this immediately after any translation insertion.
    Forces the cursor's active QTextCharFormat back to a clean state
    so the next typed character inherits no rogue background-color.
    """
    cursor = self.text_edit.textCursor()

    clean_fmt = QTextCharFormat()
    # Restore user's chosen font colour from the UI picker
    clean_fmt.setForeground(self.current_text_color)
    # Explicitly clear background — transparent means "use widget palette"
    clean_fmt.setBackground(Qt.GlobalColor.transparent)
    # Preserve font family/size if needed
    clean_fmt.setFont(self.text_edit.currentFont())

    cursor.setCharFormat(clean_fmt)
    self.text_edit.setTextCursor(cursor)
    # Also update the widget-level current format so typing picks it up
    self.text_edit.setCurrentCharFormat(clean_fmt)
```

### Recommended Fix — Centralised `insert_translation()` Method

All three root causes are avoided by routing every translation insertion through one function:

```python
from PyQt6.QtGui import QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt

def insert_translation(self, raw_translated: str):
    """
    Safely insert translated text into QTextEdit.
    - Strips all HTML from API response
    - Inserts as plain text with explicit clean format
    - Resets cursor format after insertion so next typed chars are clean
    """
    # Step 1: Strip any HTML the API may have returned
    import re
    plain_text = re.sub(r'<[^>]+>', '', raw_translated).strip()

    # Step 2: Build an explicit clean format
    fmt = QTextCharFormat()
    fmt.setForeground(self.current_text_color)          # user's chosen colour
    fmt.setBackground(Qt.GlobalColor.transparent)        # NO background colour
    fmt.setFont(self.text_edit.currentFont())

    # Step 3: Insert at current cursor with the clean format
    cursor = self.text_edit.textCursor()
    cursor.insertText(plain_text, fmt)

    # Step 4: Move cursor to end of inserted text, then reset format
    #         so the NEXT keystroke also gets the clean format
    self.text_edit.setTextCursor(cursor)
    self.text_edit.setCurrentCharFormat(fmt)            # ← critical line
```

The critical line is `setCurrentCharFormat(fmt)` at the end. Qt uses this as the "typing format" — the format applied to the very next character the user types. Without it, Qt falls back to the format of whatever block the cursor is now sitting in, which may still carry the rogue background.

### Defensive Baseline — Override `QTextEdit` Paste

If the user can also paste translated text manually, override `insertFromMimeData` to strip formatting on paste:

```python
class SafeTextEdit(QTextEdit):
    """QTextEdit that always pastes as plain text to prevent format contamination."""

    def insertFromMimeData(self, source):
        if source.hasText():
            # Force plain text paste — strip all rich text / HTML formatting
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)
```

### Summary of Changes Required

| Location | Change |
|----------|--------|
| Translation result insertion | Replace `insertHtml()` with `cursor.insertText(plain, clean_fmt)` |
| `QTextCharFormat` construction | Always set `setBackground(Qt.GlobalColor.transparent)` explicitly |
| After every translation insert | Call `setCurrentCharFormat(clean_fmt)` to reset typing format |
| Paste handler | Subclass `QTextEdit`, override `insertFromMimeData` to strip rich text |
| All translation paths | Route through single `insert_translation()` method |

---

## 9. Open Issues & Next Steps

| Issue | Priority | Notes |
|-------|----------|-------|
| OCR engine selection (Tesseract vs EasyOCR vs manga-ocr) | High | manga-ocr recommended for Japanese source |
| Glossary discovery prompt quality | High | Needs testing across multiple comic genres; false positives (common words flagged as proper nouns) are a risk |
| Context window token budget | High | Free models have small context limits (~4k tokens); keep context block under 500 tokens |
| Page summary generation cost | Medium | Adds one extra LLM call per page; can use cheapest free model for summaries |
| Glossary conflict resolution when two pages disagree | Medium | First-seen page wins by default; needs override mechanism |
| Bubble detection fallback when no contour found | High | Use full OCR bounding box as safe default |
| Manual review UI for `needs_review` boxes and glossary | Medium | Flag in output JSON; surface in a review tool |
| Art style profile auto-detection | Low | Could use image statistics to pick profile automatically |
| Cache persistence format (JSON vs SQLite) | Medium | SQLite recommended once entries exceed ~10,000 |
| Post-translation colour collision in editor | High | See Section 8 — root cause is rogue `background-color` inheritance; fix via centralised `insertTranslation()` |
