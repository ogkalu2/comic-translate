# Script Export + QA Patch System — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A decoupled, extensible QA module that exports comic translations to a structured script, runs LLM-based quality review in chunks, and applies patches back — independent of any GUI or specific storage backend.

**Architecture:** Interface-driven (ABC) with Strategy + Facade patterns. `QAOrchestrator` coordinates five pluggable components: exporter, storage, chunking strategy, LLM provider, and patch applicator. All data flows through pure dataclasses.

**Tech Stack:** Python 3.12, dataclasses, ABC, JSON (initial backend), OpenAI/Claude API (initial LLM provider)

---

## 1. Data Models

All models are pure dataclasses with no business logic.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class BlockType(str, Enum):
    DIALOGUE = "dialogue"
    NARRATION = "narration"
    SFX = "sfx"
    CREDIT = "credit"


class PatchCategory(str, Enum):
    GLOSSARY_CONSISTENCY = "glossary_consistency"
    TONE = "tone"
    GRAMMAR = "grammar"
    STYLE = "style"              # reserved: character voice / speech habits
    LOCALIZATION = "localization" # reserved: cultural adaptation


@dataclass
class BlockContext:
    speaker: Optional[str] = None
    prev_block: Optional[str] = None
    next_block: Optional[str] = None


@dataclass
class ScriptBlock:
    block_id: str           # "p{page}_b{index}"
    page: int
    type: BlockType
    bbox: List[int]         # [x1, y1, x2, y2]
    original: str
    translated: str
    original_variant: str   # e.g. "pixiv_free", "tankobon"
    context: BlockContext
    qa_metadata: Optional[Dict] = None


@dataclass
class ScriptExport:
    version: str            # "1.0"
    comic_id: str
    base_fp: str            # perceptual hash fingerprint
    script_id: str          # "{comic_id}:{base_fp}:{target_lang}"
    source_lang: str
    target_lang: str
    exported_at: float
    page_range: List[int]   # [start, end]
    active_variant: str
    variants: Dict[str, Dict]
    glossary_snapshot: Dict[str, Dict]
    blocks: List[ScriptBlock]  # flattened, sorted by page + reading order


@dataclass
class QAPatch:
    block_id: str
    original: str
    old_translated: str
    new_translated: str
    reason: str
    category: PatchCategory
    confidence: float       # 0.0–1.0


@dataclass
class QAPatchSet:
    version: str            # "1.0"
    comic_id: str
    base_fp: str
    created_at: float
    qa_model: str
    chunk_range: Dict[str, str]  # {"from": "p1_b0", "to": "p20_b15"}
    summary: Dict           # see _build_summary()
    patches: List[QAPatch]


@dataclass
class QAChunk:
    chunk_id: int
    comic_id: str
    base_fp: str
    source_lang: str
    target_lang: str
    glossary_snapshot: Dict[str, Dict]
    context_blocks: List[ScriptBlock]  # read-only overlap from previous chunk
    blocks: List[ScriptBlock]          # blocks to QA
```

---

## 2. Interfaces

### 2.1 IScriptStorage

```python
from abc import ABC, abstractmethod

class IScriptStorage(ABC):
    """Persist and retrieve script exports and patch sets."""

    @abstractmethod
    def save_script(self, script: ScriptExport, path: str) -> None: ...

    @abstractmethod
    def load_script(self, path: str) -> ScriptExport: ...

    @abstractmethod
    def save_patch(self, patch_set: QAPatchSet, path: str) -> None: ...

    @abstractmethod
    def load_patch(self, path: str) -> QAPatchSet: ...
```

Planned implementations: `JsonFileStorage`, `PostgresStorage`, `S3Storage`

### 2.2 IScriptExporter

```python
class IScriptExporter(ABC):
    """Convert internal comic representation to ScriptExport."""

    @abstractmethod
    def export(
        self,
        comic_id: str,
        base_fp: str,
        source_lang: str,
        target_lang: str,
        page_range: Optional[List[int]] = None,
        variant: str = "default",
    ) -> ScriptExport: ...
