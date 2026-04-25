import os
import hashlib
import uuid
from PySide6.QtGui import QUndoCommand
from .base import PatchCommandBase
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
        self.group_id = uuid.uuid4().hex
        self._skip_next_draw = False

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
            imk.write_image(png_path, patch_img)

            # compute a composite hash of the image and its bounding box for deduplication
            with open(png_path, 'rb') as f:
                img_bytes = f.read()
            bbox_bytes = str(bbox).encode('utf-8')
            img_hash = hashlib.sha256(img_bytes + bbox_bytes).hexdigest()

            prop = {
                'bbox': bbox,
                'png_path': png_path,
                'hash': img_hash,
                'group_id': self.group_id,
            }
            
            # Add webtoon mode information if present
            if 'scene_pos' in patch:
                prop['scene_pos'] = patch['scene_pos']
            if 'page_index' in patch:
                prop['page_index'] = patch['page_index']
                
            self.properties_list.append(prop)

    @classmethod
    def from_saved_properties(cls, ct, properties_list, file_path):
        cmd = cls.__new__(cls)
        QUndoCommand.__init__(cmd, "Insert patches")
        cmd.ct = ct
        cmd.viewer = ct.image_viewer
        cmd.scene = cmd.viewer._scene
        cmd.file_path = file_path
        cmd.display = True
        cmd._skip_next_draw = True

        normalized = []
        group_id = None
        fallback_group_id = uuid.uuid4().hex
        for prop in properties_list:
            entry = dict(prop)
            entry_group_id = entry.get("group_id") or fallback_group_id
            entry["group_id"] = entry_group_id
            if group_id is None:
                group_id = entry_group_id
            normalized.append(entry)

        cmd.group_id = group_id or fallback_group_id
        cmd.properties_list = normalized
        return cmd

    def _is_target_page_visible(self):
        if self.ct.webtoon_mode:
            try:
                page_index = self.ct.image_files.index(self.file_path)
            except ValueError:
                return False
            manager = getattr(self.ct.image_viewer, "webtoon_manager", None)
            loaded_pages = getattr(manager, "loaded_pages", set()) if manager is not None else set()
            return page_index in loaded_pages

        if self.ct.curr_img_idx < 0 or self.ct.curr_img_idx >= len(self.ct.image_files):
            return False
        current_file = self.ct.image_files[self.ct.curr_img_idx]
        return (
            current_file == self.file_path
            and self.ct.central_stack.currentWidget() == self.ct.viewer_page
            and self.ct.image_viewer.hasPhoto()
        )

    def _register_patches(self):
        # Ensure top-level storage exists
        patches_list = self.ct.image_patches.setdefault(self.file_path, [])
        mem_list = self.ct.in_memory_patches.setdefault(self.file_path, [])
        should_draw = self._is_target_page_visible()
        patch_hashes = {patch.get("hash") for patch in patches_list}
        mem_hashes = {patch.get("hash") for patch in mem_list}

        for prop in self.properties_list:
            # skip duplicates by composite hash
            prop_hash = prop["hash"]
            if prop_hash in patch_hashes:
                continue

            # add to persistent store
            patch_entry = {
                'bbox': prop['bbox'],
                'png_path': prop['png_path'],
                'hash': prop_hash,
                'group_id': prop['group_id'],
            }
            # Save scene position and page index for webtoon mode
            if 'scene_pos' in prop:
                patch_entry['scene_pos'] = prop['scene_pos']
            if 'page_index' in prop:
                patch_entry['page_index'] = prop['page_index']
            patches_list.append(patch_entry)
            patch_hashes.add(prop_hash)

            # only load into memory if being displayed
            if should_draw and prop_hash not in mem_hashes:
                img_data = imk.read_image(prop['png_path'])
                mem_list.append({
                    'bbox': prop['bbox'],
                    'image': img_data,
                    'hash': prop_hash
                })
                mem_hashes.add(prop_hash)

    def _unregister_patches(self):
        patches_list = self.ct.image_patches.get(self.file_path, [])
        mem_list = self.ct.in_memory_patches.get(self.file_path, [])

        for prop in self.properties_list:
            patches_list[:] = [p for p in patches_list if p['hash'] != prop['hash']]
            mem_list[:] = [p for p in mem_list if p['hash'] != prop['hash']]

    def _draw_pixmaps(self):
        if not self._is_target_page_visible():
            return
        
        # add new patch items
        for prop in self.properties_list:
            if not self.find_matching_item(self.scene, prop):
                self.create_patch_item(prop, self.viewer)

    def _remove_pixmaps(self):
        # remove items matching each prop
        for prop in self.properties_list:
            existing = self.find_matching_item(self.scene, prop)
            if existing:
                self.scene.removeItem(existing)

    def redo(self):
        self._register_patches()
        if self._skip_next_draw:
            self._skip_next_draw = False
            return
        self._draw_pixmaps()

    def undo(self):
        self._remove_pixmaps()
        self._unregister_patches()
        main = self.ct
        if main is not None:
            try:
                main.invalidate_page_render_pipeline(self.file_path)
            except Exception:
                pass

