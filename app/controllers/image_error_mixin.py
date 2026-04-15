from __future__ import annotations

import os
from typing import List

from PySide6 import QtCore

from app.ui.dayu_widgets.message import MMessage
from app.ui.messages import Messages
from pipeline.page_state import (
    get_active_viewer_state,
    has_runtime_patches as page_has_runtime_patches,
    resolve_page_target_lang,
)
from pipeline.render_state import get_target_snapshot, set_target_snapshot
from pipeline.stage_state import finalize_render_stage


class ImageErrorMixin:
    def _reconcile_render_snapshot_state(self, file_path: str, target_lang: str | None = None) -> None:
        state = self.main.image_states.get(file_path)
        if not state:
            return

        active_target = resolve_page_target_lang(
            state,
            preferred_target=target_lang or self.main.t_combo.currentText(),
            pipeline_state=state.get("pipeline_state"),
        )
        if not active_target:
            return

        snapshot = get_target_snapshot(state, active_target)
        viewer_state = get_active_viewer_state(
            state,
            target_lang=active_target,
            fallback_to_viewer_state=True,
        )
        if not snapshot and state.get("target_lang") == active_target and viewer_state.get("text_items_state"):
            snapshot = set_target_snapshot(state, active_target, viewer_state)

        text_items_state = (snapshot or {}).get("text_items_state") or []
        if not text_items_state:
            return

        finalize_render_stage(
            state,
            active_target,
            has_runtime_patches=page_has_runtime_patches(
                state,
                self.main.image_patches,
                file_path,
            ),
            ui_stage="render",
        )

    def _is_content_flagged_error(self, error: str) -> bool:
        lowered = (error or "").lower()
        return (
            "flagged as unsafe" in lowered
            or "content was flagged" in lowered
            or "safety filters" in lowered
        )

    def _resolve_skip_message_type(self, skip_reason: str, error: str) -> str:
        if self._is_content_flagged_error(error):
            return MMessage.ErrorType
        if skip_reason == "Text Blocks":
            return MMessage.InfoType
        return MMessage.WarningType

    def _summarize_skip_error(self, error: str) -> str:
        if not error:
            return ""
        if "Traceback" not in error and len(error) < 500:
            return error.strip()

        for raw_line in error.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("traceback"):
                break
            if line.startswith('File "') or line.startswith("File '"):
                continue
            if line.startswith("During handling of the above exception"):
                continue
            return line
        return ""

    def _build_skip_message(self, image_path: str, skip_reason: str, error: str) -> str:
        file_name = os.path.basename(image_path)
        reason = self._summarize_skip_error(error)
        t = QtCore.QCoreApplication.translate

        message_map = {
            "Text Blocks": t("Messages", "No Text Blocks Detected.\nSkipping:"),
            "OCR": t("Messages", "Could not recognize detected text.\nSkipping:"),
            "Translator": t("Messages", "Could not get translations.\nSkipping:"),
            "OCR Chunk Failed": t("Messages", "Could not recognize webtoon chunk.\nSkipping:"),
            "Translation Chunk Failed": t("Messages", "Could not translate webtoon chunk.\nSkipping:"),
        }

        base = message_map.get(
            skip_reason,
            t("Messages", "Page processing failed.\nSkipping:"),
        )
        text = f"{base} {file_name}"
        if reason:
            text += f"\n{reason}"
        return text

    def _close_transient_skip_notice(self):
        msg = self._active_transient_skip_message
        if msg is None:
            return
        try:
            msg.close()
        except Exception:
            pass
        self._active_transient_skip_message = None

    def _dispatch_to_main_thread(self, fn, *args):
        QtCore.QTimer.singleShot(0, lambda: fn(*args))

    def _dispatch_result(self, on_result, result):
        self._dispatch_to_main_thread(on_result, result)

    def _dispatch_error(self, error_handler, error):
        self._dispatch_to_main_thread(error_handler, error)

    def _show_transient_skip_notice(self, text: str, dayu_type: str):
        self._close_transient_skip_notice()
        show_func = {
            MMessage.InfoType: MMessage.info,
            MMessage.WarningType: MMessage.warning,
            MMessage.ErrorType: MMessage.error,
        }.get(dayu_type, MMessage.warning)
        self._active_transient_skip_message = show_func(
            text=text,
            parent=self.main,
            duration=6,
            closable=True,
        )

    def _hide_active_page_skip_error(self):
        msg = self._active_page_error_message
        if msg is None:
            self._active_page_error_path = None
            return
        self._suppress_dismiss_message_ids.add(id(msg))
        try:
            msg.close()
        except Exception:
            pass
        self._active_page_error_message = None
        self._active_page_error_path = None

    def _on_page_error_closed(self, file_path: str, message: MMessage):
        msg_id = id(message)
        if msg_id in self._suppress_dismiss_message_ids:
            self._suppress_dismiss_message_ids.discard(msg_id)
        else:
            state = self._page_skip_errors.get(file_path)
            if state:
                state["dismissed"] = True
        if self._active_page_error_message is message:
            self._active_page_error_message = None
            self._active_page_error_path = None

    def _show_page_skip_error_for_file(self, file_path: str):
        state = self._page_skip_errors.get(file_path)
        if not state or state.get("dismissed"):
            return
        if (
            self._active_page_error_path == file_path
            and self._active_page_error_message is not None
            and self._active_page_error_message.isVisible()
        ):
            return

        self._hide_active_page_skip_error()
        show_func = {
            MMessage.InfoType: MMessage.info,
            MMessage.WarningType: MMessage.warning,
            MMessage.ErrorType: MMessage.error,
        }.get(state.get("dayu_type"), MMessage.warning)
        message = show_func(
            text=state.get("text", ""),
            parent=self.main,
            duration=None,
            closable=True,
        )
        message.sig_closed.connect(
            lambda fp=file_path, msg=message: self._on_page_error_closed(fp, msg)
        )
        self._active_page_error_message = message
        self._active_page_error_path = file_path

    def handle_webtoon_page_focus(self, file_path: str, explicit_navigation: bool):
        if explicit_navigation:
            self._show_page_skip_error_for_file(file_path)
        else:
            self._hide_active_page_skip_error()

    def _clear_page_skip_error(self, file_path: str):
        self._page_skip_errors.pop(file_path, None)
        if self._active_page_error_path == file_path:
            self._hide_active_page_skip_error()

    def clear_page_skip_errors_for_paths(self, file_paths: List[str]):
        for file_path in file_paths:
            self._clear_page_skip_error(file_path)

    def on_render_state_ready(self, file_path: str):
        self._reconcile_render_snapshot_state(file_path)
        if self.main.curr_img_idx < 0 or self.main.curr_img_idx >= len(self.main.image_files):
            self.main.stage_nav_ctrl.refresh_stage_buttons(file_path)
            return
        current_file = self.main.image_files[self.main.curr_img_idx]
        if current_file == file_path:
            self.main.stage_nav_ctrl.restore_current_page_view()
        else:
            self.main.stage_nav_ctrl.refresh_stage_buttons(file_path)

    def on_image_skipped(self, image_path: str, skip_reason: str, error: str):
        summarized_error = self._summarize_skip_error(error)
        if hasattr(self.main, "register_batch_skip"):
            self.main.register_batch_skip(image_path, skip_reason, summarized_error)

        if self._is_content_flagged_error(error):
            reason = summarized_error.split(": ")[-1] if ": " in summarized_error else summarized_error
            file_name = os.path.basename(image_path)
            flagged_msg = Messages.get_content_flagged_text(
                details=reason,
                context=skip_reason,
            )
            skip_prefix = QtCore.QCoreApplication.translate("Messages", "Skipping:")
            text = f"{skip_prefix} {file_name}\n{flagged_msg}"
        else:
            text = self._build_skip_message(image_path, skip_reason, summarized_error)
        dayu_type = self._resolve_skip_message_type(skip_reason, error)
        self._page_skip_errors[image_path] = {
            "text": text,
            "dayu_type": dayu_type,
            "dismissed": False,
        }

        if getattr(self.main, "_batch_active", False):
            return

        if self._current_file_path() == image_path:
            self._hide_active_page_skip_error()
            self._show_page_skip_error_for_file(image_path)
            return

        self._show_transient_skip_notice(text, dayu_type)
        if self._active_page_error_path == image_path:
            self._hide_active_page_skip_error()
            self._show_page_skip_error_for_file(image_path)
