# Manga Translation System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all 9 sections from manga_translation_system_plan.md into the existing comic-translate codebase.

**Architecture:** Each section is an independent module layered on top of the existing pipeline. The cache v2 replaces CacheManager's in-memory dicts. The glossary/context layer wraps TranslationHandler. OCR noise filtering slots into OCRHandler before caching.

**Tech Stack:** Python 3.12, PySide6, asyncio, OpenCV (cv2), PIL, numpy, existing pipeline/modules structure.

---

## Section 1 — OCR Noise Filtering

### Task 1: OCR Noise Filter Module

**Files:**
- Create: `modules/ocr/noise_filter.py`
- Modify: `pipeline/ocr_handler.py`
- Test: `tests/ocr/test_noise_filter.py`

**Step 1: Create tests/ocr/ directory and write failing tests**

```python
# tests/ocr/test_noise_filter.py
import pytest
from modules.ocr.noise_filter import OCRNoiseFilter, NoiseType

def test_phantom_symbol_run_detected():
    f = OCRNoiseFilter()
    result = f.filter_text('21,"0~(!!","川"')
    assert result.strip() == ""

def test_clean_text_passes():
    f = OCRNoiseFilter()
    result = f.filter_text("Hello world")
    assert result == "Hello world"

def test_low_confidence_token_flagged():
    f = OCRNoiseFilter()
    tokens = [("Hello", 0.9), ("world", 0.3)]
    clean = f.filter_tokens(tokens, threshold=0.4)
    assert clean == ["Hello"]

def test_misread_punctuation_cleaned():
    f = OCRNoiseFilter()
    result = f.filter_text("%.")
    assert result == ""
```

**Step 2: Run to verify failure**

```bash
cd /c/Users/a1667/JetbrainsProject/01-AI-ML-Projects/comic-translate
uv run pytest tests/ocr/test_noise_filter.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

**Step 3: Create `modules/ocr/noise_filter.py`**

```python
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional

class NoiseType(Enum):
    PHANTOM = "ocr_noise.phantom"
    MISREAD = "ocr_noise.misread"

@dataclass
class NoiseEntry:
    original: str
    noise_type: NoiseType

# Regex: runs of 2+ non-alphanumeric, non-CJK, non-space chars
_SYMBOL_RUN = re.compile(r'[^\w\s\u3000-\u9fff\uff00-\uffef]{2,}')
# Regex: mixed symbol+digit garbage like 21,"0~(!!"
_GARBAGE = re.compile(r'\d+[,"\'\~\!\(\)\[\]]{2,}')

class OCRNoiseFilter:
    def filter_tokens(
        self,
        tokens: List[Tuple[str, float]],
        threshold: float = 0.4
    ) -> List[str]:
        """Drop tokens whose confidence is below threshold."""
        return [t for t, conf in tokens if conf >= threshold]

    def filter_text(self, text: str) -> str:
        """Remove phantom/misread noise patterns from raw OCR text."""
        text = _GARBAGE.sub("", text)
        text = _SYMBOL_RUN.sub("", text)
        return text.strip()

    def filter_block_text(
        self,
        text: str,
        tokens: Optional[List[Tuple[str, float]]] = None,
        confidence_threshold: float = 0.4
    ) -> Tuple[str, List[NoiseEntry]]:
        """
        Full pipeline: confidence filter → pattern filter.
        Returns (clean_text, noise_log).
        """
        noise_log: List[NoiseEntry] = []

        if tokens:
            clean_tokens = []
            for tok, conf in tokens:
                if conf < confidence_threshold:
                    noise_log.append(NoiseEntry(tok, NoiseType.PHANTOM))
                else:
                    clean_tokens.append(tok)
            text = " ".join(clean_tokens)

        cleaned = self.filter_text(text)
        if cleaned != text:
            noise_log.append(NoiseEntry(text, NoiseType.MISREAD))

        return cleaned, noise_log
```

**Step 4: Run tests**

```bash
uv run pytest tests/ocr/test_noise_filter.py -v
```
Expected: all 4 PASS

**Step 5: Wire into OCRHandler**

In `pipeline/ocr_handler.py`, after OCR runs and before caching, add:

```python
from modules.ocr.noise_filter import OCRNoiseFilter

# In OCRHandler.__init__:
self.noise_filter = OCRNoiseFilter()

# After OCR produces blk_list, before _cache_ocr_results:
for blk in blk_list:
    if blk.text:
        blk.text, _ = self.noise_filter.filter_block_text(blk.text)
```

**Step 6: Commit**

```bash
git add modules/ocr/noise_filter.py pipeline/ocr_handler.py tests/ocr/test_noise_filter.py tests/ocr/__init__.py
git commit -m "feat: add OCR noise filter for phantom and misread characters"
```


---

## Section 2 — Translation Cache v2

### Task 2: Cache v2 Data Structure

**Files:**
- Create: `pipeline/cache_v2.py`
- Create: `tests/pipeline/test_cache_v2.py`

**Step 1: Write failing tests**

```python
# tests/pipeline/test_cache_v2.py
import pytest, time
from pipeline.cache_v2 import TranslationCacheV2, TranslationStatus

def test_empty_cache_has_version():
    c = TranslationCacheV2()
    assert c.data["version"] == "2.0"

def test_store_and_retrieve_success():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Hello", "你好", model="gpt-4o-mini")
    result = c.get("en", "zh-hk", "Hello")
    assert result == "你好"

def test_api_failed_entry_not_served():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Hello", "Hello",
            status=TranslationStatus.API_FAILED)
    result = c.get("en", "zh-hk", "Hello")
    assert result is None

def test_source_equals_target_stored_as_untranslatable():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Eren", "Eren")
    entry = c._get_entry("en", "zh-hk", "Eren")
    assert entry["translation_status"] == TranslationStatus.UNTRANSLATABLE.value

def test_usage_count_increments():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Hi", "嗨")
    c.get("en", "zh-hk", "Hi")
    c.get("en", "zh-hk", "Hi")
    entry = c._get_entry("en", "zh-hk", "Hi")
    assert entry["usage_count"] == 2

def test_migrate_v1_flat_cache():
    from pipeline.cache_v2 import migrate_v1_to_v2
    old = {"Hello": "你好", "Eren": "Eren"}
    new = migrate_v1_to_v2(old, src="en", tgt="zh-hk")
    assert new["version"] == "2.0"
    assert new["entries"]["en:zh-hk:Hello"]["translation_status"] == "success"
    assert new["entries"]["en:zh-hk:Eren"]["translation_status"] == "untranslatable"
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/pipeline/test_cache_v2.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `pipeline/cache_v2.py`**

