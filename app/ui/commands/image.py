import numpy as np
import cv2
import tempfile
from PIL import Image
from PySide6.QtGui import QUndoCommand


class SetImageCommand(QUndoCommand):
    def __init__(self, parent, file_path: str, cv2_img: np.ndarray, display: bool = True):
        super().__init__()
        self.ct = parent
        self.update_image_history(file_path, cv2_img)
        self.first = True
        self.display_first_time = display

    def redo(self):
        if self.first:
            if not self.display_first_time:
                return
            
            file_path = self.ct.image_files[self.ct.curr_img_idx]
            current_index = self.ct.current_history_index[file_path]
            cv2_img = self.get_img(file_path, current_index)
            self.ct.image_viewer.display_cv2_image(cv2_img)
            self.first = False

        if self.ct.curr_img_idx >= 0:
            file_path = self.ct.image_files[self.ct.curr_img_idx]
            current_index = self.ct.current_history_index[file_path]
            
            if current_index < len(self.ct.image_history[file_path]) - 1:
                current_index += 1
                self.ct.current_history_index[file_path] = current_index

                cv2_img = self.get_img(file_path, current_index)

                self.ct.image_data[file_path] = cv2_img
                self.ct.image_viewer.display_cv2_image(cv2_img)

    def undo(self):
        if self.ct.curr_img_idx >= 0:

            file_path = self.ct.image_files[self.ct.curr_img_idx]
            current_index = self.ct.current_history_index[file_path]
            
            if current_index > 0:
                current_index -= 1
                self.ct.current_history_index[file_path] = current_index
                
                cv2_img = self.get_img(file_path, current_index)

                self.ct.image_data[file_path] = cv2_img
                self.ct.image_viewer.display_cv2_image(cv2_img)

   
    def update_image_history(self, file_path: str, cv2_img: np.ndarray):
        im = self.ct.load_image(file_path)

        if not np.array_equal(im, cv2_img):
            self.ct.image_data[file_path] = cv2_img
            
            # Update file path history
            history = self.ct.image_history[file_path]
            current_index = self.ct.current_history_index[file_path]
            
            # Remove any future history if we're not at the end
            del history[current_index + 1:]
            
            # # Save new image to temp file and add to history
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png', dir=self.ct.temp_dir)
            pil_image = Image.fromarray(cv2_img)
            pil_image.save(temp_file.name)

            history.append(temp_file.name)

            # Update in-memory history if this image is loaded
            if self.ct.in_memory_history.get(file_path, []):
                in_mem_history = self.ct.in_memory_history[file_path]
                del in_mem_history[current_index + 1:]
                in_mem_history.append(cv2_img.copy())

            self.ct.current_history_index[file_path] = len(history) - 1

    def get_img(self, file_path, current_index):
        if self.ct.in_memory_history.get(file_path, []):
            cv2_img = self.ct.in_memory_history[file_path][current_index]
        else:
            cv2_img = cv2.imread(self.ct.image_history[file_path][current_index])
            cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)

        return cv2_img