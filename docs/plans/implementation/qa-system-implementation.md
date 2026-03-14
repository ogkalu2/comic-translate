# Phase 1 Implementation Plan — QA System (JSON Backend)

> For Claude: REQUIRED SUB-SKILL: Use **superpowers:executing-plans** to implement this plan task-by-task.

## 🎯 Goal

Implement a minimal QA system with a **JSON backend** and **OpenAI provider**. No GUI, no upstream integration yet.

## 🏗️ Architecture

A pure library implementation following interfaces defined in `architecture/qa-system-design.md`.

**Tech stack:** Python 3.12, dataclasses, ABC, `json` (stdlib), OpenAI SDK.

---

## ✅ Prerequisites

- Python 3.12 installed
- `uv` package manager
- OpenAI API key (for testing)

---

## Task 1: Setup New Repo Structure

### 🔧 Files to create

- `pyproject.toml` (workspace root)
- `packages/core/pyproject.toml`
- `packages/qa/pyproject.toml`

### 1) Create workspace root

```bash
mkdir -p comic-translate-new
cd comic-translate-new
```

Create `pyproject.toml`:

```toml
[project]
name = "comic-translate-workspace"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
comic-translate-core = { workspace = true }
comic-translate-qa = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
  "packages/core/src",
  "packages/qa/src",
]

[tool.ruff]
target-version = "py312"
line-length = 100
```

### 2) Create core package structure

```bash
mkdir -p packages/core/src/comic_translate_core/{models,interfaces,pipeline,storage,fingerprint}
```

Create empty `__init__.py` files:

```bash
touch packages/core/src/comic_translate_core/__init__.py
for dir in models interfaces pipeline storage fingerprint; do
  touch packages/core/src/comic_translate_core/$dir/__init__.py
done
```

Create `packages/core/pyproject.toml`:

```toml
[project]
name = "comic-translate-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 3) Create QA package structure

```bash
mkdir -p packages/qa/src/comic_translate_qa/{chunking,providers,applicator}
```

Create empty `__init__.py` files:

```bash
touch packages/qa/src/comic_translate_qa/__init__.py
for dir in chunking providers applicator; do
  touch packages/qa/src/comic_translate_qa/$dir/__init__.py
done
```

Create `packages/qa/pyproject.toml`:

```toml
[project]
name = "comic-translate-qa"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "comic-translate-core>=0.1.0",
]

[project.optional-dependencies]
openai = ["openai>=1.0"]
dev = ["pytest>=8.0", "ruff>=0.4"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 4) Initialize workspace

```bash
uv sync --all-packages
```

### 5) Verify structure

```bash
tree -L 4 packages/
```

Expected:

```
packages/
├── core
│   ├── pyproject.toml
│   └── src
│       └── comic_translate_core
│           ├── __init__.py
│           ├── models/
│           ├── interfaces/
│           ├── pipeline/
│           ├── storage/
│           └── fingerprint/
└── qa
    ├── pyproject.toml
    └── src
        └── comic_translate_qa
            ├── __init__.py
            ├── chunking/
            ├── providers/
            └── applicator/
```

---

## Task 2: Implement Core Data Models

### Files

- `packages/core/src/comic_translate_core/models/block.py`
- `packages/core/src/comic_translate_core/models/script.py`
- `packages/core/src/comic_translate_core/models/patch.py`
- `packages/core/src/comic_translate_core/models/chunk.py`

### 1) `block.py`

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class BlockType(str, Enum):
    DIALOGUE = "dialogue"
    NARRATION = "narration"
    SFX = "sfx"
    CREDIT = "credit"


@dataclass
class BlockContext:
    speaker: Optional[str] = None
    prev_block: Optional[str] = None
    next_block: Optional[str] = None


@dataclass
class ScriptBlock:
    block_id: str
    page: int
    type: BlockType
    bbox: List[int]
    original: str
    translated: str
    original_variant: str
    context: BlockContext
    qa_metadata: Optional[dict] = None
```

### 2) `script.py`

```python
from dataclasses import dataclass
from typing import Dict, List

from .block import ScriptBlock


