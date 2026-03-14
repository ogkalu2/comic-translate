# New Repository Architecture

## Overview

Multi-package monorepo using uv workspace. Each package is independently installable with its own dependencies. Core has zero external dependencies. Heavy ML/AI deps are isolated in optional packages.

---

## Repository Layout

```
comic-translate/
├── pyproject.toml                          # Workspace root
├── uv.lock
├── CLAUDE.md
├── LICENSE
│
├── packages/
│   ├── core/                               # comic-translate-core
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── comic_translate_core/
│   │           ├── __init__.py
│   │           ├── models/
│   │           │   ├── __init__.py
│   │           │   ├── block.py            # Block, BlockType, BlockContext
│   │           │   ├── script.py           # ScriptExport, ScriptBlock
│   │           │   ├── patch.py            # QAPatch, QAPatchSet, PatchCategory
│   │           │   ├── comic.py            # ComicMeta, VariantMeta
│   │           │   ├── glossary.py         # GlossaryEntry, GlossarySnapshot
│   │           │   └── chunk.py            # QAChunk
│   │           ├── interfaces/
│   │           │   ├── __init__.py
│   │           │   ├── storage.py          # IScriptStorage
│   │           │   ├── exporter.py         # IScriptExporter
│   │           │   ├── chunking.py         # IChunkingStrategy
│   │           │   ├── llm_provider.py     # ILLMProvider
│   │           │   ├── applicator.py       # IPatchApplicator
│   │           │   ├── detector.py         # IPanelDetector, IBubbleDetector
│   │           │   ├── ocr.py              # IOCREngine
│   │           │   ├── translator.py       # ITranslator
│   │           │   ├── router.py           # ISemanticRouter
│   │           │   ├── inpainter.py        # IInpainter
│   │           │   └── renderer.py         # IRenderer
│   │           ├── pipeline/
│   │           │   ├── __init__.py
│   │           │   ├── orchestrator.py     # PipelineOrchestrator (facade)
│   │           │   └── qa_orchestrator.py  # QAOrchestrator (facade)
│   │           ├── storage/
│   │           │   ├── __init__.py
│   │           │   └── json_file.py        # JsonFileStorage
│   │           └── fingerprint/
│   │               ├── __init__.py
│   │               └── hasher.py           # base_fp, variant_id computation
│   │
│   ├── detection/                          # comic-translate-detection
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── comic_translate_detection/
│   │           ├── __init__.py
│   │           ├── panel/
│   │           │   ├── __init__.py
│   │           │   ├── yolo.py             # YOLOv12 panel detector
│   │           │   └── opencv_fallback.py  # OpenCV fallback
│   │           ├── bubble/
│   │           │   ├── __init__.py
│   │           │   ├── mask_rcnn.py        # Mask R-CNN bubble detector
│   │           │   └── heuristic.py        # SFX / credit heuristics
│   │           └── reading_order.py        # NMS + geometric sorting
│   │
│   ├── ocr/                                # comic-translate-ocr
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── comic_translate_ocr/
│   │           ├── __init__.py
│   │           ├── paddleocr.py            # PaddleOCR v5
│   │           ├── manga_ocr.py            # manga-ocr (Japanese)
│   │           ├── cloud/
│   │           │   ├── __init__.py
│   │           │   ├── gpt_vision.py       # GPT-4o vision fallback
│   │           │   └── microsoft.py        # Azure OCR
│   │           ├── noise_filter.py         # OCR noise detection + filtering
│   │           └── lang_detect.py          # Language identification
│   │
│   ├── translation/                        # comic-translate-translation
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── comic_translate_translation/
│   │           ├── __init__.py
│   │           ├── providers/
│   │           │   ├── __init__.py
│   │           │   ├── openai.py
│   │           │   ├── claude.py
│   │           │   ├── deepl.py
│   │           │   ├── local_llm.py        # Ollama / vLLM
│   │           │   └── nsfw_local.py       # EhTag + NSFW dictionary
│   │           ├── router.py               # Semantic routing (NSFW/SFX/credit)
│   │           ├── glossary.py             # Runtime glossary enforcement
│   │           ├── context.py              # Story context window
│   │           └── fallback.py             # Free → paid tier fallback chain
│   │
│   ├── qa/                                 # comic-translate-qa
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── comic_translate_qa/
│   │           ├── __init__.py
│   │           ├── chunking/
│   │           │   ├── __init__.py
│   │           │   ├── page_based.py       # PageBasedChunking
│   │           │   └── token_based.py      # TokenBasedChunking
│   │           ├── providers/
│   │           │   ├── __init__.py
│   │           │   ├── openai.py           # OpenAI QA provider
│   │           │   └── claude.py           # Claude QA provider
│   │           ├── prompt.py               # QA prompt templates
│   │           └── applicator/
│   │               ├── __init__.py
│   │               ├── noop.py             # Dry-run / stats only
│   │               └── json_patch.py       # Apply patches to JSON scripts
│   │
│   ├── rendering/                          # comic-translate-rendering
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── comic_translate_rendering/
│   │           ├── __init__.py
│   │           ├── inpainting/
│   │           │   ├── __init__.py
│   │           │   ├── lama.py
│   │           │   └── aot.py
│   │           ├── text_render.py          # Text overlay + wrapping
│   │           ├── collision.py            # Collision resolver
│   │           └── bubble_expand.py        # Bubble-aware expansion
│   │
│   └── cli/                                # comic-translate-cli (meta-package)
│       ├── pyproject.toml
│       └── src/
│           └── comic_translate_cli/
│               ├── __init__.py
│               ├── main.py                 # Entry point
│               ├── cmd_detect.py
│               ├── cmd_ocr.py
│               ├── cmd_translate.py
│               ├── cmd_qa.py
│               ├── cmd_render.py
│               └── cmd_export.py
│
├── docs/
│   └── plans/
│       ├── README.md
│       ├── architecture/
│       │   ├── pipeline-v2-overview.md
│       │   └── new-repo-structure.md       # This file
│       ├── features/
│       │   └── script-export-qa.md
│       ├── implementation/
│       ├── legacy/
│       └── reviews/
│
├── tests/
│   ├── conftest.py                         # Shared fixtures
│   ├── fixtures/
│   │   ├── sample_script.json
│   │   ├── sample_patch.json
│   │   └── sample_images/
│   ├── unit/
│   │   ├── test_core/
│   │   │   ├── test_models.py
│   │   │   ├── test_json_storage.py
│   │   │   └── test_fingerprint.py
│   │   ├── test_detection/
│   │   ├── test_ocr/
│   │   ├── test_translation/
│   │   ├── test_qa/
│   │   │   ├── test_chunking.py
│   │   │   ├── test_prompt.py
│   │   │   └── test_applicator.py
│   │   └── test_rendering/
│   └── integration/
│       └── test_full_pipeline.py
│
└── resources/
    ├── glossaries/                         # Built-in glossary data
    │   └── ehtag/
    ├── fonts/
    └── models/                             # Model weights (gitignored)
        └── .gitkeep
```

---

## Package Definitions

### comic-translate-core

Foundation package. Zero external dependencies (stdlib only).

```toml
[project]
name = "comic-translate-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4"]
```

**Contains:**
- All data models (dataclasses)
- All interfaces (ABCs)
- Pipeline orchestrators (facades that accept injected implementations)
- JsonFileStorage (only uses stdlib `json`)
- Fingerprint computation (only uses stdlib `hashlib`)

**Import examples:**
```python
from comic_translate_core.models import Block, ScriptExport, QAPatch
from comic_translate_core.interfaces import IScriptStorage, ILLMProvider
from comic_translate_core.pipeline import QAOrchestrator
from comic_translate_core.storage import JsonFileStorage
```

### comic-translate-detection

Panel and bubble detection. Heavy deps: ONNX, OpenCV.

```toml
[project]
name = "comic-translate-detection"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "comic-translate-core>=0.1.0",
    "onnxruntime>=1.17",
    "opencv-python-headless>=4.9",
    "numpy>=1.26",
]

[project.optional-dependencies]
gpu = ["onnxruntime-gpu>=1.17"]
coreml = ["coremltools>=7.0"]
```

**Import examples:**
```python
from comic_translate_detection.panel import YoloPanelDetector
from comic_translate_detection.bubble import MaskRCNNBubbleDetector
```

### comic-translate-ocr

OCR engines. Heavy deps: PaddleOCR, manga-ocr.

```toml
[project]
name = "comic-translate-ocr"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "comic-translate-core>=0.1.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
paddle = ["paddleocr>=2.8", "paddlepaddle>=2.6"]
manga = ["manga-ocr>=0.1.11"]
cloud = ["openai>=1.0", "httpx>=0.27"]
```

### comic-translate-translation

Translation providers + semantic routing.

```toml
[project]
name = "comic-translate-translation"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "comic-translate-core>=0.1.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
openai = ["openai>=1.0"]
anthropic = ["anthropic>=0.25"]
deepl = ["deepl>=1.17"]
local = ["ollama>=0.2"]
all = [
    "comic-translate-translation[openai,anthropic,deepl,local]",
]
```

### comic-translate-qa

