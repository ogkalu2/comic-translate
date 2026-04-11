"""
Rendering and inpainting engine wrappers for comic images.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class RenderingEngine(ABC):
    """
    Abstract base class for rendering engines.
    Wraps the core rendering interface.
    """

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """Initialize the rendering engine."""
        pass

    @abstractmethod
    def render(self, img: np.ndarray, blk_list: list, font_size: int = 0, **kwargs) -> np.ndarray:
        """
        Render translated text onto an image.

        Args:
            img: Input image as numpy array
            blk_list: List of text blocks to render
            font_size: Font size for rendering (0 = auto)
            **kwargs: Additional rendering parameters

        Returns:
            Image with rendered text as numpy array
        """
        pass


class InpaintingEngine(ABC):
    """
    Abstract base class for inpainting engines.
    Wraps the core inpainting interface.
    """

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """Initialize the inpainting engine."""
        pass

    @abstractmethod
    def inpaint(self, img: np.ndarray, mask: np.ndarray, **kwargs) -> np.ndarray:
        """
        Inpaint (remove text) from an image.

        Args:
            img: Input image as numpy array
            mask: Binary mask indicating text pixels to remove
            **kwargs: Additional inpainting parameters

        Returns:
            Inpainted image as numpy array
        """
        pass


class RenderingEngineFactory:
    """Factory for creating rendering engines."""

    _engines = {
        "default": "modules.rendering.render.TextRenderer",
    }

    @classmethod
    def create_engine(
        cls,
        engine_type: str = "default",
        **kwargs
    ) -> RenderingEngine:
        """
        Create a rendering engine instance.

        Args:
            engine_type: Type of rendering engine to create
            **kwargs: Engine-specific parameters

        Returns:
            Rendering engine instance
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unknown rendering engine type: {engine_type}")

        # Dynamic import to avoid circular dependencies
        module_path, class_name = cls._engines[engine_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        engine_class = getattr(module, class_name)

        return engine_class(**kwargs)

    @classmethod
    def get_available_engines(cls) -> List[str]:
        """Get list of available rendering engine types."""
        return list(cls._engines.keys())


class InpaintingEngineFactory:
    """Factory for creating inpainting engines."""

    _engines = {
        "lama": "modules.inpainting.lama.LaMaInpainting",
        "aot": "modules.inpainting.aot.AOTInpainting",
        "mi_gan": "modules.inpainting.mi_gan.MiGANInpainting",
    }

    @classmethod
    def create_engine(
        cls,
        engine_type: str = "lama",
        **kwargs
    ) -> InpaintingEngine:
        """
        Create an inpainting engine instance.

        Args:
            engine_type: Type of inpainting engine to create
            **kwargs: Engine-specific parameters

        Returns:
            Inpainting engine instance
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unknown inpainting engine type: {engine_type}")

        # Dynamic import to avoid circular dependencies
        module_path, class_name = cls._engines[engine_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        engine_class = getattr(module, class_name)

        return engine_class(**kwargs)

    @classmethod
    def get_available_engines(cls) -> List[str]:
        """Get list of available inpainting engine types."""
        return list(cls._engines.keys())
