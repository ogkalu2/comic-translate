from __future__ import annotations

import mimetypes
import os
import shutil
import tempfile
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PySide6 import QtCore, QtGui, QtWidgets


class ImportDownloadWorker(QtCore.QThread):
    """Worker thread responsible for downloading images from a WFWF URL."""

    progress = QtCore.Signal(int, int)
    error = QtCore.Signal(str)
    completed = QtCore.Signal(list)

    def __init__(self, url: str, temp_dir: str, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.url = url
        self.temp_dir = temp_dir
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0 Safari/537.36"
                ),
                "Referer": url,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _guess_extension(self, img_url: str, response: requests.Response) -> str:
        parsed = urlparse(img_url)
        ext = os.path.splitext(parsed.path)[1].lower()
        valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
        if ext in valid_exts:
            return ".jpg" if ext == ".jpeg" else ext

        mime_ext = mimetypes.guess_extension(response.headers.get("Content-Type", ""))
        if mime_ext:
            mime_ext = ".jpg" if mime_ext == ".jpe" else mime_ext
            if mime_ext in valid_exts:
                return mime_ext
        return ".jpg"

    def run(self) -> None:  # noqa: D401
        try:
            response = self._session.get(self.url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            self.error.emit(str(exc))
            return

        soup = BeautifulSoup(response.text, "html.parser")
        images = soup.find_all("img", class_="v-img lazyload")
        candidate_urls = []
        for img in images:
            src = img.attrs.get("data-original") or img.attrs.get("src")
            if not src:
                continue
            candidate_urls.append(urljoin(self.url, src))

        # Deduplicate while preserving order
        seen: set[str] = set()
        download_urls: list[str] = []
        for candidate in candidate_urls:
            if candidate not in seen:
                seen.add(candidate)
                download_urls.append(candidate)

        if not download_urls:
            self.error.emit("No downloadable images were found at the provided URL.")
            return

        total = len(download_urls)
        downloaded_files: list[str] = []
        for index, img_url in enumerate(download_urls, start=1):
            try:
                img_response = self._session.get(img_url, timeout=60)
                img_response.raise_for_status()
            except requests.RequestException as exc:
                self.error.emit(str(exc))
                return

            extension = self._guess_extension(img_url, img_response)
            filename = f"{index:04d}{extension}"
            img_path = os.path.join(self.temp_dir, filename)
            try:
                with open(img_path, "wb") as handle:
                    handle.write(img_response.content)
            except OSError as exc:
                self.error.emit(str(exc))
                return

            downloaded_files.append(img_path)
            self.progress.emit(index, total)

        self.completed.emit(downloaded_files)


class ImportWFWFDialog(QtWidgets.QDialog):
    """Dialog allowing the user to import images from a WFWF URL."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Import from WFWF"))
        self.setModal(True)

        self.temp_dir = tempfile.mkdtemp(prefix="wfwf_import_")
        self._cleanup_on_close = True
        self.download_worker: ImportDownloadWorker | None = None
        self._downloaded_files: list[str] = []

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        description = QtWidgets.QLabel(
            self.tr(
                "Paste the WFWF chapter URL. The application will download and order "
                "all images found on the page."
            )
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.url_input = QtWidgets.QLineEdit(self)
        self.url_input.setPlaceholderText(self.tr("https://wfwf443.com/..."))
        self.url_input.returnPressed.connect(self.start_download)
        layout.addWidget(self.url_input)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QtWidgets.QLabel(self)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.import_button = self.button_box.addButton(
            self.tr("Import"), QtWidgets.QDialogButtonBox.AcceptRole
        )
        self.cancel_button = self.button_box.addButton(
            QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.rejected.connect(self.reject)
        self.import_button.clicked.connect(self.start_download)
        layout.addWidget(self.button_box)

    def start_download(self) -> None:
        url = self.get_url()
        if not url:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Missing URL"),
                self.tr("Please enter a valid WFWF URL."),
            )
            return

        if self.download_worker and self.download_worker.isRunning():
            return

        self._toggle_ui_for_download(True)
        self.status_label.setText(self.tr("Fetching page..."))
        self.status_label.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

        self.download_worker = ImportDownloadWorker(url, self.temp_dir, self)
        self.download_worker.progress.connect(self._on_progress)
        self.download_worker.error.connect(self._on_error)
        self.download_worker.completed.connect(self._on_completed)
        self.download_worker.start()

    def _toggle_ui_for_download(self, downloading: bool) -> None:
        self.url_input.setEnabled(not downloading)
        self.import_button.setEnabled(not downloading)
        self.cancel_button.setEnabled(not downloading)

    def _on_progress(self, current: int, total: int) -> None:
        if self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.status_label.setText(
            self.tr("Downloading image {current} of {total}...").format(
                current=current, total=total
            )
        )

    def _on_error(self, message: str) -> None:
        self._toggle_ui_for_download(False)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.download_worker = None
        QtWidgets.QMessageBox.critical(
            self,
            self.tr("Download failed"),
            message,
        )

    def _on_completed(self, files: list[str]) -> None:
        self._downloaded_files = files
        self._cleanup_on_close = False
        self.download_worker = None
        self.accept()

    def get_url(self) -> str:
        return self.url_input.text().strip()

    def get_temp_dir(self) -> str:
        return self.temp_dir

    def get_downloaded_files(self) -> list[str]:
        return list(self._downloaded_files)

    def cleanup(self) -> None:
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def reject(self) -> None:
        super().reject()
        if self._cleanup_on_close:
            self.cleanup()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        try:
            if self._cleanup_on_close:
                self.cleanup()
        finally:
            super().closeEvent(event)
