import platform
import logging

logger = logging.getLogger(__name__)

def get_client_os() -> str:
    """
    Returns the operating system name (e.g., 'Windows', 'Darwin' (macOS), 'Linux').
    """
    try:
        system = platform.system()
        if not system:
            return "Unknown"
        return system
    except Exception as e:
        logger.error(f"Failed to detect client OS: {e}")
        return "Unknown"
