import os, sys
import logging
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSettings, QTranslator, QLocale, Qt
from PySide6.QtWidgets import QApplication, QSplashScreen

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
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    # Import Controller after splash is shown (heavy import)
    from controller import ComicTranslate

    settings = QSettings("ComicLabs", "ComicTranslate")
    selected_language = settings.value('language', get_system_language())
    if selected_language != 'English':
        load_translation(app, selected_language)  

    ct = ComicTranslate()

    # Check for file arguments
    if len(sys.argv) > 1:
        project_file = sys.argv[1]
        if os.path.exists(project_file) and project_file.endswith(".ctpr"):
            ct.thread_load_project(project_file)

    ct.show()
    splash.finish(ct)
    ct.setWindowIcon(icon)
    
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

