import os
import hashlib
import uuid
from PySide6.QtGui import QUndoCommand
from .base import PatchCommandBase
from PIL import Image
import imkit as imk

class PatchInsertCommand(QUndoCommand, PatchCommandBase):
    """
    A single command that inserts **one patch-group** (the patches created by a
    single inpaint call) and is fully undo/redo-able and serialisable.
    """
    def __init__(self, ct, patches, file_path, display=True):
        super().__init__("Insert patches")
        self.ct = ct
        self.viewer = ct.image_viewer
        self.scene = self.viewer._scene
        self.file_path = file_path     # page the patches belong to
        self.display = display

        # prepare lists of patch properties with composite hashes for deduplication
        self.properties_list = []
        for idx, patch in enumerate(patches):
            # Extract data from patch dictionary
            bbox = patch['bbox']
            patch_img = patch['image']

            # spill every image patch to a temp PNG (if not already on disk)
            sub_dir = os.path.join(ct.temp_dir,
                                   "inpaint_patches",
                                   os.path.basename(file_path))
            os.makedirs(sub_dir, exist_ok=True)
            png_path = os.path.join(sub_dir, f"patch_{uuid.uuid4().hex[:8]}_{idx}.png")
            # patch_img is produced by the inpainter in RGB color order.
            # Save directly with PIL (which expects RGB) to preserve correct channel order.
            Image.fromarray(patch_img).save(png_path)

            # compute a composite hash of the image and its bounding box for deduplication
            with open(png_path, 'rb') as f:
                img_bytes = f.read()
            bbox_bytes = str(bbox).encode('utf-8')
            img_hash = hashlib.sha256(img_bytes + bbox_bytes).hexdigest()

            prop = {
                'bbox': bbox,
                'png_path': png_path,
                'hash': img_hash
            }
            
            # Add webtoon mode information if present
            if 'scene_pos' in patch:
                prop['scene_pos'] = patch['scene_pos']
            if 'page_index' in patch:
                prop['page_index'] = patch['page_index']
                
            self.properties_list.append(prop)

    def _register_patches(self):
        # Ensure top-level storage exists
        patches_list = self.ct.image_patches.setdefault(self.file_path, [])
        if self.display:
            mem_list = self.ct.in_memory_patches.setdefault(self.file_path, [])

        for prop in self.properties_list:
            # skip duplicates by composite hash
            if any(p['hash'] == prop['hash'] for p in patches_list):
                continue

            # add to persistent store
            patch_entry = {
                'bbox': prop['bbox'],
                'png_path': prop['png_path'],
                'hash': prop['hash']
            }
            # Save scene position and page index for webtoon mode
            if 'scene_pos' in prop:
                patch_entry['scene_pos'] = prop['scene_pos']
            if 'page_index' in prop:
                patch_entry['page_index'] = prop['page_index']
            patches_list.append(patch_entry)

            # only load into memory if being displayed
            if self.display:
                img_data = imk.read_image(prop['png_path'])
                mem_list.append({
                    'bbox': prop['bbox'],
                    'image': img_data,
                    'hash': prop['hash']
                })

    def _unregister_patches(self):
        patches_list = self.ct.image_patches.get(self.file_path, [])
        if self.display:
            mem_list = self.ct.in_memory_patches.get(self.file_path, [])

        for prop in self.properties_list:
            patches_list[:] = [p for p in patches_list if p['hash'] != prop['hash']]
            if self.display:
                mem_list[:] = [p for p in mem_list if p['hash'] != prop['hash']]

    def _draw_pixmaps(self):
        # only draw when display=True
        if not self.display:
            return
        
        # add new patch items
        for prop in self.properties_list:
            if not self.find_matching_item(self.scene, prop):
                self.create_patch_item(prop, self.viewer)

    def _remove_pixmaps(self):
        # only remove when display=True
        if not self.display:
            return
        # remove items matching each prop
        for prop in self.properties_list:
            existing = self.find_matching_item(self.scene, prop)
            if existing:
                self.scene.removeItem(existing)

    def redo(self):
        self._register_patches()
        self._draw_pixmaps()
        self.display = True

    def undo(self):
        self._remove_pixmaps()
        self._unregister_patches()

