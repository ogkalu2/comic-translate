from __future__ import annotations

import os

from PySide6 import QtCore


class SearchReplaceJumpMixin:
    def _wait_for_webtoon_match_loaded(
        self,
        match_index: int,
        focus: bool,
        *,
        attempt_load: int,
        preserve_focus_state=None,
        nonce: int | None = None,
    ):
        if nonce is not None and nonce != self._jump_nonce:
            return
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]

        blk = self._find_block_in_current_image(m.key)
        if blk is not None:
            self._apply_match_selection(m, blk, focus, preserve_focus_state)
            return

        if attempt_load >= 35:
            self._apply_webtoon_fallback_selection(m, focus, preserve_focus_state)
            return

        QtCore.QTimer.singleShot(
            60,
            lambda: self._wait_for_webtoon_match_loaded(
                match_index,
                focus,
                attempt_load=attempt_load + 1,
                preserve_focus_state=preserve_focus_state,
                nonce=nonce,
            ),
        )

    def _jump_to_match_when_ready(
        self,
        match_index: int,
        focus: bool,
        attempt: int = 0,
        preserve_focus_state=None,
        nonce: int | None = None,
    ):
        if nonce is not None and nonce != self._jump_nonce:
            return
        if match_index < 0 or match_index >= len(self._matches):
            return
        m = self._matches[match_index]

        if self.main.curr_img_idx < 0:
            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60,
                lambda: self._jump_to_match_when_ready(match_index, focus, attempt + 1, nonce=nonce),
            )
            return

        current_file = self.main.image_files[self.main.curr_img_idx] if self.main.image_files else ""
        if os.path.normcase(current_file) != os.path.normcase(m.key.file_path):
            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60,
                lambda: self._jump_to_match_when_ready(
                    match_index,
                    focus,
                    attempt + 1,
                    preserve_focus_state,
                    nonce=nonce,
                ),
            )
            return

        blk = self._find_block_in_current_image(m.key)
        if blk is None:
            if getattr(self.main, "webtoon_mode", False):
                self._wait_for_webtoon_match_loaded(
                    match_index,
                    focus,
                    attempt_load=0,
                    preserve_focus_state=preserve_focus_state,
                    nonce=nonce,
                )
                return

            if attempt > 50:
                return
            QtCore.QTimer.singleShot(
                60,
                lambda: self._jump_to_match_when_ready(
                    match_index,
                    focus,
                    attempt + 1,
                    preserve_focus_state,
                    nonce=nonce,
                ),
            )
            return

        self._apply_match_selection(m, blk, focus, preserve_focus_state)

    def _jump_to_match(self, match_index: int, focus: bool = False, preserve_focus_state=None):
        if match_index < 0 or match_index >= len(self._matches):
            return
        match = self._matches[match_index]
        panel = self.main.search_panel
        panel.select_match(match)

        if not self._set_current_row_for_file(match.key.file_path):
            return
        self._jump_nonce += 1
        nonce = self._jump_nonce
        self._jump_to_match_when_ready(
            match_index,
            focus,
            attempt=0,
            preserve_focus_state=preserve_focus_state,
            nonce=nonce,
        )

    def _on_result_activated(self, match):
        try:
            idx = self._matches.index(match)
        except ValueError:
            idx = -1
        if idx >= 0:
            self._active_match_index = idx
        self._jump_to_match(self._active_match_index, focus=True)