QA system. Depends on core + translation providers.

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
anthropic = ["anthropic>=0.25"]
all = ["comic-translate-qa[openai,anthropic]"]
```

### comic-translate-rendering

Text rendering + inpainting. Heavy deps: ONNX, Pillow.

```toml
[project]
name = "comic-translate-rendering"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "comic-translate-core>=0.1.0",
    "Pillow>=10.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
inpainting = ["onnxruntime>=1.17"]
```

### comic-translate-cli

Meta-package + CLI entry point.

```toml
[project]
name = "comic-translate-cli"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "comic-translate-core>=0.1.0",
    "click>=8.1",
]

[project.optional-dependencies]
full = [
    "comic-translate-detection",
    "comic-translate-ocr[paddle,manga]",
    "comic-translate-translation[all]",
    "comic-translate-qa[all]",
    "comic-translate-rendering[inpainting]",
]
qa-only = [
    "comic-translate-qa[all]",
]
translate-only = [
    "comic-translate-translation[all]",
]

[project.scripts]
comic-translate = "comic_translate_cli.main:cli"
```

---

## Workspace Root

```toml
[project]
name = "comic-translate-workspace"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
comic-translate-core = { workspace = true }
comic-translate-detection = { workspace = true }
comic-translate-ocr = { workspace = true }
comic-translate-translation = { workspace = true }
comic-translate-qa = { workspace = true }
comic-translate-rendering = { workspace = true }
comic-translate-cli = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
    "packages/core/src",
    "packages/detection/src",
    "packages/ocr/src",
    "packages/translation/src",
    "packages/qa/src",
    "packages/rendering/src",
    "packages/cli/src",
]

[tool.ruff]
target-version = "py312"
line-length = 100
```

---

## Dependency Graph

```
                    comic-translate-core (0 deps)
                    ┌──────────┼──────────────┐
                    │          │              │
              detection      ocr        translation
              (onnx,cv2)  (paddle,     (httpx,openai,
                          manga-ocr)   anthropic,deepl)
                    │          │              │
                    │          │         ┌────┘
                    │          │         │
                    │          │        qa
                    │          │    (core + llm providers)
                    │          │         │
                    └──────────┼─────────┘
                               │
                           rendering
                        (pillow,onnx)
                               │
                    ┌──────────┘
                    │
                   cli
              (click + all above optional)
```

No circular dependencies. Core is always the root.

---

## Install Scenarios

| Scenario | Command | What you get |
|----------|---------|-------------|
| Dev (all packages, editable) | `uv sync --all-packages` | Everything linked locally |
| QA only | `pip install comic-translate-core comic-translate-qa[openai]` | Script export + QA + OpenAI |
| Full pipeline | `pip install comic-translate-cli[full]` | All packages + CLI |
| Translation only | `pip install comic-translate-cli[translate-only]` | Core + translation providers |
| CI (core tests) | `pip install comic-translate-core[dev]` | Core + pytest + ruff |
| CI (full tests) | `uv sync --all-packages` | All packages for integration tests |

---

## CI Strategy

```yaml
# .github/workflows/ci.yml
jobs:
  test-core:
    # Fast, no heavy deps
    steps:
      - uv sync -p packages/core
      - pytest tests/unit/test_core

  test-qa:
    # Medium, needs core + qa
    steps:
      - uv sync -p packages/core -p packages/qa
      - pytest tests/unit/test_qa

  test-detection:
    # Slow, needs ONNX
    steps:
      - uv sync -p packages/core -p packages/detection
      - pytest tests/unit/test_detection

  test-integration:
    # Slowest, needs everything
    needs: [test-core, test-qa, test-detection]
    steps:
      - uv sync --all-packages
      - pytest tests/integration
```

---

## Migration from Upstream

| Upstream module | New package | Adapter needed |
|----------------|-------------|----------------|
| `pipeline/main_pipeline.py` | `core/pipeline/orchestrator.py` | Rewrite |
| `pipeline/cache_v2.py` | `core/storage/` | Wrap as IScriptStorage |
| `pipeline/comic_glossary.py` | `core/models/glossary.py` | Extract data model |
| `pipeline/comic_session.py` | `translation/context.py` | Rewrite |
| `pipeline/discovery_pass.py` | `translation/glossary.py` | Rewrite |
| `modules/detection/` | `detection/` | Rewrite with interfaces |
| `modules/ocr/` | `ocr/` | Rewrite with interfaces |
| `modules/translation/` | `translation/providers/` | Rewrite with interfaces |
| `modules/rendering/` | `rendering/` | Rewrite with interfaces |
| `modules/inpainting/` | `rendering/inpainting/` | Rewrite with interfaces |
| `modules/utils/textblock.py` | `core/models/block.py` | Rewrite as dataclass |
| `app/projects/project_state.py` | `core/storage/ctpr.py` (future) | Adapter |
