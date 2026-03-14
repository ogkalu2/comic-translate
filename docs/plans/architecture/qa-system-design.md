# QA System — Abstract Design

## Purpose

Defines the interface layer and design patterns for the comic translation QA system. All concrete implementations (JSON storage, OpenAI provider, etc.) must conform to these abstractions.

This document is the **stable contract**. Feature-specific details (prompt templates, chunking heuristics) live in [`features/script-export-qa.md`](../features/script-export-qa.md).

---

## Design Patterns Used

| Pattern | Where | Why |
|---------|-------|-----|
| **Strategy** | `IChunkingStrategy`, `ILLMProvider` | Swap algorithms without changing orchestrator |
| **Facade** | `QAOrchestrator` | Single entry point coordinating 5 components |
| **Dependency Injection** | `QAOrchestrator.__init__` | All implementations injected, zero hardcoding |
| **Open/Closed** | All `I*` interfaces | New backends/providers = new class, no edits to existing code |
| **Template Method** | `ILLMProvider.review_chunk` | Subclasses define LLM call, base defines parse flow |

---

## Interfaces

### IScriptStorage

Persist and retrieve script exports and patch sets. Backend-agnostic.

```python
from abc import ABC, abstractmethod

class IScriptStorage(ABC):

    @abstractmethod
    def save_script(self, script: ScriptExport, path: str) -> None: ...

    @abstractmethod
    def load_script(self, path: str) -> ScriptExport: ...

    @abstractmethod
    def save_patch(self, patch_set: QAPatchSet, path: str) -> None: ...

    @abstractmethod
    def load_patch(self, path: str) -> QAPatchSet: ...
```

| Implementation | Package | Backend |
|---------------|---------|---------|
| `JsonFileStorage` | core | Local JSON files |
| `PostgresStorage` | core (future) | Postgres + pgvector |
| `S3Storage` | core (future) | AWS S3 |

### IScriptExporter

Convert internal comic representation to `ScriptExport`. Source-agnostic.

```python
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
    ) -> ScriptExport: ...
```

| Implementation | Package | Source |
|---------------|---------|--------|
| `MockExporter` | core | Test fixture data |
| `TextBlockExporter` | core (future) | Upstream `TextBlock[]` |
| `CtprExporter` | core (future) | `.ctpr` project files |
| `DatabaseExporter` | core (future) | Postgres blocks table |

### IChunkingStrategy

Split a `ScriptExport` into `QAChunk` objects for LLM processing.

```python
from typing import Iterator

class IChunkingStrategy(ABC):

    @abstractmethod
    def chunk(
        self,
        script: ScriptExport,
        chunk_size: int = 80,
        overlap: int = 5,
    ) -> Iterator[QAChunk]: ...
```

| Implementation | Package | Strategy |
|---------------|---------|----------|
| `PageBasedChunking` | qa | Cut on page boundaries, skip SFX/credit |
| `TokenBasedChunking` | qa (future) | Estimate tokens per block for tighter packing |

### ILLMProvider

Send a QA chunk to an LLM and parse the response into patches.

```python
class ILLMProvider(ABC):

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

| Implementation | Package | Provider |
|---------------|---------|----------|
| `OpenAIQAProvider` | qa | GPT-4o-mini / GPT-4o |
| `ClaudeQAProvider` | qa | Claude 3.5 Sonnet / Haiku |
| `LocalLLMProvider` | qa (future) | Ollama / vLLM |

### IPatchApplicator

Apply QA patches back to source data.

```python
class IPatchApplicator(ABC):

    @abstractmethod
    def apply_patches(
        self,
        patch_set: QAPatchSet,
        dry_run: bool = False,
        confidence_threshold: float = 0.7,
    ) -> Dict: ...
    # Returns: {"total": int, "applied": int, "skipped": int, "failed": int, "details": [...]}
```

| Implementation | Package | Target |
|---------------|---------|--------|
| `NoopApplicator` | qa | Dry-run, stats only |
| `JsonPatchApplicator` | qa | Apply to script JSON files |
| `CacheApplicator` | core (future) | Apply to TranslationCacheV2 |
| `DatabaseApplicator` | core (future) | Apply to Postgres blocks |

---

## Full Pipeline Interfaces

Beyond QA, the full pipeline uses these additional interfaces (defined in `core/interfaces/`):

### IPanelDetector

```python
class IPanelDetector(ABC):

    @abstractmethod
    def detect(self, image: np.ndarray) -> List[PanelBBox]: ...
```

### IBubbleDetector

```python
class IBubbleDetector(ABC):

    @abstractmethod
    def detect(self, image: np.ndarray, panels: List[PanelBBox]) -> List[BubbleBBox]: ...
```

### IOCREngine

```python
class IOCREngine(ABC):

    @abstractmethod
    def recognize(self, image: np.ndarray, bbox: List[int], lang: str) -> OCRResult: ...
```

### ISemanticRouter

```python
class ISemanticRouter(ABC):

    @abstractmethod
    def route(self, block: Block) -> RoutingDecision: ...
    # RoutingDecision: which translator to use, nsfw flag, skip flag
```

### ITranslator

```python
class ITranslator(ABC):

    @abstractmethod
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
        glossary: Optional[Dict] = None,
    ) -> TranslationResult: ...
```

### IInpainter

```python
class IInpainter(ABC):

    @abstractmethod
    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
```

### IRenderer

```python
class IRenderer(ABC):

    @abstractmethod
    def render(
        self,
        image: np.ndarray,
        blocks: List[Block],
        bubble_masks: Optional[Dict] = None,
    ) -> np.ndarray: ...
```

---

## QAOrchestrator (Facade)

Coordinates the full QA workflow: export → chunk → review → patch → apply.

```python
class QAOrchestrator:

    def __init__(
        self,
        exporter: IScriptExporter,
        storage: IScriptStorage,
        chunking: IChunkingStrategy,
        llm_provider: ILLMProvider,
        applicator: IPatchApplicator,
    ): ...

    def export_script(...) -> ScriptExport: ...
    def qa_script(...) -> QAPatchSet: ...
    def apply_patches(...) -> Dict: ...
```

See [`features/script-export-qa.md`](../features/script-export-qa.md) for full implementation.

---

## PipelineOrchestrator (Facade)

Coordinates the full translation pipeline: detect → OCR → route → translate → inpaint → render.

```python
class PipelineOrchestrator:

    def __init__(
        self,
        panel_detector: IPanelDetector,
        bubble_detector: IBubbleDetector,
        ocr_engine: IOCREngine,
        router: ISemanticRouter,
        translator: ITranslator,
        inpainter: IInpainter,
        renderer: IRenderer,
        storage: IScriptStorage,
    ): ...

    def process_comic(
        self,
        images: List[np.ndarray],
        comic_id: str,
        source_lang: str,
        target_lang: str,
    ) -> ScriptExport: ...

    def process_page(
        self,
        image: np.ndarray,
        page_number: int,
    ) -> List[Block]: ...
```

---

## Wiring Example

How to assemble components for different use cases:

```python
# QA only (minimal install)
from comic_translate_core.storage import JsonFileStorage
from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_qa.chunking import PageBasedChunking
from comic_translate_qa.providers import OpenAIQAProvider
from comic_translate_qa.applicator import NoopApplicator

qa = QAOrchestrator(
    exporter=MockExporter(),
    storage=JsonFileStorage(),
    chunking=PageBasedChunking(),
    llm_provider=OpenAIQAProvider(api_key="..."),
    applicator=NoopApplicator(),
)

# Full pipeline
from comic_translate_detection.panel import YoloPanelDetector
from comic_translate_detection.bubble import MaskRCNNBubbleDetector
from comic_translate_ocr import PaddleOCREngine
from comic_translate_translation import DeepLTranslator
from comic_translate_rendering import LamaInpainter, TextRenderer

pipeline = PipelineOrchestrator(
    panel_detector=YoloPanelDetector(model_path="..."),
    bubble_detector=MaskRCNNBubbleDetector(model_path="..."),
    ocr_engine=PaddleOCREngine(langs=["ja", "en"]),
    router=DefaultSemanticRouter(nsfw_dict=ehtag),
    translator=DeepLTranslator(api_key="..."),
    inpainter=LamaInpainter(model_path="..."),
    renderer=TextRenderer(font_dir="..."),
    storage=JsonFileStorage(),
)
```

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| [`pipeline-v2-overview.md`](pipeline-v2-overview.md) | System-level architecture (data model, stages, storage) |
| [`new-repo-structure.md`](new-repo-structure.md) | Package layout and dependency graph |
| [`features/script-export-qa.md`](../features/script-export-qa.md) | QA feature spec (data models, prompt, chunking details) |
