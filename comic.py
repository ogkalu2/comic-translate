import os, sys
import logging
import hashlib
import json
import threading
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSettings, QTranslator, QLocale, \
    Qt, QTimer, QThread, QObject, Signal, Slot, QEvent
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication
from app.ui.splash_screen import SplashScreen


def _extract_project_file(argv: list[str]) -> str | None:
    for arg in argv[1:]:
        candidate = arg.strip('"')
        if candidate.lower().endswith(".ctpr") and os.path.exists(candidate):
            return candidate
    return None


def _single_instance_server_name() -> str:
    seed = os.path.abspath(__file__).lower().encode("utf-8", errors="ignore")
    digest = hashlib.sha1(seed).hexdigest()[:12]
    return f"ComicTranslate-{digest}"


def _encode_ipc_message(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8", errors="ignore")


def _decode_ipc_messages(raw: bytes) -> list[dict]:
    msgs: list[dict] = []
    for line in raw.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                msgs.append(obj)
                continue
        except Exception:
            pass
        msgs.append({"type": "open", "path": line})
    return msgs


def _try_forward_to_existing_instance(server_name: str, project_file: str | None) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(200):
        socket.abort()
        return False

    if project_file:
        socket.write(_encode_ipc_message({"type": "open", "path": project_file}))
    else:
        socket.write(_encode_ipc_message({"type": "activate"}))

    socket.flush()
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    socket.waitForDisconnected(200)
    return True


class OpenRequestRouter(QObject):
    open_project_requested = Signal(str)
    activate_requested = Signal()


class FileOpenEventFilter(QObject):
    def __init__(self, router: OpenRequestRouter):
        super().__init__()
        self._router = router

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FileOpen:
            try:
                path = event.file()
            except Exception:
                path = None
            if path:
                self._router.open_project_requested.emit(path)
            return True
        return False


class LoadingWorker(QObject):
    """Worker to load the application in a background thread."""
    finished = Signal(object)  # Signals when loading is complete with (project_file)
    failed = Signal()  # Signal when loading fails or is cancelled
    
    def __init__(self, icon, selected_language, sys_argv):
        super().__init__()
        self.icon = icon
        self.selected_language = selected_language
        self.sys_argv = sys_argv
        self.cancelled = False
        
    @Slot()
    def run(self):
        """Do the heavy loading in background thread."""
        try:
            if self.cancelled or QThread.currentThread().isInterruptionRequested():
                self.failed.emit()
                return

            # Pre-import heavy modules while the splash stays interactive.
            # IMPORTANT: don't create any QWidget/QObject instances here.
            try:
                import importlib
                importlib.import_module("controller")
            except Exception as e:
                logging.error(f"Error preloading modules: {e}")
                self.failed.emit()
                return

            # Check for file arguments
            project_file = _extract_project_file(self.sys_argv)
             
            if self.cancelled or QThread.currentThread().isInterruptionRequested():
                self.failed.emit()
                return
             
            # Signal completion
            self.finished.emit(project_file)
             
        except Exception as e:
            logging.error(f"Error during loading: {e}")
            self.failed.emit()


def main():
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
    )
    
    if sys.platform == "win32":
        # Necessary Workaround to set Taskbar Icon on Windows
        import ctypes
        myappid = u'ComicLabs.ComicTranslate' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Create QApplication directly instead of using the context manager
    app = QApplication(sys.argv)

    router = OpenRequestRouter()
    file_open_event_filter = FileOpenEventFilter(router)
    app.installEventFilter(file_open_event_filter)

    # Single-instance behavior (Windows/Linux). macOS typically routes file opens to the
    # existing instance via QFileOpenEvent, which we also handle above.
    server_name = _single_instance_server_name()
    startup_project_file = _extract_project_file(sys.argv)

    # If another instance is already running, forward open/activate then exit.
    if _try_forward_to_existing_instance(server_name, startup_project_file):
        sys.exit(0)

    # Become the primary instance: start an IPC server for subsequent launches.
    server = QLocalServer(app)
    if not server.listen(server_name):
        # Likely a stale server (crash). Remove and retry.
        QLocalServer.removeServer(server_name)
        server.listen(server_name)
     
    # Set the application icon
    # icon = QIcon(":/icons/window_icon.png")  
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_file_dir, 'resources', 'icons', 'icon.ico')
    icon = QIcon(icon_path)
    app.setWindowIcon(icon)

    # Show Splash Screen
    splash_pix = QPixmap(os.path.join(current_file_dir, 'resources', 'icons', 'splash.png'))
    # High DPI Scaling
    screen = app.primaryScreen()
    dpr = screen.devicePixelRatio()
    target_w, target_h = 400, 225
    splash_pix = splash_pix.scaled(int(target_w * dpr), int(target_h * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    splash_pix.setDevicePixelRatio(dpr)
    splash = SplashScreen(splash_pix)
    
    # Get language settings
    settings = QSettings("ComicLabs", "ComicTranslate")
    selected_language = settings.value('language', get_system_language())
    
    # Create worker and thread
    thread = QThread()
    worker = LoadingWorker(icon, selected_language, sys.argv)
    worker.moveToThread(thread)
    worker.finished.connect(worker.deleteLater)
    worker.failed.connect(worker.deleteLater)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    # thread.finished.connect(thread.deleteLater) # Removed to avoid RuntimeError on exit check
    
    # Connect signals
    class LoadingCoordinator(QObject):
        def __init__(self):
            super().__init__()
            self._ct = None
            self._pending_project_file: str | None = None

        @Slot(str)
        def request_open_project(self, path: str):
            if not path:
                return
            if not path.lower().endswith(".ctpr"):
                return
            if not os.path.exists(path):
                return
            norm = os.path.abspath(path)
            if self._ct is not None:
                try:
                    if not self._ct._confirm_start_new_project():
                        return
                except Exception:
                    pass
                self._ct.project_ctrl.thread_load_project(norm)
            else:
                self._pending_project_file = norm

        @Slot()
        def request_activate(self):
            if self._ct is not None:
                try:
                    self._ct.show()
                    self._ct.raise_()
                    self._ct.activateWindow()
                except Exception:
                    pass
            else:
                try:
                    splash.show()
                    splash.raise_()
                    splash.activateWindow()
                except Exception:
                    pass

        @Slot()
        def on_cancel(self):
            worker.cancelled = True
            thread.requestInterruption()
            thread.quit()
            splash.close()
            app.quit()

        @Slot(object)
        def on_finished(self, project_file):
            try:
                # Apply translation before creating any translated widgets.
                if selected_language != 'English':
                    load_translation(app, selected_language)

                from controller import ComicTranslate
                self._ct = ComicTranslate()
                self._ct.setWindowIcon(icon)

                try:
                    app.aboutToQuit.connect(self._ct.shutdown)
                except Exception:
                    pass

                splash.finish(self._ct)

                if project_file:
                    self.request_open_project(project_file)
                elif self._pending_project_file:
                    self.request_open_project(self._pending_project_file)
            except Exception as e:
                logging.error(f"Error during UI initialization: {e}")
                splash.close()
                app.quit()

        @Slot()
        def on_failed(self):
            splash.close()
            app.quit()

    coordinator = LoadingCoordinator()
    router.open_project_requested.connect(coordinator.request_open_project)
    router.activate_requested.connect(coordinator.request_activate)

    def _on_ipc_new_connection():
        while server.hasPendingConnections():
            sock = server.nextPendingConnection()

            def _read_and_handle(s=sock):
                raw = s.readAll().data()
                for msg in _decode_ipc_messages(raw):
                    msg_type = str(msg.get("type") or "").lower()
                    if msg_type == "activate":
                        router.activate_requested.emit()
                    elif msg_type == "open":
                        router.open_project_requested.emit(str(msg.get("path") or ""))

            sock.readyRead.connect(_read_and_handle)
            sock.disconnected.connect(sock.deleteLater)

    server.newConnection.connect(_on_ipc_new_connection)
    splash.cancelled.connect(coordinator.on_cancel)
    worker.finished.connect(coordinator.on_finished, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(coordinator.on_failed, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(worker.run)
    
    # Show splash and start loading thread
    splash.show()
    # Defer starting work until the event loop is running so the splash remains clickable.
    QTimer.singleShot(0, thread.start)
    
    # Start the event loop
    # Start the event loop
    exec_return = app.exec()

    # Clean up loading thread explicitly to avoid "QThread: Destroyed while thread is still running"
    if thread.isRunning():
        thread.quit()
        thread.wait()

    # Best-effort IPC cleanup (avoids stale local server entries after crashes).
    try:
        server.close()
        QLocalServer.removeServer(server_name)
    except Exception:
        pass

    # Prefer a graceful shutdown (lets Qt clean up thread-local storage).
    # Some 3rd-party libs can leave non-daemon Python threads running, which can
    # keep the process alive after sys.exit(). Use a watchdog as a last resort.
    def _hard_exit():
        try:
            os._exit(int(exec_return))
        except Exception:
            os._exit(0)

    watchdog = threading.Timer(5.0, _hard_exit)
    watchdog.daemon = True
    watchdog.start()

    raise SystemExit(exec_return)


def get_system_language():
    locale = QLocale.system().name()  # Returns something like "en_US" or "zh_CN"
    
    if locale.startswith('zh_'):
        return '简体中文'

    lang_code = locale.split('_')[0]
    
    lang_map = {
        'ko': '한국어',
        'fr': 'Français',
        'ru': 'русский',
        'de': 'Deutsch',
        'es': 'Español',
        'it': 'Italiano',
        'tr': 'Türkçe',
    }
    
    return lang_map.get(lang_code, 'English')  # Default to English if not found

def load_translation(app, language: str):
    translator = QTranslator(app)
    lang_code = {
        '한국어': 'ko',
        'Français': 'fr',
        '简体中文': 'zh-CN',
        'русский': 'ru',
        'Deutsch': 'de',
        'Español': 'es',
        'Italiano': 'it',
        'Türkçe': 'tr',
    }.get(language)

    if not lang_code:
        return

    # Load the translation file
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    tr_dir = os.path.join(current_file_dir, 'resources', 'translations', 'compiled')
    if translator.load(f"ct_{lang_code}", tr_dir):
        app.installTranslator(translator)
    else:
        print(f"Failed to load translation for {language}")

    # if translator.load(f":/translations/ct_{lang_code}.qm"):
    #     app.installTranslator(translator)
    # else:
    #     print(f"Failed to load translation for {language}")

if __name__ == "__main__":
    main()
