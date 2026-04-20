# Graph Report - .  (2026-04-19)

## Corpus Check
- 338 files · ~505,714 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 5163 nodes · 14540 edges · 80 communities detected
- Extraction: 49% EXTRACTED · 51% INFERRED · 0% AMBIGUOUS · INFERRED: 7473 edges (avg confidence: 0.67)
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

## God Nodes (most connected - your core abstractions)
1. `get()` - 359 edges
2. `TextBlock` - 239 edges
3. `MToolButton` - 185 edges
4. `TextBlockItem` - 161 edges
5. `MLabel` - 145 edges
6. `ComicTranslate` - 131 edges
7. `ImageViewer` - 117 edges
8. `MPushButton` - 105 edges
9. `SettingsPage` - 85 edges
10. `AuthClient` - 79 edges

## Surprising Connections (you probably didn't know these)
- `ComicTranslate` --uses--> `Switch to memory-efficient lazy loading webtoon mode.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Connect events for lazy loading triggers.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Called when the lazy manager has completed initialization.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `MoveableRectItem` --uses--> `Rectangle Manager for Webtoon Scene Items  Handles rectangle management with s`  [INFERRED]
  app\ui\canvas\rectangle.py → app\ui\canvas\webtoons\scene_items\rectangle_manager.py
- `MoveableRectItem` --uses--> `Manages rectangles for webtoon mode with lazy loading.`  [INFERRED]
  app\ui\canvas\rectangle.py → app\ui\canvas\webtoons\scene_items\rectangle_manager.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (300): AboutPage, AccountPage, Show the logged out state., Show the logged in state., MAlert, Get MAlert feedback type.         :return: str, Get MAlert feedback message.         :return: six.string_types, Set MAlert to InfoType (+292 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (144): create_rect_item(), find_matching_item(), Find an item in the scene matching the given properties, Save properties of a path item, Create a new rect item with given properties using the viewer's method, Find an item in the scene matching the given properties, Save TextBlockItem properties using the centralized TextItemProperties, Create a new TextBlockItem using the centralized add_text_item method (+136 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (132): BatchReportController, BatchUiMixin, BatchReportStateMixin, BatchReportViewMixin, BatchUiMixin, _encode_ipc_message(), _extract_project_file(), FileOpenEventFilter (+124 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (181): create_new_blk(), create_new_txt_item(), create_path_item(), find_matching_blk(), find_matching_rect(), find_matching_txt_item(), invalidate_page_render_pipeline(), PatchCommandBase (+173 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (163): extract_archive(), _get_cached_pdf(), is_image_file(), list_archive_image_entries(), make(), make_cb7(), make_cbz(), make_pdf() (+155 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (189): DetectionEngine, LLMTranslation, OCREngine, Translate text blocks using LLM.                  Args:             blk_list: Li, Abstract base class for all detection engines.     Each model implementation sh, Initialize the translation engine with necessary parameters.                  Ar, Base class for LLM-based translation engines with shared functionality., Perform translation using specific LLM.                  Args:             user_ (+181 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (153): AuthClient, Starts the new authentication flow., Handles the tokens and user info received from the backend via the local server., Handles errors emitted by the AuthServerThread., Called when the AuthServerThread finishes execution., Safely attempts to clear server thread reference., Clean up threads before application exit., Cancels the currently active authentication flow. (+145 more)

### Community 7 - "Community 7"
Cohesion: 0.01
Nodes (212): _as_mask(), bounding_rect(), contour_area(), draw_contours(), find_contours(), get_perspective_transform(), mean(), Image analysis operations for the imkit module. (+204 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (141): BaseLLMTranslation, detect(), initialize(), _merge_usage_snapshots(), _perform_translation(), Abstract base class for all translation engines.     Defines common interface an, Base class with shared functionality for rect-related commands, Get standardized language code from language name.                  Args: (+133 more)

### Community 9 - "Community 9"
Cohesion: 0.02
Nodes (121): ABC, AOT, Input image and output image have same size         image: [H, W, C] RGB, resize_keep_aspect(), DiffusionInpaintModel, forward(), init_model(), InpaintModel (+113 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (86): CoordinateConverter, Coordinate Converter for Webtoon Manager  Handles coordinate transformations b, Handles coordinate transformations for webtoon mode., Initializes the converter with references to the data owners.         This clas, Convert a scene-coordinate brush path to page-local coordinates., LazyImageLoader, Queue a page for loading., Memory-efficient image loader with lazy loading capabilities.     This class is (+78 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (83): BatchReportStateMixin, __init__(), MBaseButton, MDBPathButtons, parse_db_orm(), parse_path(), slot_action_clicked(), slot_button_clicked() (+75 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (47): huge(), large(), medium(), Set the avatar size.         :param value: integer         :return: None, Set avatar image.         :param value: QPixmap or None.         :return: None, small(), tiny(), _slot_context_menu() (+39 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (58): BatchProcessor, PreparedBatchPage, BatchRenderMixin, BatchStateMixin, BlockDetectionHandler, Handles text block detection and coordinate loading., CacheManager, Manages OCR and translation caching for the pipeline. (+50 more)

### Community 14 - "Community 14"
Cohesion: 0.03
Nodes (36): EdgeResizer, _edges_at(), Return a Qt.Edges flag for whichever window edges *gpos* is within *margin* pixe, Event filter that provides edge resize cursors and startSystemResize for framele, FullscreenResultPreview, PageListView, Handle selection changes and emit signal with selected indices., MainWindowBuildersMixin (+28 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (18): ensure_target_snapshot(), get_target_render_states(), set_target_snapshot(), _FakeController, _FakeImageController, _FakeSettingsPage, _FakeStageNav, _FakeTargetCombo (+10 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (55): get_available_langs(), get_available_models(), get_default_model(), PororoBiencoderBase, PororoFactoryBase, PororoGenerationBase, PororoSimpleBase, PororoTaskBase (+47 more)

### Community 17 - "Community 17"
Cohesion: 0.03
Nodes (41): MDateEdit, MDateTimeEdit, MDoubleSpinBox, MTimeEdit, Set the MDoubleSpinBox size.         :param value: integer         :return: No, Set MDoubleSpinBox to huge size, Set MDoubleSpinBox to large size, Set MDoubleSpinBox to  medium (+33 more)

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (23): MComboBoxSearchMixin, MFontComboBox, Set the avatar size.         :param value: integer         :return: None, Override setView to flag _has_custom_view variable., Override default showPopup. When set custom menu, show the menu instead., Set MComboBox to huge size, Set MComboBox to large size, Set MComboBox to  medium (+15 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (27): is_close(), Restart the application.     Works for both running as script and compiled exec, restart_application(), SearchReplaceApplyMixin, _apply_preserve_case(), _apply_replacements_to_html(), _apply_text_delta_to_document(), BlockKey (+19 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (31): Export cache contents in a project-serializable form., MCacheDict, close_state_store(), ensure_project_blob_materialized(), ensure_project_path_materialized(), _join_from_archive_relpath(), load_state_from_proj_file(), save_state_to_proj_file() (+23 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (28): init_weights(), Vgg16BN, DoubleConv, This code is adapted from https://github.com/clovaai/CRAFT-pytorch/blob/master/c, BasicBlock, BidirectionalLSTM, GridGenerator, init_weights() (+20 more)

### Community 22 - "Community 22"
Cohesion: 0.06
Nodes (16): MExpandingTextEdit, Handle Enter key to emit returnPressed signal., Return the plain text content (QLineEdit compatibility)., Set the plain text content (QLineEdit compatibility)., Clear the text content., Get placeholder text., Select all text (QLineEdit compatibility)., A plain text edit that:     - Starts with single-line height     - Expands ver (+8 more)

### Community 23 - "Community 23"
Cohesion: 0.09
Nodes (7): _fmt_date(), _NewCard, _PillButton, Emit via sig so controller can clear state & show home., _RecentRow, StartupHomeScreen, _valid_urls()

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (17): ImageLoadWorker, ListViewImageLoader, Worker thread for loading images in the background., Set the file paths and card references for lazy loading., Clear all loaded images and reset state., Handle scroll events with debouncing., Schedule an update of visible items., Update which items are visible and manage loading/unloading. (+9 more)

### Community 25 - "Community 25"
Cohesion: 0.1
Nodes (17): dedent(), indent(), _munge_whitespace(text : string) -> string          Munge whitespace in text:, _split(text : string) -> [string]          Split the text to wrap into indivis, _fix_sentence_endings(chunks : [string])          Correct for sentence endings, _handle_long_word(chunks : [string],                             cur_line : [st, Object for wrapping/filling text.  The public interface consists of     the wra, _wrap_chunks(chunks : [string]) -> [string]          Wrap a sequence of text c (+9 more)

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (1): MForm

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
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Create RectState from a MoveableRectItem

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Determines the placement rule for a character.          Returns:

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Create a MAvatar with huge size

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Create a MAvatar with large size

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Create a MAvatar with medium size

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Create a MAvatar with small size

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Create a MAvatar with tiny size

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Create a Badge with dot style.         :param show: bool         :param widget

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Create a Badge with number style.         :param count: int         :param wid

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Create a Badge with text style.         :param text: six.string_types

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Create a MLoading with huge size

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Create a MLoading with large size

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Create a MLoading with medium size

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Create a MLoading with small size

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Create a MLoading with tiny size

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

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
Nodes (1): Returns vocabulary (=list of characters)

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (0): 

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
Nodes (1): Ensure model is present then return absolute paths to all its files.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Return the first file path for a model (common for single-file specs).

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Ensure model is present then return the absolute path for the requested file_nam

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Return a dict mapping each declared filename to its absolute path (ensures downl

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Return True if all files for the model exist and match provided checksums (when

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Check if this is the first virtual page of the physical page.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Check if this is the last virtual page of the physical page.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (0): 

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

## Knowledge Gaps
- **599 isolated node(s):** `Checks for updates on GitHub and handles downloading/running installers.`, `Starts the check in a background thread.`, `Starts the download in a background thread.`, `Executes the installer based on the platform.`, `Stops any active worker thread (best-effort).` (+594 more)
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
- **Thin community `Community 34`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Create RectState from a MoveableRectItem`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Determines the placement rule for a character.          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Create a MAvatar with huge size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Create a MAvatar with large size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Create a MAvatar with medium size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Create a MAvatar with small size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Create a MAvatar with tiny size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Create a Badge with dot style.         :param show: bool         :param widget`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Create a Badge with number style.         :param count: int         :param wid`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Create a Badge with text style.         :param text: six.string_types`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Create a MLoading with huge size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Create a MLoading with large size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Create a MLoading with medium size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Create a MLoading with small size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Create a MLoading with tiny size`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `__version__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Returns vocabulary (=list of characters)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `image_util.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Ensure model is present then return absolute paths to all its files.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Return the first file path for a model (common for single-file specs).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Ensure model is present then return the absolute path for the requested file_nam`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Return a dict mapping each declared filename to its absolute path (ensures downl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Return True if all files for the model exist and match provided checksums (when`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Check if this is the first virtual page of the physical page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Check if this is the last virtual page of the physical page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `ct_de.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `ct_es.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `ct_fr.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `ct_it.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `ct_ja.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `ct_ko.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `ct_ru.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `ct_tr.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `ct_zh-CN.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 13`, `Community 14`, `Community 15`, `Community 16`, `Community 19`, `Community 20`, `Community 23`?**
  _High betweenness centrality (0.211) - this node is a cross-community bridge._
- **Why does `TextBlock` connect `Community 5` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 13`, `Community 15`, `Community 16`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `MToolButton` connect `Community 0` to `Community 1`, `Community 2`, `Community 12`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 351 inferred relationships involving `get()` (e.g. with `get_system_language()` and `load_translation()`) actually correct?**
  _`get()` has 351 INFERRED edges - model-reasoned connections that need verification._
- **Are the 225 inferred relationships involving `TextBlock` (e.g. with `ComicTranslate` and `Wrap thread_load_images with unsaved-project confirmation and clear state.`) actually correct?**
  _`TextBlock` has 225 INFERRED edges - model-reasoned connections that need verification._
- **Are the 166 inferred relationships involving `MToolButton` (e.g. with `SearchReplacePanel` and `VS Code-inspired search/replace sidebar for MTPE.      Public attributes used`) actually correct?**
  _`MToolButton` has 166 INFERRED edges - model-reasoned connections that need verification._
- **Are the 98 inferred relationships involving `TextBlockItem` (e.g. with `ComicTranslate` and `Wrap thread_load_images with unsaved-project confirmation and clear state.`) actually correct?**
  _`TextBlockItem` has 98 INFERRED edges - model-reasoned connections that need verification._