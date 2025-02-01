import os
import cv2, shutil
import tempfile
import numpy as np
import copy
from typing import Callable, Tuple, List
from dataclasses import asdict, is_dataclass

from PySide6 import QtWidgets
from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication, QSettings, QThreadPool
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QUndoStack, QUndoGroup

from app.ui.dayu_widgets.clickable_card import ClickMeta
from app.ui.dayu_widgets.qt import MPixmap
from app.ui.main_window import ComicTranslateUI
from app.ui.messages import Messages
from app.thread_worker import GenericWorker
from app.ui.dayu_widgets.message import MMessage

from app.ui.canvas.text_item import TextBlockItem
from app.ui.canvas.rectangle import MoveableRectItem
from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.ui.commands.box import AddRectangleCommand, DeleteBoxesCommand, \
                                      BoxesChangeCommand, AddTextItemCommand 
from app.ui.commands.textformat import TextFormatCommand
from app.ui.commands.image import SetImageCommand
from app.projects.project_state import save_state_to_proj_file, load_state_from_proj_file

from modules.detection import do_rectangles_overlap, get_inpaint_bboxes
from modules.utils.textblock import TextBlock
from modules.rendering.render import manual_wrap
from modules.utils.file_handler import FileHandler
from modules.utils.pipeline_utils import font_selected, validate_settings, get_layout_direction, \
                                         validate_ocr, validate_translator, get_language_code
from modules.utils.archives import make
from modules.utils.download import get_models, mandatory_models
from modules.utils.translator_utils import format_translations, is_there_text
from modules.rendering.render import TextRenderingSettings
from pipeline import ComicTranslatePipeline


for model in mandatory_models:
    get_models(model)