@dataclass
class ScriptExport:
    version: str
    comic_id: str
    base_fp: str
    script_id: str
    source_lang: str
    target_lang: str
    exported_at: float
    page_range: List[int]
    active_variant: str
    variants: Dict[str, Dict]
    glossary_snapshot: Dict[str, Dict]
    blocks: List[ScriptBlock]
```

### 3) `patch.py`

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class PatchCategory(str, Enum):
    GLOSSARY_CONSISTENCY = "glossary_consistency"
    TONE = "tone"
    GRAMMAR = "grammar"
    STYLE = "style"
    LOCALIZATION = "localization"


@dataclass
class QAPatch:
    block_id: str
    original: str
    old_translated: str
    new_translated: str
    reason: str
    category: PatchCategory
    confidence: float


@dataclass
class QAPatchSet:
    version: str
    comic_id: str
    base_fp: str
    created_at: float
    qa_model: str
    chunk_range: Dict[str, str]
    summary: Dict
    patches: List[QAPatch]
```

### 4) `chunk.py`

```python
from dataclasses import dataclass
from typing import Dict, List

from .block import ScriptBlock


@dataclass
class QAChunk:
    chunk_id: int
    comic_id: str
    base_fp: str
    source_lang: str
    target_lang: str
    glossary_snapshot: Dict[str, Dict]
    context_blocks: List[ScriptBlock]
    blocks: List[ScriptBlock]
```

### 5) Update `models/__init__.py`

```python
from .block import BlockType, BlockContext, ScriptBlock
from .script import ScriptExport
from .patch import PatchCategory, QAPatch, QAPatchSet
from .chunk import QAChunk

__all__ = [
    "BlockType",
    "BlockContext",
    "ScriptBlock",
    "ScriptExport",
    "PatchCategory",
    "QAPatch",
    "QAPatchSet",
    "QAChunk",
]
```

### 6) Run tests

```bash
uv run pytest tests/unit/test_core/test_models.py -v
```

---

## Task 3: Implement Core Interfaces

### Files

- `packages/core/src/comic_translate_core/interfaces/storage.py`
- `packages/core/src/comic_translate_core/interfaces/exporter.py`
- `packages/core/src/comic_translate_core/interfaces/chunking.py`
- `packages/core/src/comic_translate_core/interfaces/llm_provider.py`
- `packages/core/src/comic_translate_core/interfaces/applicator.py`

### 1) `storage.py`

```python
from abc import ABC, abstractmethod

from ..models import ScriptExport, QAPatchSet


class IScriptStorage(ABC):

    @abstractmethod
    def save_script(self, script: ScriptExport, path: str) -> None:
        ...

    @abstractmethod
    def load_script(self, path: str) -> ScriptExport:
        ...

    @abstractmethod
    def save_patch(self, patch_set: QAPatchSet, path: str) -> None:
        ...

    @abstractmethod
    def load_patch(self, path: str) -> QAPatchSet:
        ...
```

### 2) `exporter.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, List

from ..models import ScriptExport


class IScriptExporter(ABC):

    @abstractmethod
    def export(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        ...
```

### 3) `chunking.py`

```python
from abc import ABC, abstractmethod
from typing import Iterator

from ..models import ScriptExport, QAChunk


class IChunkingStrategy(ABC):

    @abstractmethod
    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]:
        ...
```

### 4) `llm_provider.py`

```python
from abc import ABC, abstractmethod
from typing import List

from ..models import QAChunk, QAPatch


