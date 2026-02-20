# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Comic Translate is a PySide6-based desktop application for translating comics and manga using AI. It supports multiple languages and uses state-of-the-art models for text detection, OCR, inpainting, and translation via LLMs (GPT-4, Claude, Gemini).

## Development Commands

### Setup and Installation
```bash
# Initial setup (Python 3.12 required)
uv init --python 3.12
uv add -r requirements.txt --compile-bytecode

# For NVIDIA GPU support
uv pip install onnxruntime-gpu

# Update dependencies
git pull
uv add -r requirements.txt --compile-bytecode
```

### Running the Application
```bash
# Launch GUI
uv run comic.py
```

### Translation Files
```bash
# Compile Qt translation files (.ts to .qm)
# Translation source files are in resources/translations/
# Compiled files go to resources/translations/compiled/
pyside6-lrelease resources/translations/ct_<lang>.ts -qm resources/translations/compiled/ct_<lang>.qm
```

## Architecture

### Entry Point and Application Lifecycle
- **comic.py**: Main entry point. Handles single-instance enforcement via QLocalServer, splash screen with background loading, file association (.ctpr files), and translation loading.
- **controller.py**: Main application controller (`ComicTranslate` class) that inherits from `ComicTranslateUI`. Orchestrates all major components and manages application state.

### Core Components

#### Pipeline System (pipeline/)
The translation pipeline is modular and orchestrated by `ComicTranslatePipeline`:
- **main_pipeline.py**: Central orchestrator that delegates to specialized handlers
- **block_detection.py**: Text and bubble detection using RT-DETR-v2 model
- **segmentation_handler.py**: Algorithmic text segmentation within detected blocks
- **ocr_handler.py**: OCR processing with caching support
- **inpainting.py**: Text removal using LaMa/AOT-GAN/MI-GAN models
- **translation_handler.py**: Translation with LLM context and caching
- **batch_processor.py**: Batch processing for regular comics
- **webtoon_batch_processor.py**: Specialized batch processing for webtoon format
- **cache_manager.py**: Caches OCR and translation results to avoid redundant API calls
- **virtual_page.py**: Manages virtual page state for webtoon mode

#### Detection and Processing Modules (modules/)
- **modules/detection/**: Text/bubble detection models (RT-DETR-v2, font detection)
  - Uses ONNX runtime for inference
  - `rtdetr_v2_onnx.py` is the main detector
  - `utils/` contains geometry, bubble, and text line utilities

- **modules/ocr/**: OCR implementations
  - `manga_ocr/`: Japanese OCR
  - `pororo/`: Korean OCR
  - `ppocr/`: PPOCRv5 for other languages
  - `gemini_ocr.py`, `microsoft_ocr.py`, `gpt_ocr.py`: Cloud OCR options
  - `factory.py`: OCR provider selection logic

- **modules/translation/**: Translation providers
  - `llm/`: LLM-based translators (GPT, Claude, Gemini, DeepSeek, xAI, OpenRouter, GitHub, Custom)
  - `deepl.py`, `microsoft.py`, `yandex.py`: Traditional MT services
  - `factory.py`: Translator provider selection

- **modules/inpainting/**: Text removal models
  - `lama.py`: LaMa model (anime/manga finetuned)
  - `aot.py`: AOT-GAN model
  - `mi_gan.py`: MI-GAN model

- **modules/rendering/**: Text rendering and layout
  - `render.py`: Main rendering logic with word wrapping
  - `hyphen_textwrap.py`: Hyphenation support for text wrapping

- **modules/utils/**: Shared utilities
  - `textblock.py`: Core `TextBlock` class representing detected/translated text
  - `file_handler.py`: Archive extraction (CBR, CBZ, PDF, etc.)
  - `pipeline_config.py`: Settings validation
  - `language_utils.py`: Language code mapping and utilities
  - `translator_utils.py`: Translation formatting helpers

#### UI Layer (app/ui/)
- **main_window.py**: Main window UI setup (`ComicTranslateUI` class)
- **canvas/**: Image viewing and editing
  - `image_viewer.py`: Main canvas for displaying and editing images
  - `text_item.py`: Editable text blocks on canvas
  - `rectangle.py`: Bounding box rectangles
  - `drawing_manager.py`: Manual drawing tools (brush, eraser)
  - `webtoons/`: Specialized webtoon viewing components

- **settings/**: Settings dialog and configuration
  - `settings_page.py`: Main settings interface
  - `settings_ui.py`: Settings UI components

- **commands/**: Undo/redo command pattern implementation
  - All editing operations use Qt's QUndoCommand pattern
  - `box.py`, `text_edit.py`, `image.py`, etc.

- **dayu_widgets/**: Custom Qt widgets library (forked/modified)

#### Controllers (app/controllers/)
Separate concerns for different aspects of the application:
- **image.py**: Image state management, history, memory management
- **projects.py**: Project file (.ctpr) loading/saving
- **text.py**: Text block editing and formatting
- **rect_item.py**: Rectangle/bounding box manipulation
- **webtoons.py**: Webtoon-specific functionality
- **search_replace.py**: Search and replace across text blocks

#### Project State (app/projects/)
- **project_state.py**: Save/load project files (.ctpr format)
  - Uses msgpack for serialization
  - Stores images, patches, text blocks, and settings
  - Cross-platform path handling (POSIX paths in archives)
- **parsers.py**: Custom encoders/decoders for project serialization

#### Account System (app/account/)
- **auth/**: OAuth authentication for cloud services
- **config.py**: Account configuration

### Data Flow

1. **Image Loading**: FileHandler extracts archives → images loaded into memory
2. **Detection**: RT-DETR-v2 detects text/bubble boxes → segmentation creates TextBlocks
3. **OCR**: OCR provider extracts text from each TextBlock → cached
4. **Inpainting**: Selected inpainting model removes text → patches stored
5. **Translation**: LLM translates text with page context → cached
6. **Rendering**: Text rendered back onto inpainted image with proper layout
7. **Editing**: User can manually edit boxes, text, and formatting via canvas
8. **Saving**: Project state saved to .ctpr file (msgpack + images)

### State Management

- **Image States**: Tracked per image with history for undo/redo
- **Undo/Redo**: Qt's QUndoStack/QUndoGroup with command pattern
- **Memory Management**: LRU-style management keeps recent images in memory, older ones on disk
- **Caching**: OCR and translation results cached to avoid redundant API calls
- **Project Files**: .ctpr files are ZIP archives containing msgpack state + images

### Key Design Patterns

- **Pipeline Pattern**: Modular handlers for each processing stage
- **Command Pattern**: All edits are QUndoCommand subclasses
- **Factory Pattern**: OCR and translator providers selected via factories
- **Controller Pattern**: Separate controllers for different concerns
- **Observer Pattern**: Qt signals/slots for event handling

### Language Support

The application supports multiple UI languages via Qt's translation system:
- Translation files: `resources/translations/ct_<lang>.ts`
- Compiled files: `resources/translations/compiled/ct_<lang>.qm`
- Supported: English, Korean, French, Simplified Chinese, Traditional Chinese (Taiwan/Hong Kong), Russian, German, Spanish, Italian, Turkish

### Important Notes

- The application uses single-instance enforcement (only one instance can run)
- .ctpr files use POSIX paths internally for cross-platform compatibility
- Image history is stored both in-memory (recent) and on-disk (older)
- The pipeline uses shared handlers to maintain state consistency
- Webtoon mode has specialized processing for vertical scrolling comics
- All file paths should be absolute, not relative
- Archive extraction creates temporary directories that must be cleaned up

### Git Remotes

This repository has two remotes:
- **origin**: https://github.com/ogkalu2/comic-translate (upstream/original)
- **fork**: https://github.com/mythic3011/comic-translate.git (your fork)

To sync with the original repository:
```bash
git fetch origin
git merge origin/main
# or
git rebase origin/main
```