class ComicTranslate(ComicTranslateUI):
    image_processed = QtCore.Signal(int, object, str)
    progress_update = QtCore.Signal(int, int, int, int, bool)
    image_skipped = QtCore.Signal(str, str, str)
    blk_rendered = QtCore.Signal(str, int, object)

    def __init__(self, parent=None):
        super(ComicTranslate, self).__init__(parent)

        self.image_files = []
        self.curr_img_idx = -1
        self.image_states = {}

        self.blk_list = []
        self.image_data = {}  # Store the latest version of each image
        self.image_history = {}  # Store file path history for all images
        self.in_memory_history = {}  # Store cv2 image history for recent images
        self.current_history_index = {}  # Current position in the history for each image
        self.displayed_images = set()  # Set to track displayed images

        self.undo_group = QUndoGroup(self)
        self.undo_stacks = {}

        self.curr_tblock = None
        self.curr_tblock_item = None

        self.project_file = None

        self.pipeline = ComicTranslatePipeline(self)
        self.file_handler = FileHandler()
        self.threadpool = QThreadPool()
        self.current_worker = None

        self.image_skipped.connect(self.on_image_skipped)
        self.image_processed.connect(self.on_image_processed)
        self.progress_update.connect(self.update_progress)

        self.blk_rendered.connect(self.on_blk_rendered)

        self.image_cards = []
        self.current_highlighted_card = None

        self.connect_ui_elements()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.load_main_page_settings()
        self.settings_page.load_settings()

        self.temp_dir = tempfile.mkdtemp()
        self.max_images_in_memory = 10
        self.loaded_images = []

        # List of widgets to block signals for during manual rendering
        self.widgets_to_block = [
            self.font_dropdown,
            self.font_size_dropdown,
            self.line_spacing_dropdown,
            self.block_font_color_button,
            self.outline_font_color_button,
            self.outline_width_dropdown,
            self.outline_checkbox
        ]

    def connect_ui_elements(self):
        # Browsers
        self.image_browser_button.sig_files_changed.connect(self.thread_load_images)
        self.document_browser_button.sig_files_changed.connect(self.thread_load_images)
        self.archive_browser_button.sig_files_changed.connect(self.thread_load_images)
        self.comic_browser_button.sig_files_changed.connect(self.thread_load_images)
        self.project_browser_button.sig_file_changed.connect(self.thread_load_project)

        self.save_browser.sig_file_changed.connect(self.save_current_image)
        self.save_all_browser.sig_file_changed.connect(self.save_and_make)
        self.save_project_button.clicked.connect(self.thread_save_project)
        self.save_as_project_button.clicked.connect(self.thread_save_as_project)

        self.drag_browser.sig_files_changed.connect(self.thread_load_images)
       
        self.manual_radio.clicked.connect(self.manual_mode_selected)
        self.automatic_radio.clicked.connect(self.batch_mode_selected)

        # Connect buttons from button_groups
        self.hbutton_group.get_button_group().buttons()[0].clicked.connect(lambda: self.block_detect())
        self.hbutton_group.get_button_group().buttons()[1].clicked.connect(self.ocr)
        self.hbutton_group.get_button_group().buttons()[2].clicked.connect(self.translate_image)
        self.hbutton_group.get_button_group().buttons()[3].clicked.connect(self.load_segmentation_points)
        self.hbutton_group.get_button_group().buttons()[4].clicked.connect(self.inpaint_and_set)
        self.hbutton_group.get_button_group().buttons()[5].clicked.connect(self.render_text)

        self.undo_tool_group.get_button_group().buttons()[0].clicked.connect(self.undo_group.undo)
        self.undo_tool_group.get_button_group().buttons()[1].clicked.connect(self.undo_group.redo)

        # Connect other buttons and widgets
        self.translate_button.clicked.connect(self.start_batch_process)
        self.cancel_button.clicked.connect(self.cancel_current_task)
        self.set_all_button.clicked.connect(self.set_src_trg_all)
        self.clear_rectangles_button.clicked.connect(self.image_viewer.clear_rectangles)
        self.clear_brush_strokes_button.clicked.connect(self.image_viewer.clear_brush_strokes)
        self.draw_blklist_blks.clicked.connect(lambda: self.pipeline.load_box_coords(self.blk_list))
        self.change_all_blocks_size_dec.clicked.connect(lambda: self.change_all_blocks_size(-int(self.change_all_blocks_size_diff.text())))
        self.change_all_blocks_size_inc.clicked.connect(lambda: self.change_all_blocks_size(int(self.change_all_blocks_size_diff.text())))
        self.delete_button.clicked.connect(self.delete_selected_box)

        # Connect text edit widgets
        self.s_text_edit.textChanged.connect(self.update_text_block)
        self.t_text_edit.textChanged.connect(self.update_text_block_from_edit)

        self.s_combo.currentTextChanged.connect(self.save_src_trg)
        self.t_combo.currentTextChanged.connect(self.save_src_trg)

        # Connect image viewer signals
        self.image_viewer.rectangle_selected.connect(self.handle_rectangle_selection)
        self.image_viewer.rectangle_created.connect(self.handle_rectangle_creation)
        self.image_viewer.rectangle_deleted.connect(self.handle_rectangle_deletion)
        self.image_viewer.command_emitted.connect(self.push_command)
        self.image_viewer.connect_rect_item.connect(self.connect_rect_item_signals)
        self.image_viewer.connect_text_item.connect(self.connect_text_item_signals)

        # Rendering
        self.font_dropdown.currentTextChanged.connect(self.on_font_dropdown_change)
        self.font_size_dropdown.currentTextChanged.connect(self.on_font_size_change)
        self.line_spacing_dropdown.currentTextChanged.connect(self.on_line_spacing_change)
        self.block_font_color_button.clicked.connect(self.on_font_color_change)
        self.alignment_tool_group.get_button_group().buttons()[0].clicked.connect(self.left_align)
        self.alignment_tool_group.get_button_group().buttons()[1].clicked.connect(self.center_align)
        self.alignment_tool_group.get_button_group().buttons()[2].clicked.connect(self.right_align)
        self.bold_button.clicked.connect(self.bold)
        self.italic_button.clicked.connect(self.italic)
        self.underline_button.clicked.connect(self.underline)
        self.outline_font_color_button.clicked.connect(self.on_outline_color_change)
        self.outline_width_dropdown.currentTextChanged.connect(self.on_outline_width_change)
        self.outline_checkbox.stateChanged.connect(self.toggle_outline_settings)

        # Page List
        self.page_list.currentItemChanged.connect(self.on_card_selected)
        self.page_list.del_img.connect(self.handle_image_deletion)
        self.page_list.insert_browser.sig_files_changed.connect(self.thread_insert)

    def push_command(self, command):
        if self.undo_group.activeStack():
            self.undo_group.activeStack().push(command)

    def connect_rect_item_signals(self, rect_item: MoveableRectItem):
        rect_item.signals.rectangle_changed.connect(self.handle_rectangle_change)
        rect_item.signals.change_undo.connect(self.rect_change_undo)
        rect_item.signals.ocr_block.connect(lambda: self.ocr(True))
        rect_item.signals.translate_block.connect(lambda: self.translate_image(True))
    
    def connect_text_item_signals(self, text_item: TextBlockItem):
        text_item.item_selected.connect(self.on_text_item_selected)
        text_item.item_deselected.connect(self.on_text_item_deselcted)
        text_item.text_changed.connect(self.update_text_block_from_item)
        text_item.item_changed.connect(self.handle_rectangle_change)
        text_item.text_highlighted.connect(self.set_values_from_highlight)
        text_item.change_undo.connect(self.rect_change_undo)

    def on_blk_rendered(self, text: str, font_size: int, blk: TextBlock):
        if not self.image_viewer.hasPhoto():
            print("No main image to add to.")
            return
        
        target_lang = self.lang_mapping.get(self.t_combo.currentText(), None)
        trg_lng_cd = get_language_code(target_lang)
        if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja', 'th']):
            text = text.replace(' ', '')
        
        render_settings = self.render_settings()
        font_family = render_settings.font_family
        text_color_str = render_settings.color
        text_color = QColor(text_color_str)
        
        id = render_settings.alignment_id
        alignment = self.button_to_alignment[id]
        line_spacing = float(render_settings.line_spacing)
        outline_color_str = render_settings.outline_color
        outline_color = QColor(outline_color_str) if self.outline_checkbox.isChecked() else None
        outline_width = float(render_settings.outline_width)
        bold = render_settings.bold
        italic = render_settings.italic
        underline = render_settings.underline
        direction = render_settings.direction

        text_item = TextBlockItem(text, self.image_viewer.photo, font_family, 
                                  font_size, text_color, alignment, line_spacing, 
                                  outline_color, outline_width, bold, italic, underline, direction)
        
        text_item.setPos(blk.xyxy[0], blk.xyxy[1])
        text_item.set_plain_text(text)
        self.image_viewer._scene.addItem(text_item)
        self.image_viewer.text_items.append(text_item)  
        self.connect_text_item_signals(text_item)

        command = AddTextItemCommand(self, text_item)
        self.undo_group.activeStack().push(command)

    def on_text_item_deselcted(self):
        self.clear_text_edits()

    def update_text_block_from_item(self, new_text):
        if self.curr_tblock:
            self.curr_tblock.translation = new_text
            self.t_text_edit.blockSignals(True)
            self.t_text_edit.setPlainText(new_text)
            self.t_text_edit.blockSignals(False)
    
    def on_text_item_selected(self, text_item):
        self.curr_tblock_item = text_item
            
        x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
        rotation = text_item.rotation()

        self.curr_tblock = next(
                (blk for blk in self.blk_list if (int(blk.xyxy[0]), int(blk.xyxy[1])) == (x1, y1) 
                 and blk.angle == rotation),
                None
            )
        
        # Update both s_text_edit and t_text_edit
        self.s_text_edit.blockSignals(True)
        self.s_text_edit.setPlainText(self.curr_tblock.text)
        self.s_text_edit.blockSignals(False)

        self.t_text_edit.blockSignals(True)
        self.t_text_edit.setPlainText(text_item.toPlainText())
        self.t_text_edit.blockSignals(False)

        self.set_values_for_blk_item(text_item)
            
    def update_text_block_from_edit(self):
        new_text = self.t_text_edit.toPlainText()
        if self.curr_tblock:
            self.curr_tblock.translation = new_text
        
        if self.curr_tblock_item and self.curr_tblock_item in self.image_viewer._scene.items():
            cursor_position = self.t_text_edit.textCursor().position()
            self.curr_tblock_item.setPlainText(new_text)
            
            # Restore cursor position
            cursor = self.t_text_edit.textCursor()
            cursor.setPosition(cursor_position)
            self.t_text_edit.setTextCursor(cursor)

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

    def save_src_trg(self):
        source_lang = self.s_combo.currentText()
        target_lang = self.t_combo.currentText()
        if self.curr_img_idx >= 0:
            current_file = self.image_files[self.curr_img_idx]
            self.image_states[current_file]['source_lang'] = source_lang
            self.image_states[current_file]['target_lang'] = target_lang

        target_en = self.lang_mapping.get(target_lang, None)
        t_direction = get_layout_direction(target_en)
        t_text_option = self.t_text_edit.document().defaultTextOption()
        t_text_option.setTextDirection(t_direction)
        self.t_text_edit.document().setDefaultTextOption(t_text_option)

    def set_src_trg_all(self):
        source_lang = self.s_combo.currentText()
        target_lang = self.t_combo.currentText()
        for image_path in self.image_files:
            self.image_states[image_path]['source_lang'] = source_lang
            self.image_states[image_path]['target_lang'] = target_lang

    def change_all_blocks_size(self, diff: int):
        if len(self.blk_list) == 0:
            return
        updated_blk_list = []
        for blk in self.blk_list:
            blk_rect = tuple(blk.xyxy)
            blk.xyxy[:] = [blk_rect[0] - diff, blk_rect[1] - diff, blk_rect[2] + diff, blk_rect[3] + diff]
            updated_blk_list.append(blk)
        self.blk_list = updated_blk_list
        self.pipeline.load_box_coords(self.blk_list)

    def batch_mode_selected(self):
        self.disable_hbutton_group()
        self.translate_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def manual_mode_selected(self):
        self.enable_hbutton_group()
        self.translate_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
    
    def on_image_processed(self, index: int, image: np.ndarray, image_path: str):
        if index == self.curr_img_idx:
            self.set_cv2_image(image)
        else:
            command = SetImageCommand(self, image_path, image, False)
            self.undo_group.activeStack().push(command)
            self.image_data[image_path] = image

    def on_image_skipped(self, image_path: str, skip_reason: str, error: str):
        message = { 
            "Text Blocks": QCoreApplication.translate('Messages', 'No Text Blocks Detected.\nSkipping:') + f" {image_path}\n{error}", 
            "OCR": QCoreApplication.translate('Messages', 'Could not OCR detected text.\nSkipping:') + f" {image_path}\n{error}",
            "Translator": QCoreApplication.translate('Messages', 'Could not get translations.\nSkipping:') + f" {image_path}\n{error}"        
        }

        text = message.get(skip_reason, f"Unknown skip reason: {skip_reason}. Error: {error}")
        
        MMessage.info(
            text=text,
            parent=self,
            duration=5,
            closable=True
        )

    def on_manual_finished(self):
        self.loading.setVisible(False)
        self.enable_hbutton_group()
    
    def run_threaded(self, callback: Callable, result_callback: Callable=None, error_callback: Callable=None, finished_callback: Callable=None, *args, **kwargs):
        worker = GenericWorker(callback, *args, **kwargs)

        if result_callback:
            worker.signals.result.connect(lambda result: QtCore.QTimer.singleShot(0, lambda: result_callback(result)))
        if error_callback:
            worker.signals.error.connect(lambda error: QtCore.QTimer.singleShot(0, lambda: error_callback(error)))
        if finished_callback:
            worker.signals.finished.connect(finished_callback)
        
        self.current_worker = worker
        self.threadpool.start(worker)

    def cancel_current_task(self):
        if self.current_worker:
            self.current_worker.cancel()
        # No need to Enable necessary Widgets/Buttons because the threads 
        # already have finish callbacks that handle this.

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

    def on_batch_process_finished(self):
        self.progress_bar.setVisible(False)
        self.translate_button.setEnabled(True)
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
        
    def clear_text_edits(self):
        self.curr_tblock = None
        self.curr_tblock_item = None
        self.s_text_edit.clear()
        self.t_text_edit.clear()

    def finish_ocr_translate(self, single_block=False):
        if self.blk_list:
            if single_block:
                rect = self.image_viewer.selected_rect
            else:
                rect = self.find_corresponding_rect(self.blk_list[0], 0.5)
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
                lambda: self.finish_ocr_translate(single_block)
            )

    def inpaint_and_set(self):
        if self.image_viewer.hasPhoto() and self.image_viewer.has_drawn_elements():
            self.clear_text_edits()
            self.loading.setVisible(True)
            self.disable_hbutton_group()
            self.run_threaded(self.pipeline.inpaint, self.pipeline.inpaint_complete, 
                              self.default_error_handler, self.on_manual_finished)

    def load_initial_image(self, file_paths: List[str]):
        file_paths = self.file_handler.prepare_files(file_paths)
        self.image_files = file_paths

        if file_paths:
            return self.load_image(file_paths[0])
        return None
    
    def load_image(self, file_path: str):
        if file_path in self.image_data:
            return self.image_data[file_path]

        # Check if the image has been displayed before
        if file_path in self.image_history:
            # Get the current index from the history
            current_index = self.current_history_index[file_path]
            
            # Get the temp file path at the current index
            current_temp_path = self.image_history[file_path][current_index]
            
            # Load the image from the temp file
            cv2_image = cv2.imread(current_temp_path)
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
            
            if cv2_image is not None:
                return cv2_image

        # If not in memory and not in history (or failed to load from temp),
        # load from the original file path
        try:
            cv2_image = cv2.imread(file_path)
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
            return cv2_image
        except Exception as e:
            print(f"Error loading image {file_path}: {str(e)}")
            return None

    def thread_load_images(self, file_paths: List[str]):
        if file_paths and file_paths[0].lower().endswith('.ctpr'):
            self.thread_load_project(file_paths[0])
            return
        self.clear_state()
        self.run_threaded(self.load_initial_image, self.on_initial_image_loaded, self.default_error_handler, None, file_paths)

    def thread_insert(self, file_paths: list[str]):
        if self.image_files:
            def on_files_prepared(prepared_files):
                self.image_files.extend(prepared_files)
                path = prepared_files[0]
                new_index = self.image_files.index(path)
                self.update_image_cards()
                self.page_list.setCurrentRow(new_index)

            self.run_threaded(
                lambda: self.file_handler.prepare_files(file_paths, True),
                on_files_prepared,
                self.default_error_handler)
        else:
            self.thread_load_images(file_paths)

    def clear_state(self):
        # Clear existing image data
        self.image_files = []
        self.image_states.clear()
        self.image_data.clear()
        self.image_history.clear()
        self.current_history_index.clear()
        self.blk_list = []
        self.displayed_images.clear()
        self.image_viewer.clear_rectangles(page_switch=True)
        self.image_viewer.clear_brush_strokes(page_switch=True)
        self.s_text_edit.clear()
        self.t_text_edit.clear()
        self.image_viewer.clear_text_items()
        self.loaded_images = []
        self.in_memory_history.clear()
        self.undo_stacks.clear()
        self.project_file = None

        # Reset current_image_index
        self.curr_img_idx = -1

    def on_initial_image_loaded(self, cv2_image):

        if cv2_image is not None:
            self.image_data[self.image_files[0]] = cv2_image
            self.image_history[self.image_files[0]] = [self.image_files[0]]
            self.in_memory_history[self.image_files[0]] = [cv2_image.copy()]
            self.current_history_index[self.image_files[0]] = 0
            self.save_image_state(self.image_files[0])

        for file in self.image_files:
            self.save_image_state(file)
            stack = QUndoStack(self)
            self.undo_stacks[file] = stack
            self.undo_group.addStack(stack)

        if self.image_files:
            self.page_list.blockSignals(True)
            self.update_image_cards()
            self.page_list.blockSignals(False)
            self.page_list.setCurrentRow(0)
            #self.display_image(0)
            self.loaded_images.append(self.image_files[0])
        else:
            self.image_viewer.clear_scene()

        self.image_viewer.resetTransform()
        self.image_viewer.fitInView()

    def update_image_cards(self):
        # Clear existing items
        self.page_list.clear()

        # Add new items
        for index, file_path in enumerate(self.image_files):
            file_name = os.path.basename(file_path)
            list_item = QtWidgets.QListWidgetItem(file_name)
            card = ClickMeta(extra=False, avatar_size=(35, 50))
            card.setup_data({
                "title": file_name,
                #"avatar": MPixmap(file_path)
            })
            self.page_list.addItem(list_item)
            self.page_list.setItemWidget(list_item, card)

    def on_card_selected(self, current, previous):
        if current:  
            index = self.page_list.row(current)
            self.curr_tblock_item = None
            
            self.run_threaded(
                lambda: self.load_image(self.image_files[index]),
                lambda result: self.display_image_from_loaded(result, index),
                self.default_error_handler,
                None
            )

    def navigate_images(self, direction: int):
        if self.image_files:
            new_index = self.curr_img_idx + direction
            if 0 <= new_index < len(self.image_files):
                item = self.page_list.item(new_index)
                self.page_list.setCurrentItem(item)

    def handle_image_deletion(self, file_names: list[str]):
        """Handles the deletion of images based on the provided file names."""

        self.save_current_image_state()
        
        # Delete the files first.
        for file_name in file_names:
            # Find the full file path based on the file name
            file_path = next((f for f in self.image_files if os.path.basename(f) == file_name), None)
            
            if file_path:
                # Remove from the image_files list
                self.image_files.remove(file_path)
                
                # Remove associated data
                self.image_data.pop(file_path, None)
                self.image_history.pop(file_path, None)
                self.in_memory_history.pop(file_path, None)
                self.current_history_index.pop(file_path, None)

                if file_path in self.undo_stacks:
                    stack = self.undo_stacks[file_path]
                    self.undo_group.removeStack(stack)
                    self.undo_stacks.pop(file_path, None)
                    
                if file_path in self.displayed_images:
                    self.displayed_images.remove(file_path)
                    
                if file_path in self.loaded_images:
                    self.loaded_images.remove(file_path)

        if self.image_files:
            if self.curr_img_idx >= len(self.image_files):
                self.curr_img_idx = len(self.image_files) - 1

            new_index = max(0, self.curr_img_idx - 1)
            file = self.image_files[new_index]
            im = self.load_image(file)
            self.display_image_from_loaded(im, new_index, False)
            self.update_image_cards()
            self.page_list.blockSignals(True)
            self.page_list.setCurrentRow(new_index)
            self.page_list.blockSignals(False)
        else:
            # If no images remain, reset the view to the drag browser.
            self.curr_img_idx = -1
            self.central_stack.setCurrentWidget(self.drag_browser)
            self.update_image_cards()

    def display_image_from_loaded(self, cv2_image, index, switch_page=True):
        file_path = self.image_files[index]
        self.image_data[file_path] = cv2_image
        
        # Initialize history for new images
        if file_path not in self.image_history:
            self.image_history[file_path] = [file_path]
            self.in_memory_history[file_path] = [cv2_image.copy()]
            self.current_history_index[file_path] = 0

        self.display_image(index, switch_page)

        # Manage loaded images
        if file_path not in self.loaded_images:
            self.loaded_images.append(file_path)
            if len(self.loaded_images) > self.max_images_in_memory:
                oldest_image = self.loaded_images.pop(0)
                del self.image_data[oldest_image]
                self.in_memory_history[oldest_image] = []

    def set_cv2_image(self, cv2_img: np.ndarray):
        if self.curr_img_idx >= 0:
            file_path = self.image_files[self.curr_img_idx]
            
            # Push the command to the appropriate stack
            command = SetImageCommand(self, file_path, cv2_img)
            self.undo_group.activeStack().push(command)

    def save_image_state(self, file: str):
        self.image_states[file] = {
            'viewer_state': self.image_viewer.save_state(),
            'source_lang': self.s_combo.currentText(),
            'target_lang': self.t_combo.currentText(),
            'brush_strokes': self.image_viewer.save_brush_strokes(),
            'blk_list': self.blk_list.copy()  # Store a copy of the list, not a reference
        }

    def save_current_image_state(self):
        if self.curr_img_idx >= 0:
            current_file = self.image_files[self.curr_img_idx]
            self.save_image_state(current_file)

    def load_image_state(self, file_path: str):
        cv2_image = self.image_data[file_path]

        self.set_cv2_image(cv2_image)
        if file_path in self.image_states:
            state = self.image_states[file_path]

            self.blk_list = state['blk_list']
            self.image_viewer.load_state(state['viewer_state'])
            self.s_combo.setCurrentText(state['source_lang'])
            self.t_combo.setCurrentText(state['target_lang'])
            self.image_viewer.load_brush_strokes(state['brush_strokes'])

            for text_item in self.image_viewer.text_items:
                self.connect_text_item_signals(text_item)

            for rect_item in self.image_viewer.rectangles:
                self.connect_rect_item_signals(rect_item)

        self.clear_text_edits()

    def display_image(self, index: int, switch_page=True):
        if 0 <= index < len(self.image_files):
            if switch_page:
                self.save_current_image_state()
            self.curr_img_idx = index
            file_path = self.image_files[index]

            # Set the active stack for the current image
            file_path = self.image_files[index]
            if file_path in self.undo_stacks:
                self.undo_group.setActiveStack(self.undo_stacks[file_path])
            
            # Check if this image has been displayed before
            first_time_display = file_path not in self.displayed_images
            
            self.load_image_state(file_path)
            self.central_stack.setCurrentWidget(self.image_viewer)
            self.central_stack.layout().activate()
            
            # Fit in view only if it's the first time displaying this image
            if first_time_display:
                self.image_viewer.fitInView()
                self.displayed_images.add(file_path)  # Mark this image as displayed

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
            self.clear_text_edits()
            self.set_tool('brush')
            self.disable_hbutton_group()
            self.image_viewer.clear_rectangles()
            self.image_viewer.clear_text_items()
            if self.blk_list:
                self.undo_group.activeStack().beginMacro('draw_segmentation_boxes')
                for blk in self.blk_list:
                    bboxes = blk.inpaint_bboxes
                    if bboxes is not None and len(bboxes) > 0:
                        self.image_viewer.draw_segmentation_lines(bboxes)
                
                self.enable_hbutton_group()
                self.undo_group.activeStack().endMacro()

            else:
                self.loading.setVisible(True)
                self.disable_hbutton_group()
                self.run_threaded(self.pipeline.detect_blocks, self.blk_detect_segment, 
                          self.default_error_handler, self.on_manual_finished)

    def find_corresponding_text_block(self, rect: Tuple[float], iou_threshold: int = 0.5):
        for blk in self.blk_list:
            if do_rectangles_overlap(rect, blk.xyxy, iou_threshold):
                return blk
        return None

    def find_corresponding_rect(self, tblock: TextBlock, iou_threshold: int):
        for rect in self.image_viewer.rectangles:
            mp_rect = rect.mapRectToScene(rect.rect())
            x1, y1, w, h = mp_rect.getRect()
            rect_coord = (x1, y1, x1 + w, y1 + h)
            if do_rectangles_overlap(rect_coord, tblock.xyxy, iou_threshold):
                return rect
        return None
    
    def handle_rectangle_selection(self, rect: QRectF):
        rect = rect.getCoords()
        self.curr_tblock = self.find_corresponding_text_block(rect, 0.5)
        if self.curr_tblock:
            self.s_text_edit.blockSignals(True)
            self.t_text_edit.blockSignals(True)
            self.s_text_edit.setPlainText(self.curr_tblock.text)
            self.t_text_edit.setPlainText(self.curr_tblock.translation)
            self.s_text_edit.blockSignals(False)
            self.t_text_edit.blockSignals(False)
        else:
            self.s_text_edit.clear()
            self.t_text_edit.clear()
            self.curr_tblock = None

    def handle_rectangle_creation(self, rect_item: MoveableRectItem):
        self.connect_rect_item_signals(rect_item)
        new_rect = rect_item.mapRectToScene(rect_item.rect())
        x1, y1, w, h = new_rect.getRect()
        x1, y1, w, h = int(x1), int(y1), int(w), int(h)
        new_rect_coords = (x1, y1, x1 + w, y1 + h)
        image = self.image_viewer.get_cv2_image()
        inpaint_boxes = get_inpaint_bboxes(new_rect_coords, image)

        new_blk = TextBlock(text_bbox=np.array(new_rect_coords), inpaint_bboxes=inpaint_boxes)
        self.blk_list.append(new_blk)

        command = AddRectangleCommand(self, rect_item, new_blk, self.blk_list)
        self.undo_group.activeStack().push(command)

    def handle_rectangle_deletion(self, rect: QRectF):
        rect_coords = rect.getCoords()
        current_text_block = self.find_corresponding_text_block(rect_coords, 0.5)
        self.blk_list.remove(current_text_block)

    def update_text_block(self):
        if self.curr_tblock:
            self.curr_tblock.text = self.s_text_edit.toPlainText()
            self.curr_tblock.translation = self.t_text_edit.toPlainText()

    def update_progress(self, index: int, total_images: int, step: int, total_steps: int, change_name: bool):
        # Assign weights to image processing and archiving (adjust as needed)
        image_processing_weight = 0.9
        archiving_weight = 0.1

        archive_info_list = self.file_handler.archive_info
        total_archives = len(archive_info_list)

        if change_name:
            if index < total_images:
                im_path = self.image_files[index]
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

    def on_render_complete(self, rendered_image: np.ndarray):
        # self.set_cv2_image(rendered_image)
        self.loading.setVisible(False)
        self.enable_hbutton_group()
        self.undo_group.activeStack().endMacro()

    def render_text(self):
        if self.image_viewer.hasPhoto() and self.blk_list:
            self.set_tool(None)
            if not font_selected(self):
                return
            self.clear_text_edits()
            self.loading.setVisible(True)
            self.disable_hbutton_group()

            # Add items to the scene if they're not already present
            for item in self.image_viewer.text_items:
                if item not in self.image_viewer._scene.items():
                    self.image_viewer._scene.addItem(item)

            # Create a dictionary to map text items to their positions and rotations
            existing_text_items = {item: (int(item.pos().x()), int(item.pos().y()), item.rotation()) for item in self.image_viewer.text_items}

            # Identify new blocks based on position and rotation
            new_blocks = [
                blk for blk in self.blk_list
                if (int(blk.xyxy[0]), int(blk.xyxy[1]), blk.angle) not in existing_text_items.values()
            ]

            self.image_viewer.clear_rectangles()
            self.curr_tblock = None
            self.curr_tblock_item = None

            render_settings = self.render_settings()
            upper = render_settings.upper_case

            line_spacing = float(self.line_spacing_dropdown.currentText())
            font_family = self.font_dropdown.currentText()
            outline_width = float(self.outline_width_dropdown.currentText())

            bold = self.bold_button.isChecked()
            italic = self.italic_button.isChecked()
            underline = self.underline_button.isChecked()

            target_lang = self.t_combo.currentText()
            target_lang_en = self.lang_mapping.get(target_lang, None)
            trg_lng_cd = get_language_code(target_lang_en)
            format_translations(self.blk_list, trg_lng_cd, upper_case=upper)
            min_font_size = self.settings_page.get_min_font_size() 
            max_font_size = self.settings_page.get_max_font_size()

            align_id = self.alignment_tool_group.get_dayu_checked()
            alignment = self.button_to_alignment[align_id]
            direction = render_settings.direction
            
            self.undo_group.activeStack().beginMacro('text_items_rendered')
            self.run_threaded(manual_wrap, self.on_render_complete, self.default_error_handler, 
                              None, self, new_blocks, font_family, line_spacing, outline_width, 
                              bold, italic, underline, alignment, direction, max_font_size, 
                              min_font_size)

    def handle_rectangle_change(self, new_rect: QRectF, angle: float, tr_origin: Tuple):
        # Find the corresponding TextBlock in blk_list
        for blk in self.blk_list:
            if do_rectangles_overlap(blk.xyxy, (new_rect.left(), new_rect.top(), new_rect.right(), new_rect.bottom()), 0.2):
                # Update the TextBlock coordinates
                blk.xyxy[:] = [int(new_rect.left()), int(new_rect.top()), int(new_rect.right()), int(new_rect.bottom())] 
                blk.angle = angle if angle else 0
                blk.tr_origin_point = (tr_origin.x(), tr_origin.y()) if tr_origin else ()
                image = self.image_viewer.get_cv2_image()
                inpaint_bboxes = get_inpaint_bboxes(blk.xyxy, image)
                blk.inpaint_bboxes = inpaint_bboxes
                break
                
    def rect_change_undo(self, old_state, new_state):
        command = BoxesChangeCommand(self.image_viewer, old_state,
                                         new_state, self.blk_list)
        self.undo_group.activeStack().push(command)

    def on_font_dropdown_change(self, font_family):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            font_size = int(self.font_size_dropdown.currentText())
            self.curr_tblock_item.set_font(font_family, font_size)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def on_font_size_change(self, font_size):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            font_size = float(font_size)
            self.curr_tblock_item.set_font_size(font_size)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def on_line_spacing_change(self, line_spacing):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            spacing = float(line_spacing)
            self.curr_tblock_item.set_line_spacing(spacing)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def on_font_color_change(self):
        font_color = self.get_color()
        if font_color and font_color.isValid():
            self.block_font_color_button.setStyleSheet(
                f"background-color: {font_color.name()}; border: none; border-radius: 5px;"
            )
            self.block_font_color_button.setProperty('selected_color', font_color.name())
            if self.curr_tblock_item:
                old_item = copy.copy(self.curr_tblock_item)
                self.curr_tblock_item.set_color(font_color)

                command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
                self.undo_group.activeStack().push(command)

    def left_align(self):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            self.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignLeft)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def center_align(self):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            self.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def right_align(self):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            self.curr_tblock_item.set_alignment(QtCore.Qt.AlignmentFlag.AlignRight)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def bold(self):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            state = self.bold_button.isChecked()
            self.curr_tblock_item.set_bold(state)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def italic(self):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            state = self.italic_button.isChecked()
            self.curr_tblock_item.set_italic(state)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def underline(self):
        if self.curr_tblock_item:
            old_item = copy.copy(self.curr_tblock_item)
            state = self.underline_button.isChecked()
            self.curr_tblock_item.set_underline(state)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def on_outline_color_change(self):
        outline_color = self.get_color()
        if outline_color and outline_color.isValid():
            self.outline_font_color_button.setStyleSheet(
                f"background-color: {outline_color.name()}; border: none; border-radius: 5px;"
            )
            self.outline_font_color_button.setProperty('selected_color', outline_color.name())
            outline_width = float(self.outline_width_dropdown.currentText())

            if self.curr_tblock_item and self.outline_checkbox.isChecked():
                old_item = copy.copy(self.curr_tblock_item)
                self.curr_tblock_item.set_outline(outline_color, outline_width)

                command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
                self.undo_group.activeStack().push(command)

    def on_outline_width_change(self, outline_width):
        if self.curr_tblock_item and self.outline_checkbox.isChecked():
            old_item = copy.copy(self.curr_tblock_item)
            outline_width = float(self.outline_width_dropdown.currentText())
            color_str = self.outline_font_color_button.property('selected_color')
            color = QColor(color_str)
            self.curr_tblock_item.set_outline(color, outline_width)

            command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
            self.undo_group.activeStack().push(command)

    def toggle_outline_settings(self, state): 
        enabled = True if state == 2 else False
        if self.curr_tblock_item:
            if not enabled:
                self.curr_tblock_item.set_outline(None, None)
            else:
                old_item = copy.copy(self.curr_tblock_item)
                outline_width = float(self.outline_width_dropdown.currentText())
                color_str = self.outline_font_color_button.property('selected_color')
                color = QColor(color_str)
                self.curr_tblock_item.set_outline(color, outline_width)

                command = TextFormatCommand(self.image_viewer, old_item, self.curr_tblock_item)
                self.undo_group.activeStack().push(command)

    def block_text_item_widgets(self, widgets):
        # Block signals
        for widget in widgets:
            widget.blockSignals(True)

        # Block Signals is buggy for these, so use disconnect/connect
        self.bold_button.clicked.disconnect(self.bold)   
        self.italic_button.clicked.disconnect(self.italic)
        self.underline_button.clicked.disconnect(self.underline)

        self.alignment_tool_group.get_button_group().buttons()[0].clicked.disconnect(self.left_align)
        self.alignment_tool_group.get_button_group().buttons()[1].clicked.disconnect(self.center_align)
        self.alignment_tool_group.get_button_group().buttons()[2].clicked.disconnect(self.right_align)

    def unblock_text_item_widgets(self, widgets):
        # Unblock signals
        for widget in widgets:
            widget.blockSignals(False)

        self.bold_button.clicked.connect(self.bold)
        self.italic_button.clicked.connect(self.italic)
        self.underline_button.clicked.connect(self.underline)

        self.alignment_tool_group.get_button_group().buttons()[0].clicked.connect(self.left_align)
        self.alignment_tool_group.get_button_group().buttons()[1].clicked.connect(self.center_align)
        self.alignment_tool_group.get_button_group().buttons()[2].clicked.connect(self.right_align)

    def set_values_for_blk_item(self, text_item: TextBlockItem):

        self.block_text_item_widgets(self.widgets_to_block)

        try:
            # Set values
            self.font_dropdown.setCurrentText(text_item.font_family)
            self.font_size_dropdown.setCurrentText(str(int(text_item.font_size)))

            self.line_spacing_dropdown.setCurrentText(str(text_item.line_spacing))

            self.block_font_color_button.setStyleSheet(
                f"background-color: {text_item.text_color.name()}; border: none; border-radius: 5px;"
            )
            self.block_font_color_button.setProperty('selected_color', text_item.text_color.name())

            if text_item.outline_color is not None:
                self.outline_font_color_button.setStyleSheet(
                    f"background-color: {text_item.outline_color.name()}; border: none; border-radius: 5px;"
                )
                self.outline_font_color_button.setProperty('selected_color', text_item.outline_color.name())
            else:
                self.outline_font_color_button.setStyleSheet(
                    "background-color: white; border: none; border-radius: 5px;"
                )
                self.outline_font_color_button.setProperty('selected_color', '#ffffff')

            self.outline_width_dropdown.setCurrentText(str(text_item.outline_width))
            self.outline_checkbox.setChecked(text_item.outline)      

            self.bold_button.setChecked(text_item.bold)
            self.italic_button.setChecked(text_item.italic)
            self.underline_button.setChecked(text_item.underline)

            alignment_to_button = {
                QtCore.Qt.AlignmentFlag.AlignLeft: 0,
                QtCore.Qt.AlignmentFlag.AlignCenter: 1,
                QtCore.Qt.AlignmentFlag.AlignRight: 2,
            }

            alignment = text_item.alignment
            button_group = self.alignment_tool_group.get_button_group()

            if alignment in alignment_to_button:
                button_index = alignment_to_button[alignment]
                button_group.buttons()[button_index].setChecked(True)

        finally:
            self.unblock_text_item_widgets(self.widgets_to_block)

    def set_values_from_highlight(self, item_highlighted = None):

        self.block_text_item_widgets(self.widgets_to_block)

        # Attributes
        font_family = item_highlighted['font_family']
        font_size = item_highlighted['font_size']
        text_color =  item_highlighted['text_color']

        outline_color = item_highlighted['outline_color']
        outline_width =  item_highlighted['outline_width']
        outline = item_highlighted['outline'] 

        bold = item_highlighted['bold']
        italic =  item_highlighted['italic']
        underline = item_highlighted['underline']

        alignment = item_highlighted['alignment']

        try:
            # Set values
            self.font_dropdown.setCurrentText(font_family) if font_family else None
            self.font_size_dropdown.setCurrentText(str(int(font_size))) if font_size else None
 
            if text_color is not None:
                self.block_font_color_button.setStyleSheet(
                    f"background-color: {text_color}; border: none; border-radius: 5px;"
                )
                self.block_font_color_button.setProperty('selected_color', text_color)

            if outline_color is not None:
                self.outline_font_color_button.setStyleSheet(
                    f"background-color: {outline_color}; border: none; border-radius: 5px;"
                )
                self.outline_font_color_button.setProperty('selected_color', outline_color)
            else:
                self.outline_font_color_button.setStyleSheet(
                    "background-color: white; border: none; border-radius: 5px;"
                )
                self.outline_font_color_button.setProperty('selected_color', '#ffffff')

            self.outline_width_dropdown.setCurrentText(str(outline_width)) if outline_width else None
            self.outline_checkbox.setChecked(outline) 

            self.bold_button.setChecked(bold) 
            self.italic_button.setChecked(italic) 
            self.underline_button.setChecked(underline) 

            alignment_to_button = {
                QtCore.Qt.AlignmentFlag.AlignLeft: 0,
                QtCore.Qt.AlignmentFlag.AlignCenter: 1,
                QtCore.Qt.AlignmentFlag.AlignRight: 2,
            }

            button_group = self.alignment_tool_group.get_button_group()

            if alignment in alignment_to_button:
                button_index = alignment_to_button[alignment]
                button_group.buttons()[button_index].setChecked(True)

        finally:
            self.unblock_text_item_widgets(self.widgets_to_block)

    def save_current_image(self, file_path: str):
        curr_image = self.image_viewer.get_cv2_image(paint_all=True)
        cv2.imwrite(file_path, curr_image)

    def save_and_make(self, output_path: str):
        self.run_threaded(self.save_and_make_worker, None, self.default_error_handler, None, output_path)

    def save_and_make_worker(self, output_path: str):
        self.save_current_image_state()
        temp_dir = tempfile.mkdtemp()
        try:
            # Save images
            for file_path in self.image_files:
                bname = os.path.basename(file_path) 
                cv2_img = self.load_image(file_path)  

                renderer = ImageSaveRenderer(cv2_img)
                viewer_state = self.image_states[file_path]['viewer_state']
                renderer.add_state_to_image(viewer_state)
                sv_pth = os.path.join(temp_dir, bname)
                renderer.save_image(sv_pth)
            
            # Call make function
            make(temp_dir, output_path)
        finally:
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir)

    def launch_save_proj_dialog(self):
        file_dialog = QtWidgets.QFileDialog()
        file_name, _ = file_dialog.getSaveFileName(
            self, 
            "Save Project As", 
            "untitled", 
            "Project Files (*.ctpr);;All Files (*)"
        )

        return file_name
    
    def run_save_proj(self, file_name):
        self.project_file = file_name
        self.loading.setVisible(True)
        self.disable_hbutton_group()
        self.run_threaded(self.save_project, None, 
                                self.default_error_handler, self.on_manual_finished, file_name)

    def thread_save_project(self):
        file_name = ""
        self.save_current_image_state()
        if self.project_file:
            file_name = self.project_file
        else:
            file_name = self.launch_save_proj_dialog()

        if file_name:
            self.run_save_proj(file_name)
            
    def thread_save_as_project(self):
        file_name = self.launch_save_proj_dialog()
        if file_name:
            self.save_current_image_state()
            self.run_save_proj(file_name)

    def save_project(self, file_name):
        save_state_to_proj_file(self, file_name)

    def update_ui_from_project(self):
        index = self.curr_img_idx
        self.update_image_cards()

        for file in self.image_files:
            stack = QUndoStack(self)
            self.undo_stacks[file] = stack
            self.undo_group.addStack(stack)
            
        self.run_threaded(
            lambda: self.load_image(self.image_files[index]),
            lambda result: self.display_image_from_loaded(result, index, switch_page=False),
            self.default_error_handler,
            None
        )

    def thread_load_project(self, file_name):
        self.clear_state()
        self.run_threaded(self.load_project, None, 
                          self.default_error_handler, self.update_ui_from_project, file_name)

    def load_project(self, file_name):
        self.project_file = file_name
        load_state_from_proj_file(self, file_name)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Left:
            self.navigate_images(-1)
        elif event.key() == QtCore.Qt.Key_Right:
            self.navigate_images(1)
        else:
            super().keyPressEvent(event)

    def process_group(self, group_key, group_value, settings_obj: QSettings):
        """Helper function to process a group and its nested values."""
        if is_dataclass(group_value):
            group_value = asdict(group_value)
        if isinstance(group_value, dict):
            settings_obj.beginGroup(group_key)
            for sub_key, sub_value in group_value.items():
                self.process_group(sub_key, sub_value, settings_obj)
            settings_obj.endGroup()
        else:
            # Convert value to English using mappings if available
            mapped_value = self.settings_page.ui.value_mappings.get(group_value, group_value)
            settings_obj.setValue(group_key, mapped_value)

    def render_settings(self) -> TextRenderingSettings:
        target_lang = self.lang_mapping.get(self.t_combo.currentText(), None)
        direction = get_layout_direction(target_lang)

        return TextRenderingSettings(
            alignment_id = self.alignment_tool_group.get_dayu_checked(),
            font_family = self.font_dropdown.currentText(),
            min_font_size = int(self.settings_page.ui.min_font_spinbox.value()),
            max_font_size = int(self.settings_page.ui.max_font_spinbox.value()),
            color = self.block_font_color_button.property('selected_color'),
            upper_case = self.settings_page.ui.uppercase_checkbox.isChecked(),
            outline = self.outline_checkbox.isChecked(),
            outline_color = self.outline_font_color_button.property('selected_color'),
            outline_width = self.outline_width_dropdown.currentText(),
            bold = self.bold_button.isChecked(),
            italic = self.italic_button.isChecked(),
            underline = self.underline_button.isChecked(),
            line_spacing = self.line_spacing_dropdown.currentText(),
            direction = direction
        )

    def save_main_page_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")
        
        self.process_group('text_rendering', self.render_settings(), settings)

        settings.beginGroup("main_page")
        # Save languages in English
        settings.setValue("source_language", self.lang_mapping[self.s_combo.currentText()])
        settings.setValue("target_language", self.lang_mapping[self.t_combo.currentText()])
        
        settings.setValue("mode", "manual" if self.manual_radio.isChecked() else "automatic")
        
        # Save brush and eraser sizes
        settings.setValue("brush_size", self.image_viewer.brush_size)
        settings.setValue("eraser_size", self.image_viewer.eraser_size)

        settings.endGroup()

        # Save window state
        settings.beginGroup("MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.endGroup()

    def load_main_page_settings(self):
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("main_page")

        # Load languages and convert back to current language
        source_lang = settings.value("source_language", "Korean")
        target_lang = settings.value("target_language", "English")
        
        # Use reverse mapping to get the translated language names
        self.s_combo.setCurrentText(self.reverse_lang_mapping.get(source_lang, self.tr("Korean")))
        self.t_combo.setCurrentText(self.reverse_lang_mapping.get(target_lang, self.tr("English")))

        mode = settings.value("mode", "manual")
        if mode == "manual":
            self.manual_radio.setChecked(True)
            self.manual_mode_selected()
        else:
            self.automatic_radio.setChecked(True)
            self.batch_mode_selected()
        
        # Load brush and eraser sizes
        brush_size = int(settings.value("brush_size", 10))  # Default value is 10
        eraser_size = int(settings.value("eraser_size", 20))  # Default value is 20
        self.image_viewer.brush_size = brush_size
        self.image_viewer.eraser_size = eraser_size

        settings.endGroup()

        # Load window state
        settings.beginGroup("MainWindow")
        geometry = settings.value("geometry")
        state = settings.value("state")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            self.restoreState(state)
        settings.endGroup()

        # Load text rendering settings
        settings.beginGroup('text_rendering')
        alignment = settings.value('alignment_id', 1, type=int) # Default value is 1 which is Center
        self.alignment_tool_group.set_dayu_checked(alignment)  

        self.font_dropdown.setCurrentText(settings.value('font_family', ''))
        min_font_size = settings.value('min_font_size', 12)  # Default value is 12
        max_font_size = settings.value('max_font_size', 40) # Default value is 40
        self.settings_page.ui.min_font_spinbox.setValue(int(min_font_size))
        self.settings_page.ui.max_font_spinbox.setValue(int(max_font_size))

        color = settings.value('color', '#000000')
        self.block_font_color_button.setStyleSheet(f"background-color: {color}; border: none; border-radius: 5px;")
        self.block_font_color_button.setProperty('selected_color', color)
        self.settings_page.ui.uppercase_checkbox.setChecked(settings.value('upper_case', False, type=bool))
        self.outline_checkbox.setChecked(settings.value('outline', True, type=bool))

        self.line_spacing_dropdown.setCurrentText(settings.value('line_spacing', '1.0'))
        self.outline_width_dropdown.setCurrentText(settings.value('outline_width', '1.0'))
        outline_color = settings.value('outline_color', '#FFFFFF')
        self.outline_font_color_button.setStyleSheet(f"background-color: {outline_color}; border: none; border-radius: 5px;")
        self.outline_font_color_button.setProperty('selected_color', outline_color)

        self.bold_button.setChecked(settings.value('bold', False, type=bool))
        self.italic_button.setChecked(settings.value('italic', False, type=bool))
        self.underline_button.setChecked(settings.value('underline', False, type=bool))
        settings.endGroup()

    def closeEvent(self, event):
        # Save all settings when the application is closed
        self.settings_page.save_settings()
        self.save_main_page_settings()
        
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