class ILLMProvider(ABC):

    @abstractmethod
    def review_chunk(
        self,
        chunk: QAChunk,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> List[QAPatch]:
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        ...
```

### 5) `applicator.py`

```python
from abc import ABC, abstractmethod
from typing import Dict

from ..models import QAPatchSet


class IPatchApplicator(ABC):

    @abstractmethod
    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        ...
```

### 6) Update `interfaces/__init__.py`

```python
from .storage import IScriptStorage
from .exporter import IScriptExporter
from .chunking import IChunkingStrategy
from .llm_provider import ILLMProvider
from .applicator import IPatchApplicator

__all__ = [
    "IScriptStorage",
    "IScriptExporter",
    "IChunkingStrategy",
    "ILLMProvider",
    "IPatchApplicator",
]
```

---

## Task 4: Implement JsonFileStorage

### File: `packages/core/src/comic_translate_core/storage/json_file.py`

```python
import json
from pathlib import Path

from ..interfaces import IScriptStorage
from ..models import (
    ScriptExport,
    QAPatchSet,
    ScriptBlock,
    BlockContext,
    BlockType,
    QAPatch,
    PatchCategory,
)


class JsonFileStorage(IScriptStorage):

    def save_script(self, script: ScriptExport, path: str) -> None:
        data = self._script_to_dict(script)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_script(self, path: str) -> ScriptExport:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._dict_to_script(data)

    def save_patch(self, patch_set: QAPatchSet, path: str) -> None:
        data = self._patch_set_to_dict(patch_set)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_patch(self, path: str) -> QAPatchSet:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._dict_to_patch_set(data)

    @staticmethod
    def _script_to_dict(script: ScriptExport) -> dict:
        return {
            "version": script.version,
            "comic_id": script.comic_id,
            "base_fp": script.base_fp,
            "script_id": script.script_id,
            "source_lang": script.source_lang,
            "target_lang": script.target_lang,
            "exported_at": script.exported_at,
            "page_range": script.page_range,
            "active_variant": script.active_variant,
            "variants": script.variants,
            "glossary_snapshot": script.glossary_snapshot,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "page": b.page,
                    "type": b.type.value,
                    "bbox": b.bbox,
                    "original": b.original,
                    "translated": b.translated,
                    "original_variant": b.original_variant,
                    "context": {
                        "speaker": b.context.speaker,
                        "prev_block": b.context.prev_block,
                        "next_block": b.context.next_block,
                    },
                    "qa_metadata": b.qa_metadata,
                }
                for b in script.blocks
            ],
        }

    @staticmethod
    def _dict_to_script(data: dict) -> ScriptExport:
        return ScriptExport(
            version=data["version"],
            comic_id=data["comic_id"],
            base_fp=data["base_fp"],
            script_id=data["script_id"],
            source_lang=data["source_lang"],
            target_lang=data["target_lang"],
            exported_at=data["exported_at"],
            page_range=data["page_range"],
            active_variant=data["active_variant"],
            variants=data["variants"],
            glossary_snapshot=data["glossary_snapshot"],
            blocks=[
                ScriptBlock(
                    block_id=b["block_id"],
                    page=b["page"],
                    type=BlockType(b["type"]),
                    bbox=b["bbox"],
                    original=b["original"],
                    translated=b["translated"],
                    original_variant=b["original_variant"],
                    context=BlockContext(**b["context"]),
                    qa_metadata=b.get("qa_metadata"),
                )
                for b in data["blocks"]
            ],
        )

    @staticmethod
    def _patch_set_to_dict(patch_set: QAPatchSet) -> dict:
        return {
            "version": patch_set.version,
            "comic_id": patch_set.comic_id,
            "base_fp": patch_set.base_fp,
            "created_at": patch_set.created_at,
            "qa_model": patch_set.qa_model,
            "chunk_range": patch_set.chunk_range,
            "summary": patch_set.summary,
            "patches": [
                {
                    "block_id": p.block_id,
                    "original": p.original,
                    "old_translated": p.old_translated,
                    "new_translated": p.new_translated,
                    "reason": p.reason,
                    "category": p.category.value,
                    "confidence": p.confidence,
                }
                for p in patch_set.patches
            ],
        }

    @staticmethod
    def _dict_to_patch_set(data: dict) -> QAPatchSet:
        return QAPatchSet(
            version=data["version"],
            comic_id=data["comic_id"],
            base_fp=data["base_fp"],
            created_at=data["created_at"],
            qa_model=data["qa_model"],
            chunk_range=data["chunk_range"],
            summary=data["summary"],
            patches=[
                QAPatch(
                    block_id=p["block_id"],
                    original=p["original"],
                    old_translated=p["old_translated"],
                    new_translated=p["new_translated"],
                    reason=p["reason"],
                    category=PatchCategory(p["category"]),
                    confidence=p["confidence"],
                )
                for p in data["patches"]
            ],
        )
```

### Update `storage/__init__.py`

```python
from .json_file import JsonFileStorage

