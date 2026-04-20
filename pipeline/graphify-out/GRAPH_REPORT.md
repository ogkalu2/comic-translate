# Graph Report - .  (2026-04-16)

## Corpus Check
- Corpus is ~19,424 words - fits in a single context window. You may not need a graph.

## Summary
- 419 nodes · 996 edges · 13 communities detected
- Extraction: 62% EXTRACTED · 38% INFERRED · 0% AMBIGUOUS · INFERRED: 381 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Chunk Processing Pipeline|Chunk Processing Pipeline]]
- [[_COMMUNITY_OCR Translation Caches|OCR Translation Caches]]
- [[_COMMUNITY_Batch Page Execution|Batch Page Execution]]
- [[_COMMUNITY_Block Detection Flow|Block Detection Flow]]
- [[_COMMUNITY_Page Rendering State|Page Rendering State]]
- [[_COMMUNITY_Webtoon Visible Area|Webtoon Visible Area]]
- [[_COMMUNITY_Overlap Deduplication|Overlap Deduplication]]
- [[_COMMUNITY_Inpainting Operations|Inpainting Operations]]
- [[_COMMUNITY_Page Invalidation State|Page Invalidation State]]
- [[_COMMUNITY_Virtual Page Creation|Virtual Page Creation]]
- [[_COMMUNITY_First Page Helper|First Page Helper]]
- [[_COMMUNITY_Last Page Helper|Last Page Helper]]
- [[_COMMUNITY_Package Entry Point|Package Entry Point]]

## God Nodes (most connected - your core abstractions)
1. `CacheManager` - 64 edges
2. `BatchProcessor` - 39 edges
3. `InpaintingHandler` - 39 edges
4. `BlockDetectionHandler` - 29 edges
5. `ComicTranslatePipeline` - 29 edges
6. `OCRHandler` - 29 edges
7. `WebtoonBatchProcessor` - 28 edges
8. `TranslationHandler` - 27 edges
9. `ensure_pipeline_state()` - 25 edges
10. `BatchExecutionMixin` - 24 edges

## Surprising Connections (you probably didn't know these)
- `PreparedBatchPage` --uses--> `BatchRenderMixin`  [INFERRED]
  batch_processor.py → batch_render_mixin.py
- `PreparedBatchPage` --uses--> `BlockDetectionHandler`  [INFERRED]
  batch_processor.py → block_detection.py
- `PreparedBatchPage` --uses--> `CacheManager`  [INFERRED]
  batch_processor.py → cache_manager.py
- `PreparedBatchPage` --uses--> `InpaintingHandler`  [INFERRED]
  batch_processor.py → inpainting.py
- `PreparedBatchPage` --uses--> `OCRHandler`  [INFERRED]
  batch_processor.py → ocr_handler.py

## Communities

### Community 0 - "Chunk Processing Pipeline"
Cohesion: 0.04
Nodes (38): ChunkImageMixin, ChunkMappingMixin, ChunkPipelinePhaseMixin, ChunkProcessingMixin, ChunkImageMixin, ChunkMappingMixin, ChunkPipelinePhaseMixin, ChunkProcessingMixin (+30 more)

### Community 1 - "OCR Translation Caches"
Cohesion: 0.04
Nodes (35): CacheManager, Manages OCR and translation caching for the pipeline., Clear translation cache entries for the provided images, regardless of translato, Generate a hash for the image to use as cache key, Generate cache key for OCR results, Clear the OCR cache. Note: Cache now persists across image and model changes aut, Generate a unique identifier for a text block., Find a matching block ID in cache, allowing for small coordinate differences (+27 more)

### Community 2 - "Batch Page Execution"
Cohesion: 0.07
Nodes (11): BatchExecutionMixin, _is_recoverable_translation_error(), _merge_usage_stats(), BatchProcessor, PreparedBatchPage, BatchStateMixin, BatchExecutionMixin, BatchRenderMixin (+3 more)

### Community 3 - "Block Detection Flow"
Cohesion: 0.08
Nodes (27): BlockDetectionHandler, Handles text block detection and coordinate loading., _serialize_rectangles_from_blocks(), ComicTranslatePipeline, Translate visible area in webtoon mode., Regular batch processing., Webtoon batch processing with overlapping sliding windows., Release cached model instances to reduce GPU/CPU memory pressure. (+19 more)

