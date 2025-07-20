import os, sys
import logging
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings, QTranslator, QLocale
from PySide6.QtWidgets import QApplication  
from controller import ComicTranslate
from app.translations import ct_translations
from app import icon_resource

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
    icon = QIcon(":/icons/window_icon.png")  
    app.setWindowIcon(icon)

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
    
    # Start the event loop
    sys.exit(app.exec())


def get_system_language():
    locale = QLocale.system().name()  # Returns something like "en_US" or "zh_CN"
    
    # Special handling for Chinese
    if locale.startswith('zh_'):
        if locale in ['zh_CN', 'zh_SG']:
            return '简体中文'
        elif locale in ['zh_TW', 'zh_HK']:
            return '繁體中文'
    
    # For other languages, we can still use the first part of the locale
    lang_code = locale.split('_')[0]
    
    # Map the system language code to your application's language names
    lang_map = {
        'en': 'English',
        'ko': '한국어',
        'fr': 'Français',
        'ja': '日本語',
        'ru': 'русский',
        'de': 'Deutsch',
        'nl': 'Nederlands',
        'es': 'Español',
        'it': 'Italiano',
        'tr': 'Türkçe'
    }
    
    return lang_map.get(lang_code, 'English')  # Default to English if not found

def load_translation(app, language: str):
    translator = QTranslator(app)
    lang_code = {
        'English': 'en',
        '한국어': 'ko',
        'Français': 'fr',
        '日本語': 'ja',
        '简体中文': 'zh_CN',
        '繁體中文': 'zh_TW',
        'русский': 'ru',
        'Deutsch': 'de',
        'Nederlands': 'nl',
        'Español': 'es',
        'Italiano': 'it',
        'Türkçe': 'tr'
    }.get(language, 'en')

    # Load the translation file
    # if translator.load(f"ct_{lang_code}", "app/translations/compiled"):
    #     app.installTranslator(translator)
    # else:
    #     print(f"Failed to load translation for {language}")

    if translator.load(f":/translations/ct_{lang_code}.qm"):
        app.installTranslator(translator)
    else:
        print(f"Failed to load translation for {language}")

if __name__ == "__main__":
    main()