```python
import time
from enum import Enum
from typing import Optional

class TranslationStatus(Enum):
    SUCCESS = "success"
    API_FAILED = "api_failed"
    UNTRANSLATABLE = "untranslatable"
    PENDING_REVIEW = "pending_review"

def _make_key(src: str, tgt: str, text: str) -> str:
    return f"{src}:{tgt}:{text}"

def _empty_store() -> dict:
    return {
        "version": "2.0",
        "saved_at": time.time(),
        "stats": {
            "total_entries": 0,
            "total_hits": 0,
            "total_misses": 0,
            "total_updates": 0,
            "failed_api_fallbacks": 0,
        },
        "entries": {},
    }

class TranslationCacheV2:
    def __init__(self, data: Optional[dict] = None):
        self.data = data if data and data.get("version") == "2.0" else _empty_store()

    def store(
        self,
        src: str,
        tgt: str,
        source_text: str,
        translated_text: str,
        model: str = "",
        status: TranslationStatus = None,
        quality_score: float = 1.0,
    ) -> None:
        if status is None:
            status = (
                TranslationStatus.UNTRANSLATABLE
                if source_text == translated_text
                else TranslationStatus.SUCCESS
            )
        key = _make_key(src, tgt, source_text)
        now = time.time()
        existing = self.data["entries"].get(key)
        if existing:
            existing.update({
                "translated_text": translated_text,
                "updated_at": now,
                "model": model,
                "translation_status": status.value,
                "quality_score": quality_score,
                "version": existing["version"] + 1,
                "previous_translation": existing["translated_text"],
            })
            self.data["stats"]["total_updates"] += 1
        else:
            self.data["entries"][key] = {
                "source_text": source_text,
                "translated_text": translated_text,
                "source_lang": src,
                "target_lang": tgt,
                "created_at": now,
                "updated_at": now,
                "model": model,
                "confidence": quality_score,
                "usage_count": 0,
                "last_used": now,
                "quality_score": quality_score,
                "verified": False,
                "translation_status": status.value,
                "version": 1,
                "previous_translation": None,
            }
            self.data["stats"]["total_entries"] += 1

    def get(self, src: str, tgt: str, source_text: str) -> Optional[str]:
        key = _make_key(src, tgt, source_text)
        entry = self.data["entries"].get(key)
        if not entry:
            self.data["stats"]["total_misses"] += 1
            return None
        status = entry["translation_status"]
        if status in (TranslationStatus.SUCCESS.value, TranslationStatus.UNTRANSLATABLE.value):
            entry["usage_count"] += 1
            entry["last_used"] = time.time()
            self.data["stats"]["total_hits"] += 1
            return entry["translated_text"]
        self.data["stats"]["total_misses"] += 1
        return None

    def _get_entry(self, src: str, tgt: str, source_text: str) -> Optional[dict]:
        return self.data["entries"].get(_make_key(src, tgt, source_text))


def migrate_v1_to_v2(old: dict, src: str = "en", tgt: str = "en") -> dict:
    """Migrate flat KV cache to v2 schema."""
    cache = TranslationCacheV2()
    for source_text, translated_text in old.items():
        if isinstance(source_text, str) and isinstance(translated_text, str):
            status = (
                TranslationStatus.UNTRANSLATABLE
                if source_text == translated_text
                else TranslationStatus.SUCCESS
            )
            cache.store(src, tgt, source_text, translated_text,
                        status=status, quality_score=0.5)
    return cache.data
```

**Step 4: Run tests**

```bash
uv run pytest tests/pipeline/test_cache_v2.py -v
```
Expected: all 6 PASS

**Step 5: Commit**

```bash
git add pipeline/cache_v2.py tests/pipeline/test_cache_v2.py tests/pipeline/__init__.py tests/__init__.py
git commit -m "feat: add translation cache v2 with status tracking and v1 migration"
```


---

## Section 3 — Parallel API Translation with Free/Paid Fallback

### Task 3: Provider Config and Async Translation Router

**Files:**
- Create: `modules/translation/provider_config.py`
- Create: `modules/translation/async_router.py`
- Create: `tests/translation/test_async_router.py`

**Step 1: Write failing tests**

```python
# tests/translation/test_async_router.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from modules.translation.async_router import AsyncTranslationRouter, TranslationResult

def test_result_success():
    r = TranslationResult(text="你好", model="free-model", provider="openrouter", status="success")
    assert r.is_success()

def test_result_failed():
    r = TranslationResult(text="Hello", model="", provider="", status="api_failed")
    assert not r.is_success()

@pytest.mark.asyncio
async def test_router_returns_success_on_first_provider(monkeypatch):
    from modules.translation.async_router import AsyncTranslationRouter
    router = AsyncTranslationRouter()

    async def fake_call(base_url, api_key, model, text, src, tgt):
        return "你好"

    monkeypatch.setattr(router, "_call_api", fake_call)
    result = await router.translate("Hello", "en", "zh-hk")
    assert result.status == "success"
    assert result.text == "你好"

@pytest.mark.asyncio
async def test_router_falls_back_on_failure(monkeypatch):
    from modules.translation.async_router import AsyncTranslationRouter
    router = AsyncTranslationRouter()
    call_count = 0

    async def fake_call(base_url, api_key, model, text, src, tgt):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("rate limit")
        return "你好"

    monkeypatch.setattr(router, "_call_api", fake_call)
    result = await router.translate("Hello", "en", "zh-hk")
    assert result.status == "success"
    assert call_count == 2
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/translation/test_async_router.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `modules/translation/provider_config.py`**

```python
from dataclasses import dataclass, field
from typing import List
from collections import defaultdict
import itertools

@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_keys: List[str]
    free_models: List[str]
    paid_models: List[str]
    rate_limit_rpm: int = 60

# Default config — override via settings or env vars
DEFAULT_PROVIDERS: List[ProviderConfig] = [
    ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_keys=[],
        free_models=[
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free",
        ],
        paid_models=["anthropic/claude-3-haiku", "openai/gpt-4o-mini"],
        rate_limit_rpm=60,
    ),
]

# Priority: free first, then paid
TRANSLATION_PRIORITY = [
    ("openrouter", "free"),
    ("openrouter", "paid"),
]

class KeyRotator:
    """Round-robin API key rotation per provider."""
    def __init__(self):
        self._cycles: dict = {}

    def next_key(self, provider_name: str, keys: List[str]) -> str:
        if not keys:
            return ""
        if provider_name not in self._cycles:
            self._cycles[provider_name] = itertools.cycle(keys)
        return next(self._cycles[provider_name])