__all__ = ["JsonFileStorage"]
```

### Test

```bash
uv run pytest tests/unit/test_core/test_json_storage.py -v
```

---

## Task 5: Implement PageBasedChunking

### File: `packages/qa/src/comic_translate_qa/chunking/page_based.py`

```python
from typing import Iterator

from comic_translate_core.interfaces import IChunkingStrategy
from comic_translate_core.models import ScriptExport, QAChunk, BlockType


class PageBasedChunking(IChunkingStrategy):
    """Cut chunks on page boundaries.

    - Skip SFX/credit blocks (configurable)
    - Overlap last N blocks from previous chunk as read-only context
    """

    SKIP_TYPES = {BlockType.SFX, BlockType.CREDIT}

    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]:
        reviewable = [b for b in script.blocks if b.type not in self.SKIP_TYPES]

        i = 0
        chunk_id = 0
        while i < len(reviewable):
            chunk_blocks = reviewable[i : i + chunk_size]
            context_blocks = reviewable[max(0, i - overlap) : i] if i > 0 else []

            yield QAChunk(
                chunk_id=chunk_id,
                comic_id=script.comic_id,
                base_fp=script.base_fp,
                source_lang=script.source_lang,
                target_lang=script.target_lang,
                glossary_snapshot=script.glossary_snapshot,
                context_blocks=context_blocks,
                blocks=chunk_blocks,
            )

            i += chunk_size
            chunk_id += 1
```

### Update `chunking/__init__.py`

```python
from .page_based import PageBasedChunking

__all__ = ["PageBasedChunking"]
```

### Test

```bash
uv run pytest tests/unit/test_qa/test_chunking.py -v
```

---

## Task 6: Implement OpenAI QA Provider

### File: `packages/qa/src/comic_translate_qa/providers/openai_provider.py`

````python
import json
from typing import List

from comic_translate_core.interfaces import ILLMProvider
from comic_translate_core.models import QAChunk, QAPatch, PatchCategory


try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI provider requires: pip install openai")


QA_PROMPT_TEMPLATE = """\
You are a professional comic translator QA reviewer.

## Context

- Source: {source_lang} → Target: {target_lang}
- Comic: {comic_id}

## Locked Glossary (use these translations exactly)

{glossary_block}

## Previous Context (do NOT patch these)

{context_blocks_text}

## Blocks to Review

{blocks_to_review}

## Review Categories (priority order)

1. glossary_consistency — violates locked glossary terms
2. tone — unnatural, wrong register, doesn't match character voice
3. grammar — errors, awkward phrasing, machine translation artifacts

## Target Language Notes

- zh-HK: natural Hong Kong written style (書面語 with 口語 flavor)
- yue: pure Cantonese colloquial (純粵語口語)

## Rules

- Only patch blocks with clear issues (confidence >= 0.7)
- Preserve character personality and speech patterns
- If a translation is already good, skip it

## Output

Return ONLY a JSON array:
[
  {"block_id": "...", "original": "...", "old_translated": "...", "new_translated": "...",
   "reason": "...", "category": "glossary_consistency|tone|grammar", "confidence": 0.0}
]

If no issues: []
"""


class OpenAIQAProvider(ILLMProvider):

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def review_chunk(
        self,
        chunk: QAChunk,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> List[QAPatch]:
        prompt = self._build_prompt(chunk)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content.strip()
        return self._parse_response(content)

    def get_model_name(self) -> str:
        return self.model

    @staticmethod
    def _build_prompt(chunk: QAChunk) -> str:
        glossary_lines = [
            f'- "{src}" → "{entry["translated"]}" ({entry["category"]})'
            for src, entry in chunk.glossary_snapshot.items()
            if entry.get("locked", False)
        ]
        glossary_block = "\n".join(glossary_lines) if glossary_lines else "(No locked terms)"

        context_lines = [
            f'[{b.block_id}] {b.original} → {b.translated}'
            for b in chunk.context_blocks
        ]
        context_blocks_text = "\n".join(context_lines) if context_lines else "(No previous context)"

        review_lines = []
        for b in chunk.blocks:
            speaker = b.context.speaker or ""
            speaker_tag = f" (Speaker: {speaker})" if speaker else ""
            review_lines.append(
                f'[{b.block_id}] Type: {b.type.value}{speaker_tag}\n'
                f'  Original: {b.original}\n'
                f'  Translated: {b.translated}'
            )
        blocks_to_review = "\n\n".join(review_lines)

        return QA_PROMPT_TEMPLATE.format(
            source_lang=chunk.source_lang,
            target_lang=chunk.target_lang,
            comic_id=chunk.comic_id,
            glossary_block=glossary_block,
            context_blocks_text=context_blocks_text,
            blocks_to_review=blocks_to_review,
        )

    @staticmethod
    def _parse_response(content: str) -> List[QAPatch]:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        if not content or content == "[]":
            return []

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nContent: {content}")

        patches: List[QAPatch] = []
        for item in data:
            patches.append(
                QAPatch(
                    block_id=item["block_id"],
                    original=item["original"],
                    old_translated=item["old_translated"],
                    new_translated=item["new_translated"],
                    reason=item["reason"],
                    category=PatchCategory(item["category"]),
                    confidence=item["confidence"],
                )
            )

        return patches
````

### Update `providers/__init__.py`

```python
from .openai_provider import OpenAIQAProvider