```

Planned implementations: `TextBlockExporter` (from upstream TextBlock list), `ProjectStateExporter` (.ctpr), `MockExporter` (test data)

### 2.3 IChunkingStrategy

```python
from typing import Iterator

class IChunkingStrategy(ABC):
    """Split a ScriptExport into QAChunks for LLM processing."""

    @abstractmethod
    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]: ...
```

Planned implementations: `PageBasedChunking` (cut on page boundaries), `TokenBasedChunking` (estimate tokens per block)

### 2.4 ILLMProvider

```python
class ILLMProvider(ABC):
    """Send QA chunk to an LLM and parse patches."""

    @abstractmethod
    def review_chunk(
        self,
        chunk: QAChunk,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> List[QAPatch]: ...

    @abstractmethod
    def get_model_name(self) -> str: ...
```

Planned implementations: `OpenAIProvider`, `ClaudeProvider`, `LocalLLMProvider`

### 2.5 IPatchApplicator

```python
class IPatchApplicator(ABC):
    """Apply QA patches back to source data."""

    @abstractmethod
    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict: ...
    # Returns: {"total": int, "applied": int, "skipped": int, "failed": int, "details": [...]}
```

Planned implementations: `NoopApplicator` (dry-run / stats only), `TextBlockApplicator`, `CacheApplicator`, `DatabaseApplicator`

---

## 3. QAOrchestrator (Facade)

```python
import time

class QAOrchestrator:
    """Coordinates export → chunk → QA → patch → apply."""

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
        patch_set = self.storage.load_patch(patch_path)
        return self.applicator.apply_patches(patch_set, dry_run, confidence_threshold)

    @staticmethod
    def _build_summary(patches: List[QAPatch], total_reviewed: int) -> Dict:
        from collections import Counter
        categories = Counter(p.category.value for p in patches)
        return {
            "total_reviewed": total_reviewed,
            "total_patched": len(patches),
            "categories": dict(categories),
        }
```

---

## 4. QA Chunking Strategy (Reference: PageBasedChunking)

```python
class PageBasedChunking(IChunkingStrategy):
    """
    Cut chunks on page boundaries.
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
        # Filter reviewable blocks
        reviewable = [b for b in script.blocks if b.type not in self.SKIP_TYPES]

        i = 0
        chunk_id = 0
        while i < len(reviewable):
            chunk_blocks = reviewable[i:i + chunk_size]
            context_blocks = reviewable[max(0, i - overlap):i] if i > 0 else []

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

---

## 5. LLM QA Prompt Template

```python
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
  {{"block_id": "...", "original": "...", "old_translated": "...", "new_translated": "...", "reason": "...", "category": "glossary_consistency|tone|grammar", "confidence": 0.0}}
]
If no issues: []
"""
```

---

## 6. Implementation Roadmap

### Phase 1 — Minimal JSON Backend (first target)
- `JsonFileStorage(IScriptStorage)` — serialize/deserialize with `json` module
- `MockExporter(IScriptExporter)` — generate test ScriptExport from fixture data
- `PageBasedChunking(IChunkingStrategy)` — as designed above
- `OpenAIProvider(ILLMProvider)` — call GPT-4o-mini, parse JSON response
- `NoopApplicator(IPatchApplicator)` — print stats, no writes

### Phase 2 — Real Exporters
- `TextBlockExporter` — convert upstream `TextBlock[]` + `ComicSession` to `ScriptExport`
- `CacheApplicator` — apply patches back to `TranslationCacheV2`

### Phase 3 — Advanced
- `PostgresStorage` — pgvector-backed storage
- `ClaudeProvider` / `LocalLLMProvider`
- `TokenBasedChunking` — estimate tokens per block for tighter packing
- Relay Network integration (query remote nodes for existing QA patches)

### Phase 4 — Optional
- Blockchain audit trail (hash patches on-chain)
- Multi-variant cross-check QA