```

**Step 4: Create `modules/translation/async_router.py`**

```python
import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Optional, List
from modules.translation.provider_config import (
    DEFAULT_PROVIDERS, TRANSLATION_PRIORITY, KeyRotator, ProviderConfig
)

@dataclass
class TranslationResult:
    text: str
    model: str
    provider: str
    status: str  # "success" | "api_failed"

    def is_success(self) -> bool:
        return self.status == "success"

class AsyncTranslationRouter:
    def __init__(self, providers: Optional[List[ProviderConfig]] = None):
        self.providers = {p.name: p for p in (providers or DEFAULT_PROVIDERS)}
        self._rotator = KeyRotator()
        self._semaphore = asyncio.Semaphore(10)

    async def _call_api(self, base_url: str, api_key: str, model: str,
                        text: str, src: str, tgt: str) -> str:
        """POST to OpenAI-compatible chat completions endpoint."""
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": f"Translate from {src} to {tgt}. Return only the translation."},
                {"role": "user", "content": text},
            ],
            "max_tokens": 500,
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        loop = asyncio.get_event_loop()
        def _do_request():
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _do_request)
        return data["choices"][0]["message"]["content"].strip()

    async def translate(self, text: str, src: str, tgt: str) -> TranslationResult:
        async with self._semaphore:
            for provider_name, tier in TRANSLATION_PRIORITY:
                provider = self.providers.get(provider_name)
                if not provider:
                    continue
                models = provider.free_models if tier == "free" else provider.paid_models
                api_key = self._rotator.next_key(provider_name, provider.api_keys)
                for model in models:
                    try:
                        result = await self._call_api(
                            provider.base_url, api_key, model, text, src, tgt
                        )
                        return TranslationResult(
                            text=result, model=model,
                            provider=provider_name, status="success"
                        )
                    except Exception:
                        continue
            return TranslationResult(text=text, model="", provider="", status="api_failed")

    async def translate_batch(
        self, texts: List[str], src: str, tgt: str
    ) -> List[TranslationResult]:
        """Translate a list of texts in parallel, preserving order."""
        tasks = [self.translate(t, src, tgt) for t in texts]
        return await asyncio.gather(*tasks)
```

**Step 5: Run tests**

```bash
uv run pytest tests/translation/test_async_router.py -v
```
Expected: all 4 PASS

**Step 6: Commit**

```bash
git add modules/translation/provider_config.py modules/translation/async_router.py \
        tests/translation/test_async_router.py tests/translation/__init__.py
git commit -m "feat: add async translation router with free/paid provider fallback"
```


---

## Section 4 — Text Positioning & Collision Resolution

### Task 4: Collision Resolver

**Files:**
- Create: `modules/rendering/collision_resolver.py`
- Create: `tests/rendering/test_collision_resolver.py`

**Step 1: Write failing tests**

```python
# tests/rendering/test_collision_resolver.py
import pytest
import numpy as np
from modules.rendering.collision_resolver import CollisionResolver, RenderBox

def _box(id, x1, y1, x2, y2, text="hello world foo bar"):
    return RenderBox(id=id, x=x1, y=y1, width=x2-x1, height=y2-y1,
                     translated_text=text, font_size=20.0)

def test_no_collision_unchanged():
    boxes = [_box("a", 0, 0, 100, 50), _box("b", 200, 0, 300, 50)]
    resolver = CollisionResolver()
    result = resolver.resolve(boxes, bubble_masks={})
    assert not any(b.needs_review for b in result)

def test_overlapping_boxes_font_reduced():
    boxes = [_box("a", 0, 0, 100, 50), _box("b", 50, 0, 150, 50)]
    resolver = CollisionResolver()
    result = resolver.resolve(boxes, bubble_masks={})
    reduced = [b for b in result if b.font_size < 20.0]
    assert len(reduced) > 0

def test_anchor_xy_never_changes():
    boxes = [_box("a", 10, 20, 110, 70), _box("b", 60, 20, 160, 70)]
    resolver = CollisionResolver()
    result = resolver.resolve(boxes, bubble_masks={})
    for b in result:
        orig = {"a": (10, 20), "b": (60, 20)}[b.id]
        assert (b.x, b.y) == orig
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/rendering/test_collision_resolver.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `modules/rendering/collision_resolver.py`**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np

@dataclass
class RenderBox:
    id: str
    x: int          # anchor — immutable
    y: int          # anchor — immutable
    width: int
    height: int
    translated_text: str
    font_size: float
    collision_resolved: bool = False
    expansion_applied: bool = False
    needs_review: bool = False

def _overlaps(a: RenderBox, b: RenderBox) -> bool:
    return not (
        a.x + a.width <= b.x or b.x + b.width <= a.x or
        a.y + a.height <= b.y or b.y + b.height <= a.y
    )

def _has_collision(box: RenderBox, others: List[RenderBox]) -> bool:
    return any(_overlaps(box, o) for o in others)

def _try_font_reduction(box: RenderBox, min_size: float = 8.0) -> bool:
    if box.font_size <= min_size:
        return False
    box.font_size = max(min_size, box.font_size * 0.85)
    box.collision_resolved = True
    return True

class CollisionResolver:
    def resolve(
        self,
        boxes: List[RenderBox],
        bubble_masks: Dict[str, np.ndarray],
        min_font_size: float = 8.0,
    ) -> List[RenderBox]:
        # Sort top-to-bottom, right-to-left (manga reading order)
        sorted_boxes = sorted(boxes, key=lambda b: (b.y, -b.x))

        for i, box in enumerate(sorted_boxes):
            siblings = [b for b in sorted_boxes if b.id != box.id]
            if not _has_collision(box, siblings):
                continue

            # Step 1: reduce font size up to 3 times
            for _ in range(3):
                if not _has_collision(box, siblings):
                    break
                if not _try_font_reduction(box, min_font_size):
                    break

            if _has_collision(box, siblings):
                box.needs_review = True

        return sorted_boxes
```

**Step 4: Run tests**

```bash
uv run pytest tests/rendering/test_collision_resolver.py -v
```
Expected: all 3 PASS

**Step 5: Commit**

```bash
git add modules/rendering/collision_resolver.py \
        tests/rendering/test_collision_resolver.py tests/rendering/__init__.py
