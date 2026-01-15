import os
import numpy as np
import shutil
import tempfile
from typing import Callable, Tuple

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QCoreApplication, QThreadPool
from PySide6.QtGui import QUndoGroup, QUndoStack

from app.ui.dayu_widgets.qt import MPixmap
from app.ui.main_window import ComicTranslateUI
from app.ui.messages import Messages
from app.ui.dayu_widgets.message import MMessage
from app.thread_worker import GenericWorker

from app.ui.canvas.text_item import TextBlockItem
from app.ui.commands.box import DeleteBoxesCommand

from modules.utils.textblock import TextBlock
from modules.utils.file_handler import FileHandler
from modules.utils.pipeline_utils import validate_settings, validate_ocr, \
                                         validate_translator
from modules.utils.download import mandatory_models, set_download_callback, ensure_mandatory_models
from modules.detection.utils.content import get_inpaint_bboxes
from modules.utils.translator_utils import is_there_text
from modules.rendering.render import pyside_word_wrap
from modules.utils.pipeline_utils import get_language_code, is_close
from modules.utils.translator_utils import format_translations
from pipeline.main_pipeline import ComicTranslatePipeline
from pipeline.webtoon_utils import get_visible_text_items, get_first_visible_block

from app.controllers.image import ImageStateController
from app.controllers.rect_item import RectItemController
from app.controllers.projects import ProjectController
from app.controllers.text import TextController
from app.controllers.webtoons import WebtoonController
from collections import deque


# Ensure any pre-declared mandatory models
ensure_mandatory_models()

class ComicTranslate(ComicTranslateUI):
    image_processed = QtCore.Signal(int, object, str)
    patches_processed = QtCore.Signal(list, str)
    progress_update = QtCore.Signal(int, int, int, int, bool)
    image_skipped = QtCore.Signal(str, str, str)
    blk_rendered = QtCore.Signal(str, int, object)
    download_event = QtCore.Signal(str, str)  # status, name

    def __init__(self, parent=None):
        super(ComicTranslate, self).__init__(parent)
        self.setWindowTitle("Project1.ctpr[*]")

        self.blk_list: list[TextBlock] = []   
        self.curr_tblock: TextBlock = None
        self.curr_tblock_item: TextBlockItem = None     

        self.image_files = []
        self.selected_batch = []
        self.curr_img_idx = -1
        self.image_states = {}
        self.image_data = {}  # Store the latest version of each image
        self.image_history = {}  # Store file path history for all images
        self.in_memory_history = {}  # Store image history for recent images
        self.current_history_index = {}  # Current position in the history for each image
        self.displayed_images = set()  # Set to track displayed images
        self.image_patches = {}  # Store patches for each image
        self.in_memory_patches = {}  # Store patches in memory for each image
        self.image_cards = []
        self.current_card = None
        self.max_images_in_memory = 10
        self.loaded_images = []

        self.undo_group = QUndoGroup(self)
        self.undo_stacks: dict[str, QUndoStack] = {}
        self.project_file = None
        self.temp_dir = tempfile.mkdtemp()
        self._manual_dirty = False
        self._skip_close_prompt = False

        self.pipeline = ComicTranslatePipeline(self)
        self.file_handler = FileHandler()
        self.threadpool = QThreadPool()
        self.current_worker = None

        self.image_ctrl = ImageStateController(self)
        self.rect_item_ctrl = RectItemController(self)
        self.project_ctrl = ProjectController(self)
        self.text_ctrl = TextController(self)
        self.webtoon_ctrl = WebtoonController(self)

        self.image_skipped.connect(self.image_ctrl.on_image_skipped)
        self.image_processed.connect(self.image_ctrl.on_image_processed)
        self.patches_processed.connect(self.image_ctrl.on_inpaint_patches_processed)
        self.progress_update.connect(self.update_progress)
        self.blk_rendered.connect(self.text_ctrl.on_blk_rendered)
        self.download_event.connect(self.on_download_event)

        self.connect_ui_elements()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.project_ctrl.load_main_page_settings()
        self.settings_page.load_settings()

        self.operation_queue = deque()
        self.is_processing_queue = False
        self._processing_page_change = False  # Flag to prevent recursive page change handling

        # Hook the global download callback so utils can notify us
        def _dl_cb(status: str, name: str):
            # Ensure cross-thread safe emit
            try:
                self.download_event.emit(status, name)
            except Exception:
                pass
        set_download_callback(_dl_cb)

    def connect_ui_elements(self):
        # Browsers
        self.image_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.document_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.archive_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.comic_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.project_browser_button.sig_file_changed.connect(self.project_ctrl.thread_load_project)
        self.insert_browser_button.sig_files_changed.connect(self.image_ctrl.thread_insert)

        self.save_browser.sig_file_changed.connect(self.image_ctrl.save_current_image)
        self.save_all_browser.sig_file_changed.connect(self.project_ctrl.save_and_make)
        self.save_project_button.clicked.connect(self.project_ctrl.thread_save_project)
        self.save_as_project_button.clicked.connect(self.project_ctrl.thread_save_as_project)
        self.drag_browser.sig_files_changed.connect(self._guarded_thread_load_images)
       
        self.manual_radio.clicked.connect(self.manual_mode_selected)
        self.automatic_radio.clicked.connect(self.batch_mode_selected)
        
        # Webtoon mode toggle
        self.webtoon_toggle.clicked.connect(self.webtoon_ctrl.toggle_webtoon_mode)

        # Connect buttons from button_groups
        self.hbutton_group.get_button_group().buttons()[0].clicked.connect(lambda: self.block_detect())
        self.hbutton_group.get_button_group().buttons()[1].clicked.connect(self.ocr)
        self.hbutton_group.get_button_group().buttons()[2].clicked.connect(self.translate_image)
        self.hbutton_group.get_button_group().buttons()[3].clicked.connect(self.load_segmentation_points)
        self.hbutton_group.get_button_group().buttons()[4].clicked.connect(self.inpaint_and_set)
        self.hbutton_group.get_button_group().buttons()[5].clicked.connect(self.text_ctrl.render_text)

        self.undo_tool_group.get_button_group().buttons()[0].clicked.connect(self.undo_group.undo)
        self.undo_tool_group.get_button_group().buttons()[1].clicked.connect(self.undo_group.redo)

        # Connect other buttons and widgets
        self.translate_button.clicked.connect(self.start_batch_process)
        self.cancel_button.clicked.connect(self.cancel_current_task)
        self.set_all_button.clicked.connect(self.text_ctrl.set_src_trg_all)
        self.clear_rectangles_button.clicked.connect(self.image_viewer.clear_rectangles)
        self.clear_brush_strokes_button.clicked.connect(self.image_viewer.clear_brush_strokes)
        self.draw_blklist_blks.clicked.connect(lambda: self.pipeline.load_box_coords(self.blk_list))
        self.change_all_blocks_size_dec.clicked.connect(lambda: self.text_ctrl.change_all_blocks_size(-int(self.change_all_blocks_size_diff.text())))
        self.change_all_blocks_size_inc.clicked.connect(lambda: self.text_ctrl.change_all_blocks_size(int(self.change_all_blocks_size_diff.text())))
        self.delete_button.clicked.connect(self.delete_selected_box)

        # Connect text edit widgets
        self.s_text_edit.textChanged.connect(self.text_ctrl.update_text_block)
        self.t_text_edit.textChanged.connect(self.text_ctrl.update_text_block_from_edit)

        self.s_combo.currentTextChanged.connect(self.text_ctrl.save_src_trg)
        self.t_combo.currentTextChanged.connect(self.text_ctrl.save_src_trg)

        # Connect image viewer signals for both modes
        self.image_viewer.rectangle_selected.connect(self.rect_item_ctrl.handle_rectangle_selection)
        self.image_viewer.rectangle_created.connect(self.rect_item_ctrl.handle_rectangle_creation)
        self.image_viewer.rectangle_deleted.connect(self.rect_item_ctrl.handle_rectangle_deletion)
        self.image_viewer.command_emitted.connect(self.push_command)
        self.image_viewer.connect_rect_item.connect(self.rect_item_ctrl.connect_rect_item_signals)
        self.image_viewer.connect_text_item.connect(self.text_ctrl.connect_text_item_signals)
        self.image_viewer.page_changed.connect(self.webtoon_ctrl.on_page_changed)
        self.image_viewer.clear_text_edits.connect(self.text_ctrl.clear_text_edits)

        # Rendering
        self.font_dropdown.currentTextChanged.connect(self.text_ctrl.on_font_dropdown_change)
        self.font_size_dropdown.currentTextChanged.connect(self.text_ctrl.on_font_size_change)
        self.line_spacing_dropdown.currentTextChanged.connect(self.text_ctrl.on_line_spacing_change)
        self.block_font_color_button.clicked.connect(self.text_ctrl.on_font_color_change)
        self.alignment_tool_group.get_button_group().buttons()[0].clicked.connect(self.text_ctrl.left_align)
        self.alignment_tool_group.get_button_group().buttons()[1].clicked.connect(self.text_ctrl.center_align)
        self.alignment_tool_group.get_button_group().buttons()[2].clicked.connect(self.text_ctrl.right_align)
        self.bold_button.clicked.connect(self.text_ctrl.bold)
        self.italic_button.clicked.connect(self.text_ctrl.italic)
        self.underline_button.clicked.connect(self.text_ctrl.underline)
        self.outline_font_color_button.clicked.connect(self.text_ctrl.on_outline_color_change)
        self.outline_width_dropdown.currentTextChanged.connect(self.text_ctrl.on_outline_width_change)
        self.outline_checkbox.stateChanged.connect(self.text_ctrl.toggle_outline_settings)

        # Page List
        self.page_list.currentItemChanged.connect(self.image_ctrl.on_card_selected)
        self.page_list.selection_changed.connect(self.image_ctrl.on_selection_changed)
        self.page_list.del_img.connect(self.image_ctrl.handle_image_deletion)
        self.page_list.insert_browser.sig_files_changed.connect(self.image_ctrl.thread_insert)
        self.page_list.toggle_skip_img.connect(self.image_ctrl.handle_toggle_skip_images)
        self.page_list.translate_imgs.connect(self.batch_translate_selected)

        # New project and safety confirmations
        self.new_project_button.clicked.connect(self._on_new_project_clicked)

    def _guarded_thread_load_images(self, paths: list[str]):
        """Wrap thread_load_images with unsaved-project confirmation and clear state."""
        if not self._confirm_start_new_project():
            return
        self.image_ctrl.thread_load_images(paths)

    def _on_new_project_clicked(self):
        """Clear the app to initial state after confirmation."""
        if not self._confirm_start_new_project():
            return
        # Clear state and show the drag area
        self.image_ctrl.clear_state()
        self.central_stack.setCurrentWidget(self.drag_browser)
        # Reset webtoon mode UI state
        if self.webtoon_mode:
            self.webtoon_toggle.setChecked(False)
        self.webtoon_mode = False

    def connect_rect_item_signals(self, rect_item): return self.rect_item_ctrl.connect_rect_item_signals(rect_item)
    def apply_inpaint_patches(self, patches): return self.image_ctrl.apply_inpaint_patches(patches)
    def render_settings(self): return self.text_ctrl.render_settings()
    def load_image(self, file_path: str) -> np.ndarray: return self.image_ctrl.load_image(file_path)

    def _any_undo_dirty(self) -> bool:
        for stack in self.undo_stacks.values():
            try:
                if stack and not stack.isClean():
                    return True
            except Exception:
                continue
        return False

    def has_unsaved_changes(self) -> bool:
        return bool(self._manual_dirty) or self._any_undo_dirty()

    def mark_project_dirty(self):
        self._manual_dirty = True
        self._update_window_modified()

    def set_project_clean(self):
        self._manual_dirty = False
        for stack in self.undo_stacks.values():
            try:
                stack.setClean()
            except Exception:
                continue
        self._update_window_modified()

    def _update_window_modified(self):
        try:
            self.setWindowModified(self.has_unsaved_changes())
        except Exception:
            pass

    def _finish_close_after_save(self):
        self._skip_close_prompt = True
        self.close()

    def push_command(self, command):
        if self.undo_group.activeStack():
            self.undo_group.activeStack().push(command)

    def delete_selected_box(self):
        if self.curr_tblock:
            # Create and push the delete command
            command = DeleteBoxesCommand(
                self,
                self.image_viewer.selected_rect,
                self.curr_tblock_item,
                self.curr_tblock,
                self.blk_list,
            )
            self.undo_group.activeStack().push(command)

    def batch_mode_selected(self):
        self.disable_hbutton_group()
        self.translate_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def manual_mode_selected(self):
        self.enable_hbutton_group()
        self.translate_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def on_manual_finished(self):
        self.loading.setVisible(False)
        self.enable_hbutton_group()

    def run_threaded(self, callback: Callable, result_callback: Callable=None, 
                    error_callback: Callable=None, finished_callback: Callable=None, 
                    *args, **kwargs):
        """
        Enhanced run_threaded with automatic queuing for top-level calls
        """
        return self._queue_operation(
            callback, result_callback, error_callback, finished_callback,
            *args, **kwargs
        )

    def _queue_operation(self, callback: Callable, result_callback: Callable=None, 
                        error_callback: Callable=None, finished_callback: Callable=None, 
                        *args, **kwargs):
        """Queue an operation for sequential execution"""
        operation = {
            'callback': callback,
            'result_callback': result_callback,
            'error_callback': error_callback,
            'finished_callback': finished_callback,
            'args': args,
            'kwargs': kwargs,
        }
        
        self.operation_queue.append(operation)
        
        if not self.is_processing_queue:
            self._process_next_operation()

    def _process_next_operation(self):
        """
        Process the next operation in the queue
        """
        if not self.operation_queue:
            self.is_processing_queue = False
            return
            
        self.is_processing_queue = True
        operation = self.operation_queue.popleft()
        
        # Create enhanced callbacks that handle queue processing

        def enhanced_finished_callback():
            # Call the original finished callback if it exists
            if operation['finished_callback']:
                operation['finished_callback']()
            
            # Process the next operation in the queue
            QtCore.QTimer.singleShot(0, self._process_next_operation)
        
        def enhanced_error_callback(error_tuple):
            # Call the original error callback if it exists
            if operation['error_callback']:
                operation['error_callback'](error_tuple)
            
            # Process the next operation in the queue even after error
            QtCore.QTimer.singleShot(0, self._process_next_operation)

        def enhanced_result_callback(result):
            # Call the original result callback if it exists
            if operation['result_callback']:
                operation['result_callback'](result)
        
        # Execute the operation
        self._execute_single_operation(
            operation['callback'],
            enhanced_result_callback,
            enhanced_error_callback,
            enhanced_finished_callback,
            *operation['args'],
            **operation['kwargs']
        )

    def _execute_single_operation(self, callback: Callable, result_callback: Callable=None, 
                                error_callback: Callable=None, finished_callback: Callable=None, 
                                *args, **kwargs):
        """
        Execute a single threaded operation (original run_threaded logic)
        """
        worker = GenericWorker(callback, *args, **kwargs)

        if result_callback:
            worker.signals.result.connect(lambda result: QtCore.QTimer.singleShot(0, lambda: result_callback(result)))
        if error_callback:
            worker.signals.error.connect(lambda error: QtCore.QTimer.singleShot(0, lambda: error_callback(error)))
        if finished_callback:
            worker.signals.finished.connect(finished_callback)
        
        self.current_worker = worker
        self.threadpool.start(worker)

    def run_threaded_immediate(self, callback: Callable, result_callback: Callable=None, 
                              error_callback: Callable=None, finished_callback: Callable=None, 
                              *args, **kwargs):
        """
        Run a threaded operation immediately without queuing (bypass the queue)
        Use this if you need the old behavior for specific operations
        """
        return self._execute_single_operation(callback, result_callback, error_callback, 
                                            finished_callback, *args, **kwargs)

    def clear_operation_queue(self):
        """Clear all pending operations in the queue"""
        self.operation_queue.clear()
        
    def cancel_current_task(self):
        """Enhanced cancel that also clears the queue"""
        if self.current_worker:
            self.current_worker.cancel()
        
        # Clear the queue and reset state
        self.clear_operation_queue()
        self.is_processing_queue = False

        # No need to Enable necessary Widgets/Buttons because the threads 
        # already have finish callbacks that handle this.

    def run_finish_only(self, finished_callback: Callable, error_callback: Callable = None):
        """
        Queue a no-op operation whose only effect is to invoke the finished_callback.
        """
        # 1) define a no-op function
        def _noop():
            pass

        # 2) hand it off to the existing queue machinery
        #    (this will wrap it in a GenericWorker and enqueue it)
        self._queue_operation(
            callback=_noop,
            result_callback=None,
            error_callback=error_callback,
            finished_callback=finished_callback
        )

    def default_error_handler(self, error_tuple: Tuple):
        exctype, value, traceback_str = error_tuple
        error_msg = f"An error occurred:\n{exctype.__name__}: {value}"
        error_msg_trcbk = f"An error occurred:\n{exctype.__name__}: {value}\n\nTraceback:\n{traceback_str}"
        print(error_msg_trcbk)
        Messages.show_error_with_copy(self, self.tr("Error"), error_msg, error_msg_trcbk)
        self.loading.setVisible(False)
        self.enable_hbutton_group()

    def start_batch_process(self):
        for image_path in self.image_files:
            source_lang = self.image_states[image_path]['source_lang']
            target_lang = self.image_states[image_path]['target_lang']

            if not validate_settings(self, source_lang, target_lang):
                return
            
        self.translate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # Choose batch processor based on webtoon mode
        if self.webtoon_mode:
            self.run_threaded(self.pipeline.webtoon_batch_process, None, self.default_error_handler, self.on_batch_process_finished)
        else:
            self.run_threaded(self.pipeline.batch_process, None, self.default_error_handler, self.on_batch_process_finished)

    def batch_translate_selected(self, selected_file_names: list[str]):
        # map base‐name back to full paths
        selected_paths = [
            p for p in self.image_files
            if os.path.basename(p) in selected_file_names
        ]
        if not selected_paths:
            return

        # validate each
        for path in selected_paths:
            src = self.image_states[path]['source_lang']
            tgt = self.image_states[path]['target_lang']
            if not validate_settings(self, src, tgt):
                return
            
        self.selected_batch = selected_paths

        # disable UI & run
        if self.manual_radio.isChecked():
            self.automatic_radio.setChecked(True)
            self.batch_mode_selected()
        self.translate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # Choose batch processor based on webtoon mode
        if self.webtoon_mode:
            # pass our subset into webtoon_batch_process
            self.run_threaded(
                lambda: self.pipeline.webtoon_batch_process(selected_paths),
                None,
                self.default_error_handler,
                self.on_batch_process_finished
            )
        else:
            # pass our subset into batch_process
            self.run_threaded(
                lambda: self.pipeline.batch_process(selected_paths),
                None,
                self.default_error_handler,
                self.on_batch_process_finished
            )

    def on_batch_process_finished(self):
        self.progress_bar.setVisible(False)
        self.translate_button.setEnabled(True)
        self.selected_batch = []
        Messages.show_translation_complete(self)

    def disable_hbutton_group(self):
        for button in self.hbutton_group.get_button_group().buttons():
            button.setEnabled(False)

    def enable_hbutton_group(self):
        for button in self.hbutton_group.get_button_group().buttons():
            button.setEnabled(True)

    def block_detect(self, load_rects: bool = True):
        self.loading.setVisible(True)
        self.disable_hbutton_group()
        self.run_threaded(self.pipeline.detect_blocks, self.pipeline.on_blk_detect_complete, 
                          self.default_error_handler, self.on_manual_finished, load_rects)

    def finish_ocr_translate(self, single_block=False):
        if self.blk_list:
            if single_block:
                rect = self.image_viewer.selected_rect
            else:
                # In webtoon mode, use first visible block instead of just first block
                if self.webtoon_mode:
                    first_block = get_first_visible_block(self.blk_list, self.image_viewer)
                    if first_block is None:
                        first_block = self.blk_list[0]  # Fallback to first block if no visible blocks
                else:
                    first_block = self.blk_list[0]
                rect = self.rect_item_ctrl.find_corresponding_rect(first_block, 0.5)
            self.image_viewer.select_rectangle(rect) 
        self.set_tool('box')
        self.on_manual_finished()

    def ocr(self, single_block=False):
        source_lang = self.s_combo.currentText()
        if not validate_ocr(self, source_lang):
            return
        self.loading.setVisible(True)
        self.disable_hbutton_group()
        
        # Handle webtoon mode specially for visible area OCR
        if self.webtoon_mode:
            self.run_threaded(
                lambda: self.pipeline.OCR_webtoon_visible_area(single_block),
                None,
                self.default_error_handler,
                lambda: self.finish_ocr_translate(single_block)
            )
        else:
            self.run_threaded(
                lambda: self.pipeline.OCR_image(single_block),
                None,
                self.default_error_handler,
                lambda: self.finish_ocr_translate(single_block)
            )

    def translate_image(self, single_block=False):
        source_lang = self.s_combo.currentText()
        target_lang = self.t_combo.currentText()
        if not is_there_text(self.blk_list) or not validate_translator(self, source_lang, target_lang):
            return
        self.loading.setVisible(True)
        self.disable_hbutton_group()
        
        # Handle webtoon mode specially for visible area translation
        if self.webtoon_mode:
            self.run_threaded(
                lambda: self.pipeline.translate_webtoon_visible_area(single_block),
                None,
                self.default_error_handler,
                lambda: self.update_translated_text_items(single_block)
            )
        else:
            self.run_threaded(
                lambda: self.pipeline.translate_image(single_block),
                None,
                self.default_error_handler,
                lambda: self.update_translated_text_items(single_block)
            )

    def _get_visible_text_items(self):
        """Get text items that are currently visible in webtoon mode."""
        if not self.webtoon_mode:
            return self.image_viewer.text_items
        
        return get_visible_text_items(self.image_viewer.text_items, self.image_viewer.webtoon_manager)

    def update_translated_text_items(self, single_blk: bool):
        def set_new_text(text_item, wrapped, font_size):
            if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja', 'th']):
                wrapped = wrapped.replace(' ', '')
            text_item.set_plain_text(wrapped)
            text_item.set_font_size(font_size)

        # Get visible text items instead of all text items
        text_items_to_process = self._get_visible_text_items()
        
        if not text_items_to_process:
            self.finish_ocr_translate(single_blk)
            return
        
        rs = self.render_settings()
        upper = rs.upper_case
        target_lang_en = self.lang_mapping.get(self.t_combo.currentText(), None)
        trg_lng_cd = get_language_code(target_lang_en)

        # This callback only runs **after** format_translations has finished.
        def on_format_finished():
            for text_item in text_items_to_process:
                text_item.handleDeselection()
                x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
                rot = text_item.rotation()
                
                blk = next(
                    (
                        b for b in self.blk_list
                        if is_close(b.xyxy[0], x1, 5) and 
                        is_close(b.xyxy[1], y1, 5) and 
                        is_close(b.angle, rot, 1)
                    ),
                    None
                )
                if not (blk and blk.translation):
                    continue

                wrap_args = (
                    blk.translation,
                    text_item.font_family,
                    blk.xyxy[2] - blk.xyxy[0],
                    blk.xyxy[3] - blk.xyxy[1],
                    float(text_item.line_spacing),
                    float(text_item.outline_width),
                    text_item.bold,
                    text_item.italic,
                    text_item.underline,
                    text_item.alignment,
                    text_item.direction,
                    rs.max_font_size,
                    rs.min_font_size,
                )

                # enqueue the word-wrap
                self.run_threaded(
                    pyside_word_wrap,
                    lambda wrap_res, ti=text_item: set_new_text(ti, wrap_res[0], wrap_res[1]),
                    self.default_error_handler,
                    None,
                    *wrap_args
                )

            # once all wraps are queued, finish off
            self.run_finish_only(
                finished_callback=self.on_manual_finished
            )

        # enqueue the formatter
        self.run_threaded(
            lambda: format_translations(self.blk_list, trg_lng_cd, upper_case=upper),
            None,                          
            self.default_error_handler,
            on_format_finished             
        )

    def inpaint_and_set(self):
        if self.image_viewer.hasPhoto() and self.image_viewer.has_drawn_elements():
            self.text_ctrl.clear_text_edits()
            self.loading.setVisible(True)
            self.disable_hbutton_group()
            self.undo_group.activeStack().beginMacro('inpaint')
            self.run_threaded(self.pipeline.inpaint, self.pipeline.inpaint_complete, 
                              self.default_error_handler, self.on_manual_finished)

    def blk_detect_segment(self, result): 
        # Handle both old (2-tuple) and new (3-tuple) result formats
        if len(result) == 3:
            blk_list, load_rects, _ = result
        else:
            blk_list, load_rects = result
        self.blk_list = blk_list
        self.undo_group.activeStack().beginMacro('draw_segmentation_boxes')
        for blk in self.blk_list:
            bboxes = blk.inpaint_bboxes
            if bboxes is not None and len(bboxes) > 0:
                self.image_viewer.draw_segmentation_lines(bboxes)
        self.undo_group.activeStack().endMacro()

    def load_segmentation_points(self):
        if self.image_viewer.hasPhoto():
            self.text_ctrl.clear_text_edits()
            self.set_tool('brush')
            self.disable_hbutton_group()
            self.image_viewer.clear_rectangles()
            self.image_viewer.clear_text_items()

            self.loading.setVisible(True)
            self.disable_hbutton_group()
            
            if self.blk_list:
                self.undo_group.activeStack().beginMacro('draw_segmentation_boxes')

                # Handle webtoon mode specially for visible area segmentation
                if self.webtoon_mode:
                    self.run_threaded(
                        lambda: self.pipeline.segment_webtoon_visible_area(),
                        self._on_segmentation_bboxes_ready,
                        self.default_error_handler,
                        self.on_manual_finished
                    )
                else:
                    def compute_all_bboxes():
                        image = self.image_viewer.get_image_array()
                        results = []
                        for blk in self.blk_list:
                            bboxes = get_inpaint_bboxes(blk.xyxy, image)
                            results.append((blk, bboxes))
                        return results

                    self.run_threaded(
                        compute_all_bboxes,
                        self._on_segmentation_bboxes_ready,
                        self.default_error_handler,
                        self.on_manual_finished
                    )

            else:
                self.run_threaded(
                    self.pipeline.detect_blocks, 
                    self.blk_detect_segment, 
                    self.default_error_handler, 
                    self.on_manual_finished)
                
    def _on_segmentation_bboxes_ready(self, results):
        # Handle results on the main thread
        for blk, bboxes in results:
            blk.inpaint_bboxes = bboxes
            if bboxes is not None and len(bboxes) > 0:
                self.image_viewer.draw_segmentation_lines(bboxes)
        self.undo_group.activeStack().endMacro()

    def update_progress(self, index: int, total_images: int, step: int, total_steps: int, change_name: bool):
        # Assign weights to image processing and archiving (adjust as needed)
        image_processing_weight = 0.9
        archiving_weight = 0.1

        archive_info_list = self.file_handler.archive_info
        total_archives = len(archive_info_list)
        image_list = self.selected_batch if self.selected_batch else self.image_files

        if change_name:
            if index < total_images:
                im_path = image_list[index]
                im_name = os.path.basename(im_path)
                self.progress_bar.setFormat(QCoreApplication.translate('Messages', 'Processing:') + f" {im_name} . . . %p%")
            else:
                archive_index = index - total_images
                self.progress_bar.setFormat(QCoreApplication.translate('Messages', 'Archiving:') + f" {archive_index + 1}/{total_archives} . . . %p%")

        if index < total_images:
            # Image processing progress
            task_progress = (index / total_images) * image_processing_weight
            step_progress = (step / total_steps) * (1 / total_images) * image_processing_weight
        else:
            # Archiving progress
            archive_index = index - total_images
            task_progress = image_processing_weight + (archive_index / total_archives) * archiving_weight
            step_progress = (step / total_steps) * (1 / total_archives) * archiving_weight

        progress = (task_progress + step_progress) * 100 
        self.progress_bar.setValue(int(progress))

    def on_download_event(self, status: str, name: str):
        """Show a loading-type MMessage while models/files are being downloaded."""
        # Keep a counter of active downloads to handle multiple files
        if not hasattr(self, "_active_downloads"):
            self._active_downloads = 0
        if not hasattr(self, "_download_message"):
            self._download_message = None

        if status == 'start':
            self._active_downloads += 1
            # Create a persistent loading message if not already shown
            if self._download_message is None:
                try:
                    # Extract just the filename and use it in the initial message
                    import os
                    filename = os.path.basename(name)
                    # Use a specific message with the filename
                    self._download_message = MMessage.loading(self.tr(f"Downloading model file: {filename}"), parent=self)
                except Exception:
                    # If loading message cannot be shown, do nothing; avoid touching global spinner here
                    pass
            else:
                # Optionally update text with the most recent file name
                try:
                    # Extract just the filename from the path/name and format the message
                    import os
                    filename = os.path.basename(name)
                    # Access the internal label to update text
                    self._download_message._content_label.setText(self.tr(f"Downloading model file: {filename}"))
                except Exception:
                    pass
        elif status == 'end':
            self._active_downloads = max(0, self._active_downloads - 1)
            if self._active_downloads == 0:
                # Close the loading message
                try:
                    if self._download_message is not None:
                        self._download_message.close()
                finally:
                    self._download_message = None
                # Do not change the main window loading spinner here; it's managed by the running task lifecycle

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Left:
            self.image_ctrl.navigate_images(-1)
        elif event.key() == QtCore.Qt.Key_Right:
            self.image_ctrl.navigate_images(1)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self.text_ctrl._commit_pending_text_command()
        except Exception:
            pass
        if not getattr(self, "_skip_close_prompt", False):
            if self.has_unsaved_changes():
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tr("Unsaved Changes"),
                    self.tr("Save changes to this file?"),
                    QtWidgets.QMessageBox.StandardButton.Save
                    | QtWidgets.QMessageBox.StandardButton.Discard
                    | QtWidgets.QMessageBox.StandardButton.Cancel,
                    QtWidgets.QMessageBox.StandardButton.Save
                )

                if reply == QtWidgets.QMessageBox.StandardButton.Save:
                    self.project_ctrl.thread_save_project(
                        post_save_callback=self._finish_close_after_save
                    )
                    event.ignore()
                    return
                if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
        else:
            self._skip_close_prompt = False

        # Save all settings when the application is closed
        self.settings_page.save_settings()
        self.project_ctrl.save_main_page_settings()
        self.image_ctrl.cleanup()
        
        # Delete temp archive folders
        for archive in self.file_handler.archive_info:
            temp_dir = archive['temp_dir']
            if os.path.exists(temp_dir): 
                shutil.rmtree(temp_dir)  

        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

        super().closeEvent(event)

