import os
import platform

def get_user_data_dir(app_name: str = "ComicTranslate") -> str:
    """
    Returns the platform-specific user data directory for the application.
    
    Windows: %LOCALAPPDATA%/<app_name>
    macOS: ~/Library/Application Support/<app_name>
    Linux: $XDG_DATA_HOME/<app_name> or ~/.local/share/<app_name>
    """
    system = platform.system()
    
    if system == "Windows":
        base_dir = os.getenv('LOCALAPPDATA')
        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif system == "Darwin":
        base_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        # Linux / Unix
        base_dir = os.getenv('XDG_DATA_HOME')
        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), ".local", "share")
            
    return os.path.join(base_dir, app_name)
