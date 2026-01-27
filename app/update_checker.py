import os
import platform
import logging
import requests
import subprocess
import tempfile
from packaging import version
from PySide6.QtCore import QObject, Signal, QThread, QStandardPaths
from app.version import __version__

logger = logging.getLogger(__name__)

class UpdateChecker(QObject):
    """
    Checks for updates on GitHub and handles downloading/running installers.
    """
    update_available = Signal(str, str, str)  # version, release_notes, download_url
    up_to_date = Signal()
    error_occurred = Signal(str)
    download_progress = Signal(int)
    download_finished = Signal(str) # file_path

    REPO_OWNER = "ogkalu2"
    REPO_NAME = "comic-translate"

    def __init__(self):
        super().__init__()
        self._worker_thread = None
        self._worker = None

    def _safe_stop_thread(self):
        try:
            if self._worker_thread and self._worker_thread.isRunning():
                self._worker_thread.quit()
                self._worker_thread.wait()
        except RuntimeError:
            # The C++ object has been deleted
            pass
        except Exception as e:
            logger.error(f"Error stopping thread: {e}")
        self._worker_thread = None

    def check_for_updates(self):
        """Starts the check in a background thread."""
        self._safe_stop_thread()
            
        self._worker_thread = QThread()
        self._worker = UpdateWorker(self.REPO_OWNER, self.REPO_NAME, __version__)
        self._worker.moveToThread(self._worker_thread)
        
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        
        self._worker.update_available.connect(self.update_available)
        self._worker.up_to_date.connect(self.up_to_date)
        self._worker.error.connect(self.error_occurred)
        
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    def download_installer(self, url, filename):
        """Starts the download in a background thread."""
        self._safe_stop_thread()

        self._worker_thread = QThread()
        self._worker = DownloadWorker(url, filename)
        self._worker.moveToThread(self._worker_thread)
        
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        
        self._worker.progress.connect(self.download_progress)
        self._worker.finished_path.connect(self.download_finished)
        self._worker.error.connect(self.error_occurred)
        
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    def run_installer(self, file_path):
        """Executes the installer based on the platform."""
        try:
            system = platform.system()
            if system == "Windows":
                # Use os.startfile; Windows will parse the installer manifest
                # and trigger UAC only if the installer requires it.
                os.startfile(file_path)
            elif system == "Darwin": # macOS
                subprocess.Popen(["open", file_path])
        except Exception as e:
            self.error_occurred.emit(f"Failed to launch installer: {e}")

    def shutdown(self):
        """Stops any active worker thread (best-effort)."""
        self._safe_stop_thread()
        self._worker_thread = None
        self._worker = None


class UpdateWorker(QObject):
    update_available = Signal(str, str, str)
    up_to_date = Signal()
    error = Signal(str)
    finished = Signal()

    def __init__(self, owner, repo, current_version):
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.current_version = current_version

    def run(self):
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            latest_tag = data.get("tag_name", "").lstrip("v")
            if not latest_tag:
                 self.error.emit("Could not parse version from release.")
                 self.finished.emit()
                 return

            if version.parse(latest_tag) > version.parse(self.current_version):
                # Find appropriate asset
                asset_url = None
                system = platform.system()
                if system == "Windows":
                    for asset in data.get("assets", []):
                        if asset["name"].endswith(".exe") or asset["name"].endswith(".msi"):
                            asset_url = asset["browser_download_url"]
                            break
                elif system == "Darwin":
                    for asset in data.get("assets", []):
                        if asset["name"].endswith(".dmg") or asset["name"].endswith(".pkg"):
                            asset_url = asset["browser_download_url"]
                            break
                
                if asset_url:
                    self.update_available.emit(latest_tag, data.get("html_url", ""), asset_url)
                else:
                    self.error.emit(f"New version {latest_tag} available, but no installer found for your OS.")
            else:
                self.up_to_date.emit()

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    progress = Signal(int)
    finished_path = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, url, filename):
        super().__init__()
        self.url = url
        self.filename = filename

    def run(self):
        try:
            # Download to Downloads directory
            download_dir = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            if not download_dir:
                download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            
            # Fallback to temp if Downloads doesn't exist
            if not os.path.exists(download_dir):
                download_dir = tempfile.gettempdir()

            save_path = os.path.join(download_dir, self.filename)
            
            response = requests.get(self.url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded_size / total_size) * 100)
                            self.progress.emit(percent)
            
            self.finished_path.emit(save_path)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
