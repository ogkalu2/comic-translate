"""
Startup script for the Manga Translation API server.
Run this file to start the FastAPI server.
"""

import sys
import os
import logging

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI server."""
    logger.info("Starting Manga Translation API Server")
    logger.info(f"Host: {settings.host}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"GPU Acceleration: {'Enabled' if settings.enable_gpu else 'Disabled'}")
    logger.info(f"Default Detector: {settings.default_detector}")
    logger.info(f"Default OCR: {settings.default_ocr}")
    logger.info(f"Default Translator: {settings.default_translator}")
    logger.info(f"Default Inpainter: {settings.default_inpainter}")
    
    uvicorn.run(
        "server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level
    )


if __name__ == "__main__":
    main()