__all__ = ["OpenAIQAProvider"]
```

### Test

```bash
uv run pytest tests/unit/test_qa/test_openai_provider.py -v
```

---

## Task 7: Implement NoopApplicator

### File: `packages/qa/src/comic_translate_qa/applicator/noop.py`

```python
from typing import Dict

from comic_translate_core.interfaces import IPatchApplicator
from comic_translate_core.models import QAPatchSet


class NoopApplicator(IPatchApplicator):
    """Dry-run applicator that only prints stats.

    Does not modify any source data.
    """

    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        total = len(patch_set.patches)
        applied = sum(1 for p in patch_set.patches if p.confidence >= confidence_threshold)
        skipped = total - applied

        details = []
        for patch in patch_set.patches:
            action = "would_apply" if patch.confidence >= confidence_threshold else "skipped"
            details.append({
                "block_id": patch.block_id,
                "action": action,
                "category": patch.category.value,
                "confidence": patch.confidence,
                "reason": patch.reason,
            })

        return {
            "total": total,
            "applied": applied,
            "skipped": skipped,
            "failed": 0,
            "details": details,
        }
```

### Update `applicator/__init__.py`

```python
from .noop import NoopApplicator

__all__ = ["NoopApplicator"]
```

### Test

```bash
uv run pytest tests/unit/test_qa/test_applicator.py -v
```

---

## Task 8: Implement QAOrchestrator

### File: `packages/core/src/comic_translate_core/pipeline/qa_orchestrator.py`

```python
import time
from collections import Counter
from typing import Dict, List, Optional

from ..interfaces import (
    IChunkingStrategy,
    ILLMProvider,
    IPatchApplicator,
    IScriptExporter,
    IScriptStorage,
)
from ..models import QAPatch, QAPatchSet, ScriptExport


class QAOrchestrator:
    """Coordinates export → chunk → QA → patch → apply.

    Uses dependency injection for all strategies.
    """

    def __init__(
        self,
        exporter: IScriptExporter,
        storage: IScriptStorage,
        chunking: IChunkingStrategy,
        llm_provider: ILLMProvider,
        applicator: IPatchApplicator,
    ):
        self.exporter = exporter
        self.storage = storage
        self.chunking = chunking
        self.llm_provider = llm_provider
        self.applicator = applicator

    def export_script(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        output_path: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        """Export comic to script JSON."""
        script = self.exporter.export(
            comic_id, base_fp, source_lang, target_lang, page_range, variant
        )
        self.storage.save_script(script, output_path)
        return script

    def qa_script(
        self,
        script_path: str,
        output_patch_path: str,
        chunk_size: int = 80,
        overlap: int = 5,
        temperature: float = 0.3,
    ) -> QAPatchSet:
        """Run QA on script and generate patch set."""
        script = self.storage.load_script(script_path)
        all_patches: List[QAPatch] = []
        total_blocks_reviewed = 0

        for chunk in self.chunking.chunk(script, chunk_size, overlap):
            patches = self.llm_provider.review_chunk(chunk, temperature)
            all_patches.extend(patches)
            total_blocks_reviewed += len(chunk.blocks)

        first_id = script.blocks[0].block_id if script.blocks else ""
        last_id = script.blocks[-1].block_id if script.blocks else ""

        patch_set = QAPatchSet(
            version="1.0",
            comic_id=script.comic_id,
            base_fp=script.base_fp,
            created_at=time.time(),
            qa_model=self.llm_provider.get_model_name(),
            chunk_range={"from": first_id, "to": last_id},
            summary=self._build_summary(all_patches, total_blocks_reviewed),
            patches=all_patches,
        )

        self.storage.save_patch(patch_set, output_patch_path)
        return patch_set

    def apply_patches(
        self,
        patch_path: str,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict:
        """Apply patches from file."""
        patch_set = self.storage.load_patch(patch_path)
        return self.applicator.apply_patches(patch_set, dry_run, confidence_threshold)

    @staticmethod
    def _build_summary(patches: List[QAPatch], total_reviewed: int) -> Dict:
        """Build summary stats from patches."""
        categories = Counter(p.category.value for p in patches)
        return {
            "total_reviewed": total_reviewed,
            "total_patched": len(patches),
            "categories": dict(categories),
        }
```

### Update `pipeline/__init__.py`

```python
from .qa_orchestrator import QAOrchestrator

__all__ = ["QAOrchestrator"]
```

### Test

```bash
uv run pytest tests/integration/test_qa_orchestrator.py -v
```

---

## Task 9: Create MockExporter for Testing

### File: `packages/core/src/comic_translate_core/storage/mock_exporter.py`

```python
import time
from typing import List, Optional

from ..interfaces import IScriptExporter
from ..models import BlockContext, BlockType, ScriptBlock, ScriptExport


class MockExporter(IScriptExporter):
    """Mock exporter that generates test data.

    Useful for testing QA system without real comic data.
    """

    def export(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport:
        page_range = page_range or [1, 3]

        blocks = []
        for page in range(page_range[0], page_range[1] + 1):
            for i in range(3):
                block_id = f"p{page}_b{i}"
                blocks.append(
                    ScriptBlock(
                        block_id=block_id,
                        page=page,
                        type=BlockType.DIALOGUE,
                        bbox=[100 + i * 50, 100, 200 + i * 50, 150],
                        original=f"Original text {block_id}",
                        translated=f"Translated text {block_id}",
                        original_variant=variant,
                        context=BlockContext(
                            speaker="Character A" if i % 2 == 0 else "Character B",
                            prev_block=f"p{page}_b{i-1}" if i > 0 else None,
                            next_block=f"p{page}_b{i+1}" if i < 2 else None,
                        ),
                    )
                )

        return ScriptExport(
            version="1.0",
            comic_id=comic_id,
            base_fp=base_fp,
            script_id=f"{comic_id}:{base_fp}:{target_lang}",
            source_lang=source_lang,
            target_lang=target_lang,
            exported_at=time.time(),
            page_range=page_range,
            active_variant=variant,
            variants={variant: {"censored": False, "source": "test"}},
            glossary_snapshot={
                "Character A": {
                    "translated": "角色A",
                    "category": "character_name",
                    "locked": True,
                }
            },
            blocks=blocks,
        )
```

### Update `storage/__init__.py`

```python
from .json_file import JsonFileStorage
from .mock_exporter import MockExporter

__all__ = ["JsonFileStorage", "MockExporter"]
```

---

## Task 10: Write Integration Test

### File: `tests/integration/test_qa_full_flow.py`

```python
import tempfile
from pathlib import Path

from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from comic_translate_qa.applicator import NoopApplicator
from comic_translate_qa.chunking import PageBasedChunking
from comic_translate_qa.providers import OpenAIQAProvider


def test_full_qa_flow():
    """Test complete QA flow: export → qa → apply"""

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "script.json"
        patch_path = Path(tmpdir) / "patches.json"

        orchestrator = QAOrchestrator(
            exporter=MockExporter(),
            storage=JsonFileStorage(),
            chunking=PageBasedChunking(),
            llm_provider=OpenAIQAProvider(api_key="test-key"),  # Mock in real test
            applicator=NoopApplicator(),
        )

        script = orchestrator.export_script(
            comic_id="test_comic",
            base_fp="test_fp",
            source_lang="ja",
            target_lang="zh-hk",
            output_path=str(script_path),
        )

        assert script_path.exists()
        assert len(script.blocks) == 9  # 3 pages × 3 blocks

        # Step 2: QA (skip in test, requires real API key)
        # patch_set = orchestrator.qa_script(
        #     script_path=str(script_path),
        #     output_patch_path=str(patch_path),
        # )

        # Step 3: Apply (skip, depends on step 2)
        # result = orchestrator.apply_patches(patch_path=str(patch_path))
        # assert result["total"] >= 0
```

---

## Task 11: Create CLI Wrapper (Optional)

### File: `packages/qa/src/comic_translate_qa/cli.py`

```python
import click

from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from comic_translate_qa.applicator import NoopApplicator
from comic_translate_qa.chunking import PageBasedChunking
from comic_translate_qa.providers import OpenAIQAProvider


@click.group()
def cli():
    """Comic Translate QA CLI"""
    pass


@cli.command()
@click.option("--comic-id", required=True)
@click.option("--output", required=True)
def export(comic_id, output):
    """Export mock script for testing"""
    orchestrator = QAOrchestrator(
        exporter=MockExporter(),
        storage=JsonFileStorage(),
        chunking=PageBasedChunking(),
        llm_provider=OpenAIQAProvider(api_key="dummy"),
        applicator=NoopApplicator(),
    )

    script = orchestrator.export_script(
        comic_id=comic_id,
        base_fp="mock_fp",
        source_lang="ja",
        target_lang="zh-hk",
        output_path=output,
    )

    click.echo(f"Exported {len(script.blocks)} blocks to {output}")


@cli.command()
@click.option("--script", required=True)
@click.option("--output", required=True)
@click.option("--api-key", envvar="OPENAI_API_KEY", required=True)
def qa(script, output, api_key):
    """Run QA on script"""
    orchestrator = QAOrchestrator(
        exporter=MockExporter(),
        storage=JsonFileStorage(),
        chunking=PageBasedChunking(),
        llm_provider=OpenAIQAProvider(api_key=api_key),
        applicator=NoopApplicator(),
    )

    patch_set = orchestrator.qa_script(
        script_path=script,
        output_patch_path=output,
    )

    click.echo(f"Generated {len(patch_set.patches)} patches")
    click.echo(f"Summary: {patch_set.summary}")


@cli.command()
@click.option("--patches", required=True)
def apply(patches):
    """Apply patches (dry-run)"""
    orchestrator = QAOrchestrator(
        exporter=MockExporter(),
        storage=JsonFileStorage(),
        chunking=PageBasedChunking(),
        llm_provider=OpenAIQAProvider(api_key="dummy"),
        applicator=NoopApplicator(),
    )

    result = orchestrator.apply_patches(patch_path=patches)

    click.echo(f"Total: {result['total']}")
    click.echo(f"Applied: {result['applied']}")
    click.echo(f"Skipped: {result['skipped']}")


if __name__ == "__main__":
    cli()
```

### Add CLI support to `qa/pyproject.toml`

```toml
[project.optional-dependencies]
cli = ["click>=8.1"]

[project.scripts]
comic-qa = "comic_translate_qa.cli:cli"
```

---

                          prev_block=f"p{page}_b{i-1}" if i > 0 else None,
                          next_block=f"p{page}_b{i+1}" if i < 2 else None,
                      ),
                  ))

          return ScriptExport(
              version="1.0",
              comic_id=comic_id,
              base_fp=base_fp,
              script_id=f"{comic_id}:{base_fp}:{target_lang}",
              source_lang=source_lang,
              target_lang=target_lang,
              exported_at=time.time(),
              page_range=page_range,
              active_variant=variant,
              variants={variant: {"censored": False, "source": "test"}},
              glossary_snapshot={
                  "Character A": {
                      "translated": "角色A",
                      "category": "character_name",
                      "locked": True,
                  }
              },
              blocks=blocks,
          )

Update storage/init.py:

from .json_file import JsonFileStorage
from .mock_exporter import MockExporter

**all** = ["JsonFileStorage", "MockExporter"]

---

Task 10: Write Integration Test

File: tests/integration/test_qa_full_flow.py

import tempfile
from pathlib import Path
from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from comic_translate_qa.chunking import PageBasedChunking
from comic_translate_qa.providers import OpenAIQAProvider
from comic_translate_qa.applicator import NoopApplicator

def test_full_qa_flow():
"""Test complete QA flow: export → qa → apply"""

      # Setup
      with tempfile.TemporaryDirectory() as tmpdir:
          script_path = Path(tmpdir) / "script.json"
          patch_path = Path(tmpdir) / "patches.json"

          # Wire up components
          orchestrator = QAOrchestrator(
              exporter=MockExporter(),
              storage=JsonFileStorage(),
              chunking=PageBasedChunking(),
              llm_provider=OpenAIQAProvider(api_key="test-key"),  # Mock in real test
              applicator=NoopApplicator(),
          )

          # Step 1: Export
          script = orchestrator.export_script(
              comic_id="test_comic",
              base_fp="test_fp",
              source_lang="ja",
              target_lang="zh-hk",
              output_path=str(script_path),
          )

          assert script_path.exists()
          assert len(script.blocks) == 9  # 3 pages × 3 blocks

          # Step 2: QA (skip in test, requires real API key)
          # patch_set = orchestrator.qa_script(
          #     script_path=str(script_path),
          #     output_patch_path=str(patch_path),
          # )

          # Step 3: Apply (skip, depends on step 2)
          # result = orchestrator.apply_patches(patch_path=str(patch_path))
          # assert result["total"] >= 0

---

Task 11: Create CLI Wrapper (Optional)

File: packages/qa/src/comic_translate_qa/cli.py

import click
from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage, MockExporter
from .chunking import PageBasedChunking
from .providers import OpenAIQAProvider
from .applicator import NoopApplicator

@click.group()
def cli():
"""Comic Translate QA CLI"""
pass

@cli.command()
@click.option("--comic-id", required=True)
@click.option("--output", required=True)
def export(comic_id, output):
"""Export mock script for testing"""
orchestrator = QAOrchestrator(
exporter=MockExporter(),
storage=JsonFileStorage(),
chunking=PageBasedChunking(),
llm_provider=OpenAIQAProvider(api_key="dummy"),
applicator=NoopApplicator(),
)

      script = orchestrator.export_script(
          comic_id=comic_id,
          base_fp="mock_fp",
          source_lang="ja",
          target_lang="zh-hk",
          output_path=output,
      )

      click.echo(f"Exported {len(script.blocks)} blocks to {output}")

@cli.command()
@click.option("--script", required=True)
@click.option("--output", required=True)
@click.option("--api-key", envvar="OPENAI_API_KEY", required=True)
def qa(script, output, api_key):
"""Run QA on script"""
orchestrator = QAOrchestrator(
exporter=MockExporter(),
storage=JsonFileStorage(),
chunking=PageBasedChunking(),
llm_provider=OpenAIQAProvider(api_key=api_key),
applicator=NoopApplicator(),
)

      patch_set = orchestrator.qa_script(
          script_path=script,
          output_patch_path=output,
      )

      click.echo(f"Generated {len(patch_set.patches)} patches")
      click.echo(f"Summary: {patch_set.summary}")

@cli.command()
@click.option("--patches", required=True)
def apply(patches):
"""Apply patches (dry-run)"""
orchestrator = QAOrchestrator(
exporter=MockExporter(),
storage=JsonFileStorage(),
chunking=PageBasedChunking(),
llm_provider=OpenAIQAProvider(api_key="dummy"),
applicator=NoopApplicator(),
)

      result = orchestrator.apply_patches(patch_path=patches)

      click.echo(f"Total: {result['total']}")
      click.echo(f"Applied: {result['applied']}")
      click.echo(f"Skipped: {result['skipped']}")

if **name** == "**main**":
cli()

Add to qa/pyproject.toml:

[project.optional-dependencies]
cli = ["click>=8.1"]

[project.scripts]
comic-qa = "comic_translate_qa.cli:cli"

---
