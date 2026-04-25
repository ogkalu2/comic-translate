# Graph Report - .  (2026-04-25)

## Corpus Check
- 348 files · ~515,772 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 5497 nodes · 15886 edges · 103 communities detected
- Extraction: 47% EXTRACTED · 53% INFERRED · 0% AMBIGUOUS · INFERRED: 8389 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]

## God Nodes (most connected - your core abstractions)
1. `get()` - 397 edges
2. `TextBlock` - 286 edges
3. `TextBlockItem` - 204 edges
4. `MToolButton` - 185 edges
5. `MLabel` - 145 edges
6. `ComicTranslate` - 135 edges
7. `ImageViewer` - 124 edges
8. `MPushButton` - 105 edges
9. `SettingsPage` - 85 edges
10. `TextItemProperties` - 84 edges

## Surprising Connections (you probably didn't know these)
- `Do the heavy loading in background thread.` --uses--> `ComicTranslate`  [INFERRED]
  comic.py → controller.py
- `ComicTranslate` --uses--> `Webtoon controller with lazy loading support.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Switch to memory-efficient lazy loading webtoon mode.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Set up scene item management for lazy loading.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Connect events for lazy loading triggers.`  [INFERRED]
  controller.py → app\controllers\webtoons.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (334): AboutPage, AccountPage, Show the logged out state., Show the logged in state., MAlert, Get MAlert feedback type.         :return: str, Get MAlert feedback message.         :return: six.string_types, Set MAlert to InfoType (+326 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (206): find_matching_item(), find_matching_rect(), _serialize_rectangles_from_blocks(), BrushStrokeManager, Brush Stroke Manager for Webtoon Scene Items  Handles brush stroke management, Process a single brush stroke and distribute it to pages., Create a page-specific path from scene path elements., Manages brush strokes for webtoon mode with lazy loading. (+198 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (234): extract_archive(), _get_cached_pdf(), is_image_file(), list_archive_image_entries(), make(), make_cb7(), make_cbz(), make_pdf() (+226 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (191): create_new_blk(), create_new_txt_item(), create_path_item(), create_rect_item(), find_matching_blk(), find_matching_txt_item(), invalidate_page_render_pipeline(), PatchCommandBase (+183 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (79): Update or add a single block's translation result to the cache., ComicTranslateUI, ComicTranslate, ImageCollectionLoadMixin, ImageCollectionMutationMixin, ImageDisplayMixin, ImageErrorMixin, Handle toggling skip status for images                  Args:             fil (+71 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (169): ABC, BaseLLMTranslation, detect(), initialize(), _merge_usage_snapshots(), OCREngine, _perform_translation(), Whether the engine can recognize a list of crops without page detection. (+161 more)

### Community 6 - "Community 6"
Cohesion: 0.01
Nodes (181): AuthClient, Starts the new authentication flow., Handles the tokens and user info received from the backend via the local server., Handles errors emitted by the AuthServerThread., Called when the AuthServerThread finishes execution., Safely attempts to clear server thread reference., Clean up threads before application exit., Cancels the currently active authentication flow. (+173 more)

### Community 7 - "Community 7"
Cohesion: 0.01
Nodes (192): contour_area(), draw_contours(), get_perspective_transform(), mean(), Calculates the area of a polygon defined by a contour using the Shoelace formula, Emulates cv2.drawContours using Pillow and Numpy.      Args:         image (n, Calculates the 3x3 perspective transform matrix using a vectorized     NumPy im, Performs a perspective warp using PIL/Pillow.          Args:         image (n (+184 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (181): LLMTranslation, Abstract base class for all translation engines.     Defines common interface an, Translate text blocks using LLM.                  Args:             blk_list: Li, Initialize the translation engine with necessary parameters.                  Ar, Base class for LLM-based translation engines with shared functionality., Base class for LLM-based translation engines with shared functionality., Get standardized language code from language name.                  Args:, Perform translation using specific LLM.                  Args:             user_ (+173 more)

### Community 9 - "Community 9"
Cohesion: 0.02
Nodes (124): _as_mask(), bounding_rect(), find_contours(), Image analysis operations for the imkit module., findContours-style border tracing that matches OpenCV ordering (Suzuki-style sta, OpenCV-style boundingRect replacement.      Args:         contour: np.ndarray, _trace_border_fast(), BatchProcessor (+116 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (81): BatchReportStateMixin, BatchReportViewMixin, __init__(), MBaseButton, MDBPathButtons, parse_db_orm(), parse_path(), slot_action_clicked() (+73 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (96): AOT, Input image and output image have same size         image: [H, W, C] RGB, resize_keep_aspect(), DiffusionInpaintModel, forward(), init_model(), InpaintModel, images: [H, W, C] RGB, not normalized         masks: [H, W]         return: BG (+88 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (98): DetectionEngine, Abstract base class for all detection engines.     Each model implementation sh, Export cache contents in a project-serializable form., DetectionEngine, Move tensors in nested containers to device; returns the same structure.     Su, tensors_to_device(), Create and initialize RT-DETR-v2 detection engine., calculate_iou() (+90 more)

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (45): MFlowLayout, FlowLayout, the code is come from PySide/examples/layouts/flowlayout.py     I c, EdgeResizer, _edges_at(), Return a Qt.Edges flag for whichever window edges *gpos* is within *margin* pixe, Event filter that provides edge resize cursors and startSystemResize for framele, PageListView, Handle selection changes and emit signal with selected indices. (+37 more)

### Community 14 - "Community 14"
Cohesion: 0.02
Nodes (84): get_available_langs(), get_available_models(), get_default_model(), load(), PororoBiencoderBase, PororoFactoryBase, PororoGenerationBase, PororoSimpleBase (+76 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (69): CharacterStyle, get_rule(), GlyphPlacement, PlacementRule, Determines glyph placement rules for vertical text., QAbstractTextDocumentLayout, Break long text to multiple lines, and find the largest point size         so t, Break long text to multiple lines, and find the largest point size         so t (+61 more)

### Community 16 - "Community 16"
Cohesion: 0.03
Nodes (41): MDateEdit, MDateTimeEdit, MDoubleSpinBox, MTimeEdit, Set the MDoubleSpinBox size.         :param value: integer         :return: No, Set MDoubleSpinBox to huge size, Set MDoubleSpinBox to large size, Set MDoubleSpinBox to  medium (+33 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (23): MComboBoxSearchMixin, MFontComboBox, Set the avatar size.         :param value: integer         :return: None, Override setView to flag _has_custom_view variable., Override default showPopup. When set custom menu, show the menu instead., Set MComboBox to huge size, Set MComboBox to large size, Set MComboBox to  medium (+15 more)

### Community 18 - "Community 18"
Cohesion: 0.07
Nodes (27): is_close(), Restart the application.     Works for both running as script and compiled exec, restart_application(), SearchReplaceApplyMixin, _apply_preserve_case(), _apply_replacements_to_html(), _apply_text_delta_to_document(), BlockKey (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (28): init_weights(), Vgg16BN, DoubleConv, This code is adapted from https://github.com/clovaai/CRAFT-pytorch/blob/master/c, BasicBlock, BidirectionalLSTM, GridGenerator, init_weights() (+20 more)

### Community 20 - "Community 20"
Cohesion: 0.08
Nodes (8): _fmt_date(), _NewCard, _PillButton, Rebuild rows from [{path, mtime}, …] list (newest modified first)., Emit via sig so controller can clear state & show home., _RecentRow, StartupHomeScreen, _valid_urls()

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (15): MExpandingTextEdit, Handle Enter key to emit returnPressed signal., Return the plain text content (QLineEdit compatibility)., Set the plain text content (QLineEdit compatibility)., Clear the text content., Get placeholder text., A plain text edit that:     - Starts with single-line height     - Expands ver, Recalculate height when widget is resized. (+7 more)

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (18): ImageLoadWorker, ListViewImageLoader, process_queue(), Lazy image loader for QListWidget that loads thumbnails only when visible., Worker thread for loading images in the background., Clear all loaded images and reset state., Clear all loaded images and reset state., Handle scroll events with debouncing. (+10 more)

### Community 23 - "Community 23"
Cohesion: 0.1
Nodes (17): dedent(), indent(), _munge_whitespace(text : string) -> string          Munge whitespace in text:, _split(text : string) -> [string]          Split the text to wrap into indivis, _fix_sentence_endings(chunks : [string])          Correct for sentence endings, _handle_long_word(chunks : [string],                             cur_line : [st, Object for wrapping/filling text.  The public interface consists of     the wra, _wrap_chunks(chunks : [string]) -> [string]          Wrap a sequence of text c (+9 more)

### Community 24 - "Community 24"
Cohesion: 0.31
Nodes (2): MCarousel, MGuidPrivate

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (1): MForm

### Community 26 - "Community 26"
Cohesion: 0.4
Nodes (2): MTabBar, MTabWidget

### Community 27 - "Community 27"
Cohesion: 0.33
Nodes (5): DetResult, OCRResult, Detection result: polygons (N,4,2) int32 and scores length N., RecLine, RecResult

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (2): MDockWidget, Just apply the qss. No more extend.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): TransformerConfig

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Process the loading queue.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Create RectState from a MoveableRectItem

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Determines the placement rule for a character.          Returns:

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Create a MAvatar with huge size

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Create a MAvatar with large size

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Create a MAvatar with medium size

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Create a MAvatar with small size

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Create a MAvatar with tiny size

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Create a Badge with dot style.         :param show: bool         :param widget

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Create a Badge with number style.         :param count: int         :param wid

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Create a Badge with text style.         :param text: six.string_types

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Create a MLoading with huge size

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Create a MLoading with large size

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Create a MLoading with medium size

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Create a MLoading with small size

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Create a MLoading with tiny size

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Returns vocabulary (=list of characters)

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (0): 

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (0): 

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (0): 

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (0): 

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Ensure model is present then return absolute paths to all its files.

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Return the first file path for a model (common for single-file specs).

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Ensure model is present then return the absolute path for the requested file_nam

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Return a dict mapping each declared filename to its absolute path (ensures downl

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Return True if all files for the model exist and match provided checksums (when

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Check if this is the first virtual page of the physical page.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Check if this is the last virtual page of the physical page.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (0): 

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (0): 

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (0): 

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Manage memory by unloading images that are no longer needed.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Force load an image immediately (for current selection).

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Shutdown the loader and clean up resources.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Add an image to the loading queue.

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Clear the loading queue.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Process the loading queue.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Load and resize an image to the target size.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Lazy image loader for QListWidget that loads thumbnails only when visible.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Set the file paths and card references for lazy loading.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Handle scroll events with debouncing.

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Schedule an update of visible items.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Update which items are visible and manage loading/unloading.

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Get indices of currently visible items.

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Queue an image for loading.

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Handle when an image has been loaded.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Manage memory by unloading images that are no longer needed.

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Force load an image immediately (for current selection).

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Shutdown the loader and clean up resources.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Return True if this block should be rendered vertically.

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Return True if this block should be rendered vertically.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Check if the language usually does not use spaces between words.     Includes:

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Heuristic for scripts that are typically written without spaces.

## Knowledge Gaps
- **665 isolated node(s):** `Checks for updates on GitHub and handles downloading/running installers.`, `Starts the check in a background thread.`, `Starts the download in a background thread.`, `Executes the installer based on the platform.`, `Stops any active worker thread (best-effort).` (+660 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 29`** (2 nodes): `main()`, `main.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (2 nodes): `TransformerConfig`, `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `version.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Process the loading queue.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Create RectState from a MoveableRectItem`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Determines the placement rule for a character.          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Create a MAvatar with huge size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Create a MAvatar with large size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Create a MAvatar with medium size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Create a MAvatar with small size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Create a MAvatar with tiny size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Create a Badge with dot style.         :param show: bool         :param widget`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Create a Badge with number style.         :param count: int         :param wid`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Create a Badge with text style.         :param text: six.string_types`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Create a MLoading with huge size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Create a MLoading with large size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Create a MLoading with medium size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Create a MLoading with small size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Create a MLoading with tiny size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `__version__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Returns vocabulary (=list of characters)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `image_util.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Ensure model is present then return absolute paths to all its files.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Return the first file path for a model (common for single-file specs).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Ensure model is present then return the absolute path for the requested file_nam`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Return a dict mapping each declared filename to its absolute path (ensures downl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Return True if all files for the model exist and match provided checksums (when`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Check if this is the first virtual page of the physical page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Check if this is the last virtual page of the physical page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `ct_de.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `ct_es.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `ct_fr.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `ct_it.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `ct_ja.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `ct_ko.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `ct_ru.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `ct_tr.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `ct_zh-CN.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Manage memory by unloading images that are no longer needed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Force load an image immediately (for current selection).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Shutdown the loader and clean up resources.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Add an image to the loading queue.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Clear the loading queue.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Process the loading queue.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Load and resize an image to the target size.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Lazy image loader for QListWidget that loads thumbnails only when visible.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Set the file paths and card references for lazy loading.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Handle scroll events with debouncing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Schedule an update of visible items.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Update which items are visible and manage loading/unloading.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Get indices of currently visible items.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Queue an image for loading.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Handle when an image has been loaded.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Manage memory by unloading images that are no longer needed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Force load an image immediately (for current selection).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Shutdown the loader and clean up resources.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Return True if this block should be rendered vertically.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Return True if this block should be rendered vertically.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Check if the language usually does not use spaces between words.     Includes:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Heuristic for scripts that are typically written without spaces.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 14`, `Community 15`, `Community 18`, `Community 20`?**
  _High betweenness centrality (0.182) - this node is a cross-community bridge._
- **Why does `TextBlock` connect `Community 8` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 11`, `Community 12`, `Community 15`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `ComicTranslate` connect `Community 4` to `Community 0`, `Community 1`, `Community 3`, `Community 6`, `Community 8`, `Community 9`, `Community 11`, `Community 12`, `Community 14`, `Community 18`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 389 inferred relationships involving `get()` (e.g. with `get_system_language()` and `load_translation()`) actually correct?**
  _`get()` has 389 INFERRED edges - model-reasoned connections that need verification._
- **Are the 272 inferred relationships involving `TextBlock` (e.g. with `ComicTranslate` and `Wrap thread_load_images with unsaved-project confirmation and clear state.`) actually correct?**
  _`TextBlock` has 272 INFERRED edges - model-reasoned connections that need verification._
- **Are the 133 inferred relationships involving `TextBlockItem` (e.g. with `ComicTranslate` and `Wrap thread_load_images with unsaved-project confirmation and clear state.`) actually correct?**
  _`TextBlockItem` has 133 INFERRED edges - model-reasoned connections that need verification._
- **Are the 166 inferred relationships involving `MToolButton` (e.g. with `SearchReplacePanel` and `VS Code-inspired search/replace sidebar for MTPE.      Public attributes used`) actually correct?**
  _`MToolButton` has 166 INFERRED edges - model-reasoned connections that need verification._