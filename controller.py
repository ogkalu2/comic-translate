import os
import numpy as np
import shutil
import tempfile
from typing import Callable, Tuple

from PySide6 import QtWidgets
from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication, QThreadPool
from PySide6.QtGui import QUndoGroup, QUndoStack

from app.ui.dayu_widgets.qt import MPixmap
from app.ui.main_window import ComicTranslateUI
from app.ui.messages import Messages
from app.thread_worker import GenericWorker

from app.ui.canvas.text_item import TextBlockItem
from app.ui.commands.box import DeleteBoxesCommand

from modules.utils.textblock import TextBlock
from modules.utils.file_handler import FileHandler
from modules.utils.pipeline_utils import validate_settings, validate_ocr, \
                                         validate_translator
from modules.utils.download import get_models, mandatory_models
from modules.detection.utils.general import get_inpaint_bboxes
from modules.utils.translator_utils import is_there_text
from modules.rendering.render import pyside_word_wrap
from modules.utils.pipeline_utils import get_language_code
from modules.utils.translator_utils import format_translations
from pipeline import ComicTranslatePipeline

from app.controllers.image import ImageStateController
from app.controllers.rect_item import RectItemController
from app.controllers.projects import ProjectController
from app.controllers.text import TextController
from collections import deque


for model in mandatory_models:
    get_models(model)

class ComicTranslate(ComicTranslateUI):
    image_processed = QtCore.Signal(int, object, str)
    patches_processed = QtCore.Signal(int, list, str)
    progress_update = QtCore.Signal(int, int, int, int, bool)
    image_skipped = QtCore.Signal(str, str, str)
    blk_rendered = QtCore.Signal(str, int, object)

    def __init__(self, parent=None):
        super(ComicTranslate, self).__init__(parent)

        self.blk_list: list[TextBlock] = []   
        self.curr_tblock: TextBlock = None
        self.curr_tblock_item: TextBlockItem = None     

        self.image_files = []
        self.selected_batch = []
        self.curr_img_idx = -1
        self.image_states = {}
        self.image_data = {}  # Store the latest version of each image
        self.image_history = {}  # Store file path history for all images
        self.in_memory_history = {}  # Store cv2 image history for recent images
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

        self.pipeline = ComicTranslatePipeline(self)
        self.file_handler = FileHandler()
        self.threadpool = QThreadPool()
        self.current_worker = None

        self.image_ctrl = ImageStateController(self)
        self.rect_item_ctrl = RectItemController(self)
        self.project_ctrl = ProjectController(self)
        self.text_ctrl = TextController(self)

        self.image_skipped.connect(self.image_ctrl.on_image_skipped)
        self.image_processed.connect(self.image_ctrl.on_image_processed)
        self.patches_processed.connect(self.image_ctrl.on_inpaint_patches_processed)
        self.progress_update.connect(self.update_progress)
        self.blk_rendered.connect(self.text_ctrl.on_blk_rendered)

        self.connect_ui_elements()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.project_ctrl.load_main_page_settings()
        self.settings_page.load_settings()

        self.operation_queue = deque()
        self.is_processing_queue = False


    def connect_ui_elements(self):
        # Browsers
        self.image_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.document_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.archive_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.comic_browser_button.sig_files_changed.connect(self.image_ctrl.thread_load_images)
        self.project_browser_button.sig_file_changed.connect(self.project_ctrl.thread_load_project)

        self.save_browser.sig_file_changed.connect(self.image_ctrl.save_current_image)
        self.save_all_browser.sig_file_changed.connect(self.project_ctrl.save_and_make)
        self.save_project_button.clicked.connect(self.project_ctrl.thread_save_project)
        self.save_as_project_button.clicked.connect(self.project_ctrl.thread_save_as_project)

        self.drag_browser.sig_files_changed.connect(self.image_ctrl.thread_load_images)
       
        self.manual_radio.clicked.connect(self.manual_mode_selected)
        self.automatic_radio.clicked.connect(self.batch_mode_selected)

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

        # Connect image viewer signals
        self.image_viewer.rectangle_selected.connect(self.rect_item_ctrl.handle_rectangle_selection)
        self.image_viewer.rectangle_created.connect(self.rect_item_ctrl.handle_rectangle_creation)
        self.image_viewer.rectangle_deleted.connect(self.rect_item_ctrl.handle_rectangle_deletion)
        self.image_viewer.command_emitted.connect(self.push_command)
        self.image_viewer.connect_rect_item.connect(self.rect_item_ctrl.connect_rect_item_signals)
        self.image_viewer.connect_text_item.connect(self.text_ctrl.connect_text_item_signals)

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
        self.page_list.del_img.connect(self.image_ctrl.handle_image_deletion)
        self.page_list.insert_browser.sig_files_changed.connect(self.image_ctrl.thread_insert)
        self.page_list.toggle_skip_img.connect(self.image_ctrl.handle_toggle_skip_images)
        self.page_list.translate_imgs.connect(self.batch_translate_selected)

    def connect_rect_item_signals(self, rect_item): return self.rect_item_ctrl.connect_rect_item_signals(rect_item)
    def apply_inpaint_patches(self, patches): return self.image_ctrl.apply_inpaint_patches(patches)
    def render_settings(self): return self.text_ctrl.render_settings()
    def load_image(self, file_path: str) -> np.ndarray: return self.image_ctrl.load_image(file_path)

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
        QtWidgets.QMessageBox.critical(self, "Error", error_msg)
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
                rect = self.rect_item_ctrl.find_corresponding_rect(self.blk_list[0], 0.5)
            self.image_viewer.select_rectangle(rect) 
        self.set_tool('box')
        self.on_manual_finished()

    def ocr(self, single_block=False):
        source_lang = self.s_combo.currentText()
        if not validate_ocr(self, source_lang):
            return
        self.loading.setVisible(True)
        self.disable_hbutton_group()
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
        self.run_threaded(
            lambda: self.pipeline.translate_image(single_block),
            None,
            self.default_error_handler,
            lambda: self.update_translated_text_items(single_block)
        )

    def update_translated_text_items(self, single_blk: bool):
        def set_new_text(text_item, wrapped, font_size):
            if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja', 'th']):
                wrapped = wrapped.replace(' ', '')
            text_item.set_plain_text(wrapped)
            text_item.set_font_size(font_size)

        if not self.image_viewer.text_items:
            self.finish_ocr_translate(single_blk)
            return
        
        rs = self.render_settings()
        upper = rs.upper_case
        target_lang_en = self.lang_mapping.get(self.t_combo.currentText(), None)
        trg_lng_cd = get_language_code(target_lang_en)

        # This callback only runs **after** format_translations has finished.
        def on_format_finished():
            for text_item in self.image_viewer.text_items:
                text_item.handleDeselection()
                x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
                rot = text_item.rotation()
                blk = next(
                    (
                        b for b in self.blk_list
                        if (int(b.xyxy[0]), int(b.xyxy[1])) == (x1, y1)
                        and b.angle == rot
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

                def compute_all_bboxes():
                    image = self.image_viewer.get_cv2_image()
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

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Left:
            self.image_ctrl.navigate_images(-1)
        elif event.key() == QtCore.Qt.Key_Right:
            self.image_ctrl.navigate_images(1)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Save all settings when the application is closed
        self.settings_page.save_settings()
        self.project_ctrl.save_main_page_settings()
        
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