### Community 4 - "Page Rendering State"
Cohesion: 0.17
Nodes (28): BatchRenderMixin, activate_target_lang(), best_available_stage(), _best_available_stage_from_ps(), _coerce_page_validity(), _coerce_target_validity(), _default_page_validity(), default_pipeline_state() (+20 more)

### Community 5 - "Webtoon Visible Area"
Cohesion: 0.08
Nodes (28): list, Perform OCR on the visible area in webtoon mode., Perform segmentation on the visible area in webtoon mode., Perform translation on the visible area in webtoon mode., convert_bboxes_to_webtoon_coordinates(), convert_block_to_visible_coordinates(), filter_and_convert_visible_blocks(), find_block_intersecting_pages() (+20 more)

### Community 6 - "Overlap Deduplication"
Cohesion: 0.18
Nodes (13): DedupeMixin, _patch_area(), _patch_bbox_to_xyxy(), Merge results from all chunks that processed this virtual page., Suppress clipped duplicates on page boundaries when a neighboring page already, _rect_area_xyxy(), _rect_intersection_area_xyxy(), build_render_template_map() (+5 more)

### Community 7 - "Inpainting Operations"
Cohesion: 0.18
Nodes (4): InpaintingHandler, _is_probable_oom(), Build an inpaint mask using the same refined stroke pipeline as manual segmentat, Handles image inpainting functionality.

### Community 8 - "Page Invalidation State"
Cohesion: 0.26
Nodes (12): invalidate_page_for_box_edit(), invalidate_page_for_format_edit(), invalidate_page_for_segmentation_edit(), invalidate_page_for_source_text_edit(), invalidate_page_for_translated_text_edit(), build_page_state_context(), get_active_viewer_state(), get_page_state() (+4 more)

### Community 9 - "Virtual Page Creation"
Cohesion: 0.25
Nodes (5): Creates virtual pages from physical webtoon pages to handle very long images., Initialize the virtual page creator.                  Args:             max_v, Create virtual pages from a physical page.                  Args:, Generate overlapping pairs of virtual pages for chunk processing.         This, VirtualPageCreator

### Community 10 - "First Page Helper"
Cohesion: 1.0
Nodes (1): Check if this is the first virtual page of the physical page.

### Community 11 - "Last Page Helper"
Cohesion: 1.0
Nodes (1): Check if this is the last virtual page of the physical page.

### Community 12 - "Package Entry Point"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **68 isolated node(s):** `Handles text block detection and coordinate loading.`, `Manages OCR and translation caching for the pipeline.`, `Clear the OCR cache. Note: Cache now persists across image and model changes aut`, `Clear the translation cache. Note: Cache now persists across image and model cha`, `Clear all cache entries (OCR, translation, inpaint) for the provided images.` (+63 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `First Page Helper`** (1 nodes): `Check if this is the first virtual page of the physical page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Last Page Helper`** (1 nodes): `Check if this is the last virtual page of the physical page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Package Entry Point`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CacheManager` connect `OCR Translation Caches` to `Chunk Processing Pipeline`, `Batch Page Execution`, `Block Detection Flow`, `Webtoon Visible Area`?**
  _High betweenness centrality (0.273) - this node is a cross-community bridge._
- **Why does `WebtoonBatchProcessor` connect `Chunk Processing Pipeline` to `OCR Translation Caches`, `Batch Page Execution`, `Block Detection Flow`, `Inpainting Operations`?**
  _High betweenness centrality (0.185) - this node is a cross-community bridge._
- **Why does `BatchProcessor` connect `Batch Page Execution` to `OCR Translation Caches`, `Block Detection Flow`, `Page Rendering State`, `Inpainting Operations`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `CacheManager` (e.g. with `PreparedBatchPage` and `BatchProcessor`) actually correct?**
  _`CacheManager` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `BatchProcessor` (e.g. with `BatchExecutionMixin` and `BatchRenderMixin`) actually correct?**
  _`BatchProcessor` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `InpaintingHandler` (e.g. with `PreparedBatchPage` and `BatchProcessor`) actually correct?**
  _`InpaintingHandler` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `BlockDetectionHandler` (e.g. with `PreparedBatchPage` and `BatchProcessor`) actually correct?**
  _`BlockDetectionHandler` has 23 INFERRED edges - model-reasoned connections that need verification._