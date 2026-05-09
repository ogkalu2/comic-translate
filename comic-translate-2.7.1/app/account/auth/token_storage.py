import keyring
import logging
from typing import Optional
from PySide6.QtCore import QSettings

logger = logging.getLogger(__name__)

# Constants
KEYRING_SERVICE = "comic-translate"
SETTINGS_GROUP = "auth"

def get_settings():
    return QSettings("ComicLabs", "ComicTranslate")

def set_token(name: str, value: str):
    """Securely store a token, chunking it if necessary. Fallback to QSettings if keyring fails."""
    # First, try to clear any existing chunks to avoid stale data
    delete_token(name)
    
    # Use a smaller chunk size to be safe (512 chars ~ 512-2048 bytes depending on encoding)
    chunk_size = 512 
    chunks = [value[i:i+chunk_size] for i in range(0, len(value), chunk_size)]
    
    try:
        # If it fits in one, just save it normally
        if len(chunks) == 1:
            keyring.set_password(KEYRING_SERVICE, name, value)
            return

        # Otherwise, save counts and chunks
        keyring.set_password(KEYRING_SERVICE, f"{name}_chunks", str(len(chunks)))
        for i, chunk in enumerate(chunks):
            keyring.set_password(KEYRING_SERVICE, f"{name}_chunk_{i}", chunk)
            
    except Exception as e:
        logger.error(f"Keyring storage failed for {name} (Size: {len(value)}): {e}. Falling back to QSettings.")
        # Fallback: Store in QSettings (Encodings issues handled by QSettings, hopefully)
        # Note: This is less secure, but allows the app to function.
        settings = get_settings()
        settings.setValue(f"{SETTINGS_GROUP}/{name}", value)

def get_token(name: str) -> Optional[str]:
    """Retrieve a token, checking keyring first, then QSettings callback."""
    # 1. Try generic keyring lookup
    try:
        token = keyring.get_password(KEYRING_SERVICE, name)
        if token:
            return token
    except Exception: pass
    
    # 2. Try keyring chunks
    try:
        chunk_count_str = keyring.get_password(KEYRING_SERVICE, f"{name}_chunks")
        if chunk_count_str:
            chunk_count = int(chunk_count_str)
            assembled_token = ""
            for i in range(chunk_count):
                chunk = keyring.get_password(KEYRING_SERVICE, f"{name}_chunk_{i}")
                if chunk is None:
                    raise ValueError("Missing chunk")
                assembled_token += chunk
            return assembled_token
    except Exception: pass

    # 3. Fallback: QSettings
    settings = get_settings()
    if settings.contains(f"{SETTINGS_GROUP}/{name}"):
        return str(settings.value(f"{SETTINGS_GROUP}/{name}"))
        
    return None

def delete_token(name: str):
    """Delete a token and all its potential chunks (keyring & QSettings)."""
    # Keyring cleanup
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except Exception: pass

    try:
        chunk_count_str = keyring.get_password(KEYRING_SERVICE, f"{name}_chunks")
        if chunk_count_str:
            chunk_count = int(chunk_count_str)
            keyring.delete_password(KEYRING_SERVICE, f"{name}_chunks")
            for i in range(chunk_count):
                try:
                    keyring.delete_password(KEYRING_SERVICE, f"{name}_chunk_{i}")
                except Exception: pass
    except Exception: pass
    
    # QSettings cleanup
    settings = get_settings()
    if settings.contains(f"{SETTINGS_GROUP}/{name}"):
        settings.remove(f"{SETTINGS_GROUP}/{name}")
