import os, sys
import logging
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSettings, QTranslator, QLocale, \
    Qt, QTimer, QThread, QObject, Signal, Slot
from PySide6.QtWidgets import QApplication
from app.ui.splash_screen import SplashScreen


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
            project_file = None
            for arg in self.sys_argv[1:]:
                candidate = arg.strip('"')
                if candidate.lower().endswith(".ctpr") and os.path.exists(candidate):
                    project_file = candidate
                    break
            
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
    
    # Set the application icon
    # icon = QIcon(":/icons/window_icon.png")  
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_file_dir, 'resources', 'icon.ico')
    icon = QIcon(icon_path)
    app.setWindowIcon(icon)

    # Show Splash Screen
    splash_pix = QPixmap(os.path.join(current_file_dir, 'resources', 'splash.png'))
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
    thread.finished.connect(thread.deleteLater)
    
    # Connect signals
    class LoadingCoordinator(QObject):
        def __init__(self):
            super().__init__()

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
                ct = ComicTranslate()
                ct.setWindowIcon(icon)

                splash.finish(ct)

                if project_file:
                    ct.thread_load_project(project_file)
            except Exception as e:
                logging.error(f"Error during UI initialization: {e}")
                splash.close()
                app.quit()

        @Slot()
        def on_failed(self):
            splash.close()
            app.quit()

    coordinator = LoadingCoordinator()
    splash.cancelled.connect(coordinator.on_cancel)
    worker.finished.connect(coordinator.on_finished, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(coordinator.on_failed, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(worker.run)
    
    # Show splash and start loading thread
    splash.show()
    # Defer starting work until the event loop is running so the splash remains clickable.
    QTimer.singleShot(0, thread.start)
    
    # Start the event loop
    sys.exit(app.exec())


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

