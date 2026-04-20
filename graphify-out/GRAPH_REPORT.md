# Graph Report - .  (2026-04-21)

## Corpus Check
- 343 files · ~509,114 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 5270 nodes · 14947 edges · 82 communities detected
- Extraction: 48% EXTRACTED · 52% INFERRED · 0% AMBIGUOUS · INFERRED: 7712 edges (avg confidence: 0.68)
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

## God Nodes (most connected - your core abstractions)
1. `get()` - 369 edges
2. `TextBlock` - 243 edges
3. `MToolButton` - 185 edges
4. `TextBlockItem` - 179 edges
5. `MLabel` - 145 edges
6. `ComicTranslate` - 132 edges
7. `ImageViewer` - 118 edges
8. `MPushButton` - 105 edges
9. `SettingsPage` - 85 edges
10. `AuthClient` - 79 edges

## Surprising Connections (you probably didn't know these)
- `Do the heavy loading in background thread.` --uses--> `ComicTranslate`  [INFERRED]
  comic.py → controller.py
- `ComicTranslate` --uses--> `Switch to memory-efficient lazy loading webtoon mode.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Connect events for lazy loading triggers.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `ComicTranslate` --uses--> `Called when the lazy manager has completed initialization.`  [INFERRED]
  controller.py → app\controllers\webtoons.py
- `MoveableRectItem` --uses--> `Load rectangles for a specific page.`  [INFERRED]
  app\ui\canvas\rectangle.py → app\ui\canvas\webtoons\scene_items\rectangle_manager.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (354): AboutPage, AccountPage, Show the logged out state., Show the logged in state., MAlert, Get MAlert feedback type.         :return: str, Get MAlert feedback message.         :return: six.string_types, Set MAlert to InfoType (+346 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (243): create_new_blk(), create_new_txt_item(), create_rect_item(), find_matching_blk(), find_matching_item(), find_matching_rect(), find_matching_txt_item(), invalidate_page_render_pipeline() (+235 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (152): Encode CV2/numpy image directly to base64 string using cv2.imencode., BatchReportController, BatchUiMixin, BatchReportStateMixin, BatchReportViewMixin, BatchUiMixin, Load brush strokes for a specific page., Update or add a single block's translation result to the cache. (+144 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (186): ABC, AOT, Input image and output image have same size         image: [H, W, C] RGB, resize_keep_aspect(), DiffusionInpaintModel, forward(), init_model(), InpaintModel (+178 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (179): AuthClient, Starts the new authentication flow., Handles the tokens and user info received from the backend via the local server., Handles errors emitted by the AuthServerThread., Called when the AuthServerThread finishes execution., Safely attempts to clear server thread reference., Clean up threads before application exit., Cancels the currently active authentication flow. (+171 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (145): create_patch_item(), BatchExecutionMixin, _is_recoverable_translation_error(), _merge_usage_stats(), BatchProcessor, PreparedBatchPage, BatchStateMixin, BatchExecutionMixin (+137 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (106): create_path_item(), PathCommandBase, save_path_properties(), BrushStrokeCommand, ClearBrushStrokesCommand, EraseUndoCommand, Restore the scene to match the target state by comparing with current state., SegmentBoxesCommand (+98 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (163): DetectionEngine, LLMTranslation, Translate text blocks using LLM.                  Args:             blk_list: Li, Abstract base class for all detection engines.     Each model implementation sh, Initialize the translation engine with necessary parameters.                  Ar, Perform translation using specific LLM.                  Args:             user_, Initialize the OCR engine with necessary parameters.                  Args:, Detect text blocks in an image.                  Args:             image: Inpu (+155 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (132): BaseLLMTranslation, detect(), initialize(), _merge_usage_snapshots(), _perform_translation(), Abstract base class for all translation engines.     Defines common interface an, Base class for LLM-based translation engines with shared functionality., Get standardized language code from language name.                  Args: (+124 more)

### Community 9 - "Community 9"
Cohesion: 0.02
Nodes (142): extract_archive(), _get_cached_pdf(), is_image_file(), list_archive_image_entries(), make(), make_cb7(), make_cbz(), make_pdf() (+134 more)

### Community 10 - "Community 10"
Cohesion: 0.01
Nodes (177): _as_mask(), bounding_rect(), contour_area(), draw_contours(), find_contours(), get_perspective_transform(), mean(), Image analysis operations for the imkit module. (+169 more)

### Community 11 - "Community 11"
Cohesion: 0.03
Nodes (37): MFlowLayout, FlowLayout, the code is come from PySide/examples/layouts/flowlayout.py     I c, EdgeResizer, _edges_at(), Return a Qt.Edges flag for whichever window edges *gpos* is within *margin* pixe, Event filter that provides edge resize cursors and startSystemResize for framele, PageListView, Handle selection changes and emit signal with selected indices. (+29 more)

### Community 12 - "Community 12"
Cohesion: 0.04
Nodes (54): CharacterStyle, FontKey, FontMetricsCache, get_rule(), GlyphPlacement, PlacementRule, High accuracy method using QPainterPath for text outline., Determines glyph placement rules for vertical text. (+46 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (56): get_available_langs(), get_available_models(), get_default_model(), PororoBiencoderBase, PororoFactoryBase, PororoGenerationBase, PororoSimpleBase, PororoTaskBase (+48 more)

### Community 14 - "Community 14"
Cohesion: 0.03
Nodes (41): MDateEdit, MDateTimeEdit, MDoubleSpinBox, MTimeEdit, Set the MDoubleSpinBox size.         :param value: integer         :return: No, Set MDoubleSpinBox to huge size, Set MDoubleSpinBox to large size, Set MDoubleSpinBox to  medium (+33 more)

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (42): count(), dot(), MBadge, Set current style to show a number          :param num: int         :return:, Get current showed text         :return: six.string_types, Set current style to show a text.         :param text: six.string_types, Badge normally appears in proximity to notifications or user avatars with eye-ca, Get current overflow number         :return: int (+34 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (44): encode_image(), _decode_ipc_messages(), _encode_ipc_message(), _extract_project_file(), FileOpenEventFilter, get_system_language(), LoadingWorker, main() (+36 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (23): MComboBoxSearchMixin, MFontComboBox, Set the avatar size.         :param value: integer         :return: None, Override setView to flag _has_custom_view variable., Override default showPopup. When set custom menu, show the menu instead., Set MComboBox to huge size, Set MComboBox to large size, Set MComboBox to  medium (+15 more)

### Community 18 - "Community 18"
Cohesion: 0.07
Nodes (27): is_close(), Restart the application.     Works for both running as script and compiled exec, restart_application(), SearchReplaceApplyMixin, _apply_preserve_case(), _apply_replacements_to_html(), _apply_text_delta_to_document(), BlockKey (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (29): init_weights(), Vgg16BN, CRAFT, DoubleConv, This code is adapted from https://github.com/clovaai/CRAFT-pytorch/blob/master/c, BasicBlock, BidirectionalLSTM, GridGenerator (+21 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (27): BasicBlock, FeatureExtractor of FAN     (http://openaccess.thecvf.com/content_ICCV_2017/pap, 3x3 convolution with padding, :param n_input_channels (int): The number of input channels of the feature extra, FeatureExtractor of CRNN (https://arxiv.org/pdf/1507.05717.pdf), ResNet, ResNetFeatureExtractor, VGGFeatureExtractor (+19 more)

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (8): _fmt_date(), _NewCard, _PillButton, Rebuild rows from [{path, mtime}, …] list (newest modified first)., Emit via sig so controller can clear state & show home., _RecentRow, StartupHomeScreen, _valid_urls()

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (15): MExpandingTextEdit, Handle Enter key to emit returnPressed signal., Return the plain text content (QLineEdit compatibility)., Set the plain text content (QLineEdit compatibility)., Clear the text content., Get placeholder text., A plain text edit that:     - Starts with single-line height     - Expands ver, Recalculate height when widget is resized. (+7 more)

### Community 23 - "Community 23"
Cohesion: 0.1
Nodes (17): dedent(), indent(), _munge_whitespace(text : string) -> string          Munge whitespace in text:, _split(text : string) -> [string]          Split the text to wrap into indivis, _fix_sentence_endings(chunks : [string])          Correct for sentence endings, _handle_long_word(chunks : [string],                             cur_line : [st, Object for wrapping/filling text.  The public interface consists of     the wra, _wrap_chunks(chunks : [string]) -> [string]          Wrap a sequence of text c (+9 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (3): MPopup, MTabBar, MTabWidget

### Community 25 - "Community 25"
Cohesion: 0.31
Nodes (2): MCarousel, MGuidPrivate

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

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Check if the language usually does not use spaces between words.     Includes:

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Heuristic for scripts that are typically written without spaces.

## Knowledge Gaps
- **608 isolated node(s):** `Checks for updates on GitHub and handles downloading/running installers.`, `Starts the check in a background thread.`, `Starts the download in a background thread.`, `Executes the installer based on the platform.`, `Stops any active worker thread (best-effort).` (+603 more)
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
- **Thin community `Community 80`** (1 nodes): `Check if the language usually does not use spaces between words.     Includes:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Heuristic for scripts that are typically written without spaces.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 9` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 15`, `Community 16`, `Community 18`, `Community 21`?**
  _High betweenness centrality (0.229) - this node is a cross-community bridge._
- **Why does `TextBlock` connect `Community 7` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 8`, `Community 10`, `Community 12`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `ComicTranslate` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 16`, `Community 18`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 361 inferred relationships involving `get()` (e.g. with `get_system_language()` and `load_translation()`) actually correct?**
  _`get()` has 361 INFERRED edges - model-reasoned connections that need verification._
- **Are the 229 inferred relationships involving `TextBlock` (e.g. with `ComicTranslate` and `Wrap thread_load_images with unsaved-project confirmation and clear state.`) actually correct?**
  _`TextBlock` has 229 INFERRED edges - model-reasoned connections that need verification._
- **Are the 166 inferred relationships involving `MToolButton` (e.g. with `SearchReplacePanel` and `VS Code-inspired search/replace sidebar for MTPE.      Public attributes used`) actually correct?**
  _`MToolButton` has 166 INFERRED edges - model-reasoned connections that need verification._
- **Are the 113 inferred relationships involving `TextBlockItem` (e.g. with `ComicTranslate` and `Wrap thread_load_images with unsaved-project confirmation and clear state.`) actually correct?**
  _`TextBlockItem` has 113 INFERRED edges - model-reasoned connections that need verification._