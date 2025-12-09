"""
Server configuration settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    log_level: str = "info"
    
    # API settings
    api_title: str = "Manga Translation API"
    api_version: str = "1.0.0"
    api_description: str = "Backend API for manga image translation"
    
    # CORS settings
    cors_origins: list = ["*"]
    cors_credentials: bool = True
    cors_methods: list = ["*"]
    cors_headers: list = ["*"]
    
    # Model settings
    default_detector: str = "RT-DETR-V2"
    default_ocr: str = "Default"
    default_translator: str = "Google Translate"
    default_inpainter: str = "LaMa"
    
    # GPU settings
    enable_gpu: bool = False
    
    # Language settings
    default_source_lang: str = "Japanese"
    default_target_lang: str = "English"
    
    # Upload settings
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    
    # Cache settings
    enable_caching: bool = True
    cache_ttl: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
