---
type: "query"
date: "2026-04-16T12:14:15.649205+00:00"
question: "show inpainting"
contributor: "graphify"
source_nodes: ["InpaintingHandler", "ImageViewer.get_mask_for_inpainting", "LaMa", "PatchInsertCommand"]
---

# Q: show inpainting

## Answer

Interpreted as the inpainting subsystem, not literal show_* UI methods. The graph centers inpainting on InpaintingHandler in pipeline/inpainting.py L17, with entry points from ImageViewer.get_mask_for_inpainting at app/ui/canvas/image_viewer.py L426 and ComicTranslate.inpaint_and_set at controller.py L738. Batch and webtoon flows connect through _run_chunk_inpainting at pipeline/batch_execution_mixin.py L429 and _run_chunk_inpaint at pipeline/webtoon_batch/chunk_pipeline_phase_mixin.py L72. Backend model nodes are InpaintModel in modules/inpainting/base.py L21, DiffusionInpaintModel in the same file at L406, and LaMa in modules/inpainting/lama.py L14. Results are applied through PatchInsertCommand in app/ui/commands/inpaint.py L8 and ImagePersistenceMixin.apply_inpaint_patches at app/controllers/image_persistence_mixin.py L238, with cache hooks in pipeline/cache_manager.py.

## Source Nodes

- InpaintingHandler
- ImageViewer.get_mask_for_inpainting
- LaMa
- PatchInsertCommand