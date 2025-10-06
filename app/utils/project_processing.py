from __future__ import annotations

import os
import shutil
import tempfile
from typing import Iterable

from PySide6 import QtWidgets

from app.ui.dayu_widgets.message import MMessage
from app.ui.dialogs.import_wfwf_dialog import ImportWFWFDialog


def _copy_and_order_images(image_paths: Iterable[str]) -> list[str]:
    """Copy downloaded images to a dedicated temp directory in order."""
    project_dir = tempfile.mkdtemp(prefix="wfwf_project_")
    ordered_files: list[str] = []

    for index, src in enumerate(image_paths, start=1):
        extension = os.path.splitext(src)[1] or ".jpg"
        # Normalise jpeg extension
        if extension.lower() == ".jpeg":
            extension = ".jpg"
        dest = os.path.join(project_dir, f"{index:04d}{extension}")
        shutil.copy2(src, dest)
        ordered_files.append(dest)

    return ordered_files


def import_from_wfwf(main_window: QtWidgets.QWidget) -> None:
    """Launch the WFWF import dialog and load the downloaded images."""
    dialog = ImportWFWFDialog(main_window)

    if dialog.exec() != QtWidgets.QDialog.Accepted:
        dialog.cleanup()
        return

    downloaded_files = dialog.get_downloaded_files()
    if not downloaded_files:
        dialog.cleanup()
        MMessage.error(
            text=main_window.tr("No images were downloaded from the provided URL."),
            parent=main_window,
            duration=None,
            closable=True,
        )
        return

    try:
        ordered_files = _copy_and_order_images(downloaded_files)
    except OSError as exc:
        dialog.cleanup()
        MMessage.error(
            text=main_window.tr("Failed to prepare downloaded images: {error}").format(error=str(exc)),
            parent=main_window,
            duration=None,
            closable=True,
        )
        return

    dialog.cleanup()

    main_window.image_ctrl.thread_load_images(ordered_files)
    MMessage.success(
        text=main_window.tr("WFWF images downloaded successfully."),
        parent=main_window,
        duration=3000,
        closable=True,
    )