git commit -m "feat: add text collision resolver with font reduction and review flagging"
```


---

## Section 5 — Bubble-Aware Text Expansion

### Task 5: Bubble Detector and Text Expander

**Files:**
- Create: `modules/rendering/bubble_expander.py`
- Create: `tests/rendering/test_bubble_expander.py`

**Step 1: Write failing tests**

```python
# tests/rendering/test_bubble_expander.py
import pytest
import numpy as np
from modules.rendering.bubble_expander import BubbleDetector, BubbleExpander, ArtStyleProfile

def _white_circle_image(size=200, radius=80):
    """Create a white circle on black background — simulates a speech bubble."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    cx, cy = size // 2, size // 2
    for y in range(size):
        for x in range(size):
            if (x - cx)**2 + (y - cy)**2 < radius**2:
                img[y, x] = 255
    return img

def test_bubble_detected_in_circle_image():
    img = _white_circle_image()
    detector = BubbleDetector()
    masks = detector.detect(img)
    assert len(masks) >= 1

def test_no_bubble_in_blank_image():
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    detector = BubbleDetector()
    masks = detector.detect(img)
    assert len(masks) == 0

def test_expander_clips_to_bubble_mask():
    from modules.rendering.collision_resolver import RenderBox
    img = _white_circle_image(size=200, radius=80)
    detector = BubbleDetector()
    masks = detector.detect(img)
    assert masks

    box = RenderBox(id="a", x=80, y=80, width=40, height=40,
                    translated_text="hello", font_size=12.0)
    expander = BubbleExpander()
    expanded = expander.expand(box, masks[0], max_expand_px=30)
    # Expanded box must not exceed image bounds
    assert expanded.x >= 0
    assert expanded.y >= 0
    assert expanded.x + expanded.width <= 200
    assert expanded.y + expanded.height <= 200

def test_art_style_profile_clean_digital():
    p = ArtStyleProfile.clean_digital()
    assert p.min_solidity >= 0.85
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/rendering/test_bubble_expander.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `modules/rendering/bubble_expander.py`**

```python
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from modules.rendering.collision_resolver import RenderBox

@dataclass
class BubbleDetectionParams:
    min_area_px: int = 2000
    max_area_ratio: float = 0.4
    min_solidity: float = 0.70
    max_texture_variance: float = 50.0
    aspect_ratio_min: float = 0.3
    aspect_ratio_max: float = 3.0
    canny_low: int = 50
    canny_high: int = 150
    mask_erosion_px: int = 8

class ArtStyleProfile:
    @staticmethod
    def clean_digital() -> BubbleDetectionParams:
        return BubbleDetectionParams(min_solidity=0.85, max_texture_variance=30)

    @staticmethod
    def classic_screentone() -> BubbleDetectionParams:
        return BubbleDetectionParams(min_solidity=0.70, max_texture_variance=80)

    @staticmethod
    def rough_sketch() -> BubbleDetectionParams:
        return BubbleDetectionParams(min_solidity=0.60, max_texture_variance=120)


class BubbleDetector:
    def __init__(self, params: Optional[BubbleDetectionParams] = None):
        self.params = params or BubbleDetectionParams()

    def detect(self, image: np.ndarray) -> List[np.ndarray]:
        """Return list of binary masks, one per detected bubble."""
        p = self.params
        h, w = image.shape[:2]
        total_area = h * w

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        edges = cv2.Canny(blurred, p.canny_low, p.canny_high)
        combined = cv2.bitwise_or(binary, edges)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        masks = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < p.min_area_px or area > total_area * p.max_area_ratio:
                continue

            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < p.min_solidity:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / bh if bh > 0 else 0
            if not (p.aspect_ratio_min <= aspect <= p.aspect_ratio_max):
                continue

            # Texture check: low variance = smooth bubble interior
            roi = gray[y:y+bh, x:x+bw]
            if roi.size > 0 and float(roi.var()) > p.max_texture_variance:
                continue

            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
            # Erode to create safe inner zone
            kernel = np.ones((p.mask_erosion_px, p.mask_erosion_px), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            if mask.any():
                masks.append(mask)

        return masks


class BubbleExpander:
    def expand(
        self,
        box: RenderBox,
        bubble_mask: np.ndarray,
        max_expand_px: int = 20,
    ) -> RenderBox:
        """Expand box outward, clipped to bubble_mask safe zone."""
        h, w = bubble_mask.shape[:2]
        new_x = max(0, box.x - max_expand_px)
        new_y = max(0, box.y - max_expand_px)
        new_w = min(w - new_x, box.width + 2 * max_expand_px)
        new_h = min(h - new_y, box.height + 2 * max_expand_px)

        # Clip: check that expanded corners are inside mask
        corners = [
            (new_x, new_y), (new_x + new_w, new_y),
            (new_x, new_y + new_h), (new_x + new_w, new_y + new_h),
        ]
        for cx, cy in corners:
            cx = min(cx, w - 1)
            cy = min(cy, h - 1)
            if bubble_mask[cy, cx] == 0:
                # Corner outside mask — don't expand
                return box

        from copy import copy
        expanded = copy(box)
        expanded.x = new_x
        expanded.y = new_y
        expanded.width = new_w
        expanded.height = new_h
        expanded.expansion_applied = True
        return expanded
```

**Step 4: Run tests**

```bash
uv run pytest tests/rendering/test_bubble_expander.py -v
```
Expected: all 4 PASS

**Step 5: Commit**

```bash
git add modules/rendering/bubble_expander.py \
        tests/rendering/test_bubble_expander.py
git commit -m "feat: add bubble detector and bubble-aware text expander"
```


---

## Section 6 — Cross-Page Consistency: Comic Glossary & Story Context

### Task 6: Comic Glossary

**Files:**
- Create: `pipeline/comic_glossary.py`
- Create: `tests/pipeline/test_comic_glossary.py`

**Step 1: Write failing tests**

```python
# tests/pipeline/test_comic_glossary.py
import pytest
from pipeline.comic_glossary import ComicGlossary, GlossaryEntry, GlossaryCategory

def test_empty_glossary():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    assert g.get("Eren") is None

def test_add_and_retrieve_locked_entry():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    g.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, first_seen_page=1, locked=True)
    assert g.get("Eren") == "艾倫"

def test_locked_entry_not_overwritten():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    g.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, locked=True)
    g.add("Eren", "愛倫", GlossaryCategory.CHARACTER_NAME, locked=False)
    assert g.get("Eren") == "艾倫"

def test_enforce_glossary_replaces_violations():
    g = ComicGlossary(comic_id="test", source_lang="en", target_lang="zh-hk")
    g.add("Titan", "巨人", GlossaryCategory.STORY_TERM, locked=True)
    raw = "The Titan attacked the village."
    fixed = g.enforce("The 巨人 attacked the village.")
    assert "巨人" in fixed

def test_to_dict_and_from_dict_roundtrip():
    g = ComicGlossary(comic_id="c1", source_lang="en", target_lang="zh-hk")
    g.add("Mikasa", "三笠", GlossaryCategory.CHARACTER_NAME, locked=True)
    data = g.to_dict()
    g2 = ComicGlossary.from_dict(data)
    assert g2.get("Mikasa") == "三笠"

def test_locked_entries_list():
    g = ComicGlossary(comic_id="c1", source_lang="en", target_lang="zh-hk")
    g.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, locked=True)
    g.add("village", "村莊", GlossaryCategory.STORY_TERM, locked=False)
    locked = g.locked_entries()
    assert len(locked) == 1
    assert locked[0].source == "Eren"
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/pipeline/test_comic_glossary.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `pipeline/comic_glossary.py`**

```python
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class GlossaryCategory(str, Enum):
    CHARACTER_NAME = "character_name"
    FACTION_NAME = "faction_name"
    LOCATION_NAME = "location_name"
    STORY_TERM = "story_term"
    SFX = "sfx"
    TITLE_HONORIFIC = "title_honorific"

@dataclass
class GlossaryEntry:
    source: str
    translated: str
    category: GlossaryCategory
    first_seen_page: int = 1
    locked: bool = False
    notes: Optional[str] = None
    known_variants: List[str] = field(default_factory=list)

class ComicGlossary:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.version = 1
        self.last_updated = time.time()
        self._entries: Dict[str, GlossaryEntry] = {}

    def add(
        self,
        source: str,
        translated: str,
        category: GlossaryCategory,
        first_seen_page: int = 1,
        locked: bool = False,
        notes: Optional[str] = None,
    ) -> None:
        existing = self._entries.get(source)
        if existing and existing.locked:
            return  # locked entries are never overwritten
        self._entries[source] = GlossaryEntry(
            source=source,
            translated=translated,
            category=category,
            first_seen_page=first_seen_page,
            locked=locked,
            notes=notes,
        )
        self.last_updated = time.time()

    def get(self, source: str) -> Optional[str]:
        entry = self._entries.get(source)
        return entry.translated if entry else None

    def locked_entries(self) -> List[GlossaryEntry]:
        return [e for e in self._entries.values() if e.locked]

    def enforce(self, text: str) -> str:
        """Replace any glossary violations in translated text."""
        result = text
        for entry in self.locked_entries():
            for variant in entry.known_variants:
                result = result.replace(variant, entry.translated)
        return result

    def build_prompt_block(self) -> str:
        lines = [
            f'- "{e.source}" → "{e.translated}" ({e.category.value})'
            for e in self.locked_entries()
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "comic_id": self.comic_id,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "version": self.version,
            "last_updated": self.last_updated,
            "entries": {
                k: {
                    "source": e.source,
                    "translated": e.translated,
                    "category": e.category.value,
                    "first_seen_page": e.first_seen_page,
                    "locked": e.locked,
                    "notes": e.notes,
                    "known_variants": e.known_variants,
                }
                for k, e in self._entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComicGlossary":
        g = cls(data["comic_id"], data["source_lang"], data["target_lang"])
        g.version = data.get("version", 1)
        g.last_updated = data.get("last_updated", time.time())
        for k, v in data.get("entries", ).items():
            g._entries[k] = GlossaryEntry(
                source=v["source"],
                translated=v["translated"],
                category=GlossaryCategory(v["category"]),
                first_seen_page=v.get("first_seen_page", 1),
                locked=v.get("locked", False),
                notes=v.get("notes"),
                known_variants=v.get("known_variants", []),
            )
        return g
```

**Step 4: Run tests**

```bash
uv run pytest tests/pipeline/test_comic_glossary.py -v
```
Expected: all 6 PASS

**Step 5: Commit**

```bash
git add pipeline/comic_glossary.py tests/pipeline/test_comic_glossary.py
git commit -m "feat: add comic glossary with locked entries and enforcement"
```


### Task 7: Story Context Window

**Files:**
- Create: `pipeline/story_context.py`
- Create: `tests/pipeline/test_story_context.py`

**Step 1: Write failing tests**

```python
# tests/pipeline/test_story_context.py
import pytest
from pipeline.story_context import StoryContextWindow, PageSummary

def test_empty_window():
    w = StoryContextWindow(comic_id="c1")
    assert w.build_prompt_block() == ""

def test_add_and_retrieve_page():
    w = StoryContextWindow(comic_id="c1", max_pages=3)
    w.add_page(PageSummary(page_number=1, key_events="Hero arrives.", speakers_on_page=["Eren"], emotional_tone="tense"))
    block = w.build_prompt_block()
    assert "Page 1" in block
    assert "Hero arrives" in block

def test_rolling_window_drops_oldest():
    w = StoryContextWindow(comic_id="c1", max_pages=2)
    for i in range(1, 4):
        w.add_page(PageSummary(page_number=i, key_events=f"Event {i}.", speakers_on_page=[], emotional_tone="neutral"))
    block = w.build_prompt_block()
    assert "Page 1" not in block
    assert "Page 3" in block

def test_char_cap_respected():
    w = StoryContextWindow(comic_id="c1", max_pages=5, max_chars=50)
    w.add_page(PageSummary(page_number=1, key_events="A" * 200, speakers_on_page=[], emotional_tone="neutral"))
    block = w.build_prompt_block()
    assert len(block) <= 50
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/pipeline/test_story_context.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `pipeline/story_context.py`**

```python
from dataclasses import dataclass, field
from typing import List
from collections import deque

@dataclass
class PageSummary:
    page_number: int
    key_events: str
    speakers_on_page: List[str]
    emotional_tone: str

class StoryContextWindow:
    def __init__(self, comic_id: str, max_pages: int = 5, max_chars: int = 2000):
        self.comic_id = comic_id
        self.max_pages = max_pages
        self.max_chars = max_chars
        self._pages: deque = deque(maxlen=max_pages)

    def add_page(self, summary: PageSummary) -> None:
        self._pages.append(summary)

    def build_prompt_block(self) -> str:
        lines = [
            f"Page {p.page_number}: {p.key_events} [Tone: {p.emotional_tone}]"
            for p in list(self._pages)[-3:]
        ]
        result = "\n".join(lines)
        return result[:self.max_chars]

    def build_system_prompt(self, glossary_block: str, target_lang: str) -> str:
        context = self.build_prompt_block()
        parts = [f"You are translating a comic into {target_lang}."]
        if glossary_block:
            parts.append(f"\nLOCKED GLOSSARY — use these exactly:\n{glossary_block}")
        if context:
            parts.append(f"\nRECENT STORY CONTEXT:\n{context}")
        parts.append(
            "\nRULES:\n"
            "1. Preserve each character's consistent speech style.\n"
            "2. Never retranslate any term in the locked glossary.\n"
            "3. Keep SFX punchy and short.\n"
            "4. Return only the translated text, no explanation."
        )
        return "\n".join(parts)
```

**Step 4: Run tests**

```bash
uv run pytest tests/pipeline/test_story_context.py -v
```
Expected: all 4 PASS

**Step 5: Commit**

```bash
git add pipeline/story_context.py tests/pipeline/test_story_context.py
git commit -m "feat: add story context window with rolling page summaries"
```


### Task 8: Comic Session — Wire Glossary + Context into TranslationHandler

**Files:**
- Create: `pipeline/comic_session.py`
- Modify: `pipeline/translation_handler.py`
- Create: `tests/pipeline/test_comic_session.py`

**Step 1: Write failing tests**

```python
# tests/pipeline/test_comic_session.py
import pytest
from pipeline.comic_session import ComicSession
from pipeline.comic_glossary import GlossaryCategory

def test_session_creates_glossary_and_context():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    assert s.glossary is not None
    assert s.context is not None

def test_session_builds_system_prompt_with_glossary():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    s.glossary.add("Eren", "艾倫", GlossaryCategory.CHARACTER_NAME, locked=True)
    prompt = s.build_system_prompt()
    assert "艾倫" in prompt
    assert "zh-hk" in prompt

def test_session_enforces_glossary_on_output():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    s.glossary.add("Titan", "巨人", GlossaryCategory.STORY_TERM, locked=True)
    # Simulate API returning wrong term
    raw = "The Giant attacked."
    enforced = s.enforce_glossary(raw)
    # No known_variants set, so raw passes through unchanged
    assert enforced == raw

def test_session_serialise_roundtrip():
    s = ComicSession(comic_id="c1", source_lang="en", target_lang="zh-hk")
    s.glossary.add("Mikasa", "三笠", GlossaryCategory.CHARACTER_NAME, locked=True)
    data = s.to_dict()
    s2 = ComicSession.from_dict(data)
    assert s2.glossary.get("Mikasa") == "三笠"
    assert s2.comic_id == "c1"
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/pipeline/test_comic_session.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `pipeline/comic_session.py`**

```python
from pipeline.comic_glossary import ComicGlossary, GlossaryCategory
from pipeline.story_context import StoryContextWindow, PageSummary

class ComicSession:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.glossary = ComicGlossary(comic_id, source_lang, target_lang)
        self.context = StoryContextWindow(comic_id)

    def build_system_prompt(self) -> str:
        return self.context.build_system_prompt(
            glossary_block=self.glossary.build_prompt_block(),
            target_lang=self.target_lang,
        )

    def enforce_glossary(self, text: str) -> str:
        return self.glossary.enforce(text)

    def add_page_summary(self, summary: PageSummary) -> None:
        self.context.add_page(summary)

    def to_dict(self) -> dict:
        return {
            "comic_id": self.comic_id,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "glossary": self.glossary.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComicSession":
        s = cls(data["comic_id"], data["source_lang"], data["target_lang"])
        s.glossary = ComicGlossary.from_dict(data["glossary"])
        return s
```

**Step 4: Run tests**

```bash
uv run pytest tests/pipeline/test_comic_session.py -v
```
Expected: all 4 PASS

**Step 5: Commit**

```bash
git add pipeline/comic_session.py tests/pipeline/test_comic_session.py
git commit -m "feat: add ComicSession wiring glossary and story context together"
```


---

## Section 7 — Two-Pass Comic Processing Pipeline

### Task 9: Discovery Pass (OCR all pages, build glossary)

**Files:**
- Create: `pipeline/discovery_pass.py`
- Create: `tests/pipeline/test_discovery_pass.py`

**Step 1: Write failing tests**

```python
# tests/pipeline/test_discovery_pass.py
import pytest
from unittest.mock import MagicMock, patch
from pipeline.discovery_pass import DiscoveryPass

def _make_blk(text):
    blk = MagicMock()
    blk.text = text
    return blk

def test_accumulates_ocr_text():
    dp = DiscoveryPass(comic_id="c1", source_lang="en", target_lang="zh-hk")
    dp.add_page_ocr_results([_make_blk("Hello"), _make_blk("World")])
    dp.add_page_ocr_results([_make_blk("Eren attacked.")])
    text = dp.get_all_ocr_text()
    assert "Hello" in text
    assert "Eren attacked." in text

def test_discovery_prompt_built():
    dp = DiscoveryPass(comic_id="c1", source_lang="en", target_lang="zh-hk")
    dp.add_page_ocr_results([_make_blk("Eren ran.")])
    prompt = dp.build_discovery_prompt()
    assert "character names" in prompt.lower() or "proper noun" in prompt.lower()
    assert "Eren ran." in prompt

def test_apply_discovered_terms_to_glossary():
    dp = DiscoveryPass(comic_id="c1", source_lang="en", target_lang="zh-hk")
    from pipeline.comic_session import ComicSession
    session = ComicSession("c1", "en", "zh-hk")
    terms = [
        {"text": "Eren", "category": "character_name", "confidence": 0.95},
        {"text": "Titan", "category": "story_term", "confidence": 0.88},
    ]
    dp.apply_discovered_terms(session, terms)
    assert session.glossary.get("Eren") is not None
    assert session.glossary.get("Titan") is not None
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/pipeline/test_discovery_pass.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Create `pipeline/discovery_pass.py`**

```python
from typing import List, Any
from pipeline.comic_glossary import GlossaryCategory
from pipeline.comic_session import ComicSession

_CATEGORY_MAP = {
    "character_name": GlossaryCategory.CHARACTER_NAME,
    "faction_name": GlossaryCategory.FACTION_NAME,
    "location_name": GlossaryCategory.LOCATION_NAME,
    "story_term": GlossaryCategory.STORY_TERM,
    "sfx": GlossaryCategory.SFX,
    "title_honorific": GlossaryCategory.TITLE_HONORIFIC,
}

_DISCOVERY_PROMPT_TEMPLATE = """\
You are analyzing raw OCR text from a comic.
Identify ALL of the following without translating them:
- Character names
- Location names
- Organization/faction names
- Special terms, powers, or story-specific vocabulary
- Sound effects (SFX)

Return as JSON: {{"terms": [{{"text": "...", "category": "...", "confidence": 0.0}}]}}
Only return the JSON, no explanation.

OCR Text from all pages:
{all_ocr_text}
"""

class DiscoveryPass:
    def __init__(self, comic_id: str, source_lang: str, target_lang: str):
        self.comic_id = comic_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._page_texts: List[str] = []

    def add_page_ocr_results(self, blk_list: List[Any]) -> None:
        page_text = " ".join(blk.text for blk in blk_list if blk.text)
        self._page_texts.append(page_text)

    def get_all_ocr_text(self) -> str:
        return "\n".join(self._page_texts)

    def build_discovery_prompt(self) -> str:
        return _DISCOVERY_PROMPT_TEMPLATE.format(
            all_ocr_text=self.get_all_ocr_text()
        )

    def apply_discovered_terms(
        self,
        session: ComicSession,
        terms: List[dict],
        confidence_threshold: float = 0.7,
    ) -> None:
        """
        Apply LLM-discovered terms to the session glossary.
        Terms below confidence_threshold are added unlocked (can be overridden).
        """
        for term in terms:
            text = term.get("text", "").strip()
            category_str = term.get("category", "story_term")
            confidence = term.get("confidence", 0.0)
            if not text:
                continue
            category = _CATEGORY_MAP.get(category_str, GlossaryCategory.STORY_TERM)
            locked = confidence >= confidence_threshold
            # Source text is the term itself; translation is empty until confirmed
            session.glossary.add(
                source=text,
                translated=text,   # placeholder — human or Phase 2 fills this
                category=category,
                locked=locked,
            )
```

**Step 4: Run tests**

```bash
uv run pytest tests/pipeline/test_discovery_pass.py -v
```
Expected: all 3 PASS

**Step 5: Commit**

```bash
git add pipeline/discovery_pass.py tests/pipeline/test_discovery_pass.py
git commit -m "feat: add discovery pass for pre-scan glossary population"
```


---

## Section 8 — UI Bug: Post-Translation Text Colour Collision

### Task 10: Fix QTextEdit Cursor Format Contamination

**Files:**
- Modify: `app/ui/canvas/text_item.py`
- Create: `tests/ui/test_text_item_format.py`

**Step 1: Locate the translation insertion point in text_item.py**

Read `app/ui/canvas/text_item.py` and find any call to `insertHtml`, `setHtml`, or `insertText` that sets translated text. The bug is that after insertion the cursor inherits a rogue `background-color`.

**Step 2: Write failing test**

```python
# tests/ui/test_text_item_format.py
import pytest
# NOTE: PySide6 requires a QApplication to exist before creating widgets.
# Run with: uv run pytest tests/ui/test_text_item_format.py -v
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtCore import Qt

@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a

def test_insert_translation_leaves_clean_cursor_format(app):
    from app.ui.canvas.text_item import TextBlockItem
    item = TextBlockItem()
    item.set_plain_text("original text")

    # Simulate inserting a translation that might carry HTML background
    item.insert_translation("<p style='background-color:white'>翻譯文字</p>")

    fmt = item.document().defaultTextOption()
    cursor = item.textCursor()
    char_fmt = cursor.charFormat()
    bg = char_fmt.background().color()
    # Background must be transparent (alpha=0) or invalid — not white
    assert bg.alpha() == 0 or not bg.isValid(), \
        f"Cursor has rogue background: {bg.name()}"
```

**Step 3: Run to verify failure**

```bash
uv run pytest tests/ui/test_text_item_format.py -v
```
Expected: `AttributeError: 'TextBlockItem' object has no attribute 'insert_translation'`

**Step 4: Add `insert_translation` method to `TextBlockItem`**

In `app/ui/canvas/text_item.py`, add this method to the `TextBlockItem` class:

```python
import re as _re

def insert_translation(self, raw_translated: str) -> None:
    """
    Safely insert translated text.
    - Strips HTML from API response
    - Inserts as plain text with explicit clean format
    - Resets cursor format so next typed chars are clean
    """
    from PySide6.QtGui import QTextCharFormat, QColor
    from PySide6.QtCore import Qt

    # Step 1: strip any HTML the API may have returned
    plain_text = _re.sub(r'<[^>]+>', '', raw_translated).strip()

    # Step 2: build explicit clean format — no background colour
    fmt = QTextCharFormat()
    fmt.setForeground(self.text_color)
    fmt.setBackground(Qt.GlobalColor.transparent)
    if self.font_family:
        from PySide6.QtGui import QFont
        font = QFont(self.font_family, int(self.font_size))
        font.setBold(self.bold)
        font.setItalic(self.italic)
        font.setUnderline(self.underline)
        fmt.setFont(font)

    # Step 3: insert at current cursor with clean format
    cursor = self.textCursor()
    cursor.select(cursor.SelectionType.Document)
    cursor.insertText(plain_text, fmt)

    # Step 4: reset typing format so next keystroke is also clean
    self.setTextCursor(cursor)
    self.setCurrentCharFormat(fmt)
```

**Step 5: Run test**

```bash
uv run pytest tests/ui/test_text_item_format.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add app/ui/canvas/text_item.py tests/ui/test_text_item_format.py tests/ui/__init__.py
git commit -m "fix: add insert_translation to prevent cursor background-color contamination"
```


---

## Section 9 — Integration: Wire All Modules into the Pipeline

### Task 11: Integrate Cache v2 into CacheManager

**Files:**
- Modify: `pipeline/cache_manager.py`

**Step 1: Read current cache_manager.py translation_cache structure**

The current `translation_cache` is a plain dict keyed by `(image_hash, translator_key, source_lang, target_lang, context_hash)` → `{block_id: {'source_text': str, 'translation': str}}`.

**Step 2: Add v2 cache alongside existing cache (non-breaking)**

In `pipeline/cache_manager.py`, in `CacheManager.__init__`, add:

```python
from pipeline.cache_v2 import TranslationCacheV2
self.translation_cache_v2 = TranslationCacheV2()
```

**Step 3: In `_cache_translation_results`, also write to v2**

Find `_cache_translation_results` in `pipeline/cache_manager.py` (around the block that stores `{block_id: {'source_text': ..., 'translation': ...}}`). After the existing store, add:

```python
# Also write to v2 cache
for blk in (processed_blk_list or blk_list):
    if blk.text and blk.translation:
        self.translation_cache_v2.store(
            src=blk.source_lang,
            tgt=blk.target_lang,
            source_text=blk.text,
            translated_text=blk.translation,
        )
```

**Step 4: In `_get_cached_translation_for_block`, try v2 first**

At the top of `_get_cached_translation_for_block`, before the existing lookup:

```python
# Try v2 cache first
v2_result = self.translation_cache_v2.get(
    block.source_lang, block.target_lang, block.text
)
if v2_result is not None:
    return v2_result
```

**Step 5: Run existing app to verify no regression**

```bash
uv run python -c "from pipeline.cache_manager import CacheManager; c = CacheManager(); print('OK')"
```
Expected: `OK`

**Step 6: Commit**

```bash
git add pipeline/cache_manager.py
git commit -m "feat: integrate cache v2 alongside existing CacheManager"
```

---

### Task 12: Integrate OCR Noise Filter into OCRHandler

**Files:**
- Modify: `pipeline/ocr_handler.py`

**Step 1: Read `pipeline/ocr_handler.py`**

Find the section in `OCR_image` where `blk_list` is populated after `self.ocr_processor.process(img, blk_list)`.

**Step 2: Add noise filter after OCR, before cache write**

In `OCRHandler.__init__`, add:

```python
from modules.ocr.noise_filter import OCRNoiseFilter
self._noise_filter = OCRNoiseFilter()
```

After `self.ocr_processor.process(img, blk_list)` in both `OCR_image` and `OCR_webtoon_visible_area`, add:

```python
for blk in blk_list:
    if blk.text:
        blk.text, _ = self._noise_filter.filter_block_text(blk.text)
        # Keep texts list in sync
        if blk.texts:
            blk.texts = [self._noise_filter.filter_text(t) for t in blk.texts]
```

**Step 3: Verify import works**

```bash
uv run python -c "from pipeline.ocr_handler import OCRHandler; print('OK')"
```
Expected: `OK`

**Step 4: Commit**

```bash
git add pipeline/ocr_handler.py
git commit -m "feat: wire OCR noise filter into OCRHandler"
```

---

### Task 13: Integrate ComicSession into TranslationHandler

**Files:**
- Modify: `pipeline/translation_handler.py`

**Step 1: Read `pipeline/translation_handler.py`**

Find `translate_image` — specifically where `self.translator.translate(blk_list, image, extra_context)` is called and where the system prompt / extra_context is built.

**Step 2: Add ComicSession as optional attribute**

In `TranslationHandler.__init__`, add:

```python
self.comic_session = None  # Set externally before batch processing
```

**Step 3: Inject glossary + context into extra_context**

In `translate_image`, before calling `self.translator.translate(...)`, add:

```python
if self.comic_session is not None:
    system_prompt = self.comic_session.build_system_prompt()
    # Append to existing extra_context
    extra_context = f"{extra_context}\n{system_prompt}".strip()
```

**Step 4: Enforce glossary on translated output**

After `self.translator.translate(blk_list, image, extra_context)`, add:

```python
if self.comic_session is not None:
    for blk in blk_list:
        if blk.translation:
            blk.translation = self.comic_session.enforce_glossary(blk.translation)
```

**Step 5: Verify import works**

```bash
uv run python -c "from pipeline.translation_handler import TranslationHandler; print('OK')"
```
Expected: `OK`

**Step 6: Commit**

```bash
git add pipeline/translation_handler.py
git commit -m "feat: inject ComicSession glossary and context into TranslationHandler"
```

---

### Task 14: Add Discovery Pass to BatchProcessor

**Files:**
- Modify: `pipeline/batch_processor.py`

**Step 1: Read `pipeline/batch_processor.py`**

Find `batch_process` — the main loop that iterates over `selected_paths`. Identify where OCR results are available (after `ocr_handler.OCR_image()`).

**Step 2: Add Pass 1 (discovery) before Pass 2 (translation)**

In `BatchProcessor.__init__`, add:

```python
from pipeline.discovery_pass import DiscoveryPass
from pipeline.comic_session import ComicSession
self.comic_session = None
```

In `batch_process`, before the main processing loop, add a discovery pre-pass:

```python
# Pass 1: OCR all pages and build glossary
source_lang = self.main_page.settings_page.get_language()
target_lang = self.main_page.settings_page.get_language()  # target from settings
comic_id = "batch_" + str(int(time.time()))
discovery = DiscoveryPass(comic_id, source_lang, target_lang)
self.comic_session = ComicSession(comic_id, source_lang, target_lang)
# Wire session into translation handler
self.main_page.pipeline.translation_handler.comic_session = self.comic_session
```

**Step 3: Accumulate OCR results during discovery pass**

After each page's OCR in the main loop, add:

```python
if hasattr(self, 'comic_session') and self.comic_session:
    discovery.add_page_ocr_results(blk_list)
```

**Step 4: Verify import works**

```bash
uv run python -c "from pipeline.batch_processor import BatchProcessor; print('OK')"
```
Expected: `OK`

**Step 5: Commit**

```bash
git add pipeline/batch_processor.py
git commit -m "feat: add discovery pass pre-scan to BatchProcessor"
```

---

### Task 15: Run Full Test Suite

**Step 1: Create `tests/__init__.py` and subdirectory inits if missing**

```bash
touch tests/__init__.py tests/ocr/__init__.py tests/pipeline/__init__.py \
      tests/rendering/__init__.py tests/translation/__init__.py tests/ui/__init__.py
```

**Step 2: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```
Expected: all tests PASS (Tasks 1–10 tests = ~26 tests total)

**Step 3: Fix any failures before proceeding**

If any test fails, read the error, fix the minimal code, re-run.

**Step 4: Final commit**

```bash
git add tests/
git commit -m "test: add test suite init files for all test packages"
```

---

## Open Issues (from manga_translation_system_plan.md §9)

These are tracked but not implemented in this plan — address in follow-up:

| Issue | Priority | Follow-up task |
|-------|----------|----------------|
| Glossary discovery prompt quality tuning | High | Test across genres, reduce false positives |
| Context window token budget for free models | High | Cap context block at 500 chars for free-tier |
| Page summary generation (LLM call per page) | Medium | Add `generate_page_summary()` to `ComicSession` |
| Bubble detection fallback when no contour found | High | Use full OCR bounding box as default in `BubbleExpander` |
| Cache persistence to disk (JSON/SQLite) | Medium | Add `save(path)` / `load(path)` to `TranslationCacheV2` |
| Manual review UI for `needs_review` boxes | Medium | Surface `collision_resolved.needs_review` in canvas |
| Art style profile auto-detection | Low | Use image variance stats to pick `ArtStyleProfile` |

