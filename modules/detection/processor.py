import numpy as np

from ..utils.textblock import TextBlock
from .factory import DetectionEngineFactory

# Attempt to import the optional image enhancement subsystem.  Import failures
# are tolerated so that the application runs even if the enhancement package
# is missing.
try:
    from modules.enhancement import get_enhancer
except Exception:
    # Fallback: define a no‑op enhancer getter to avoid NameError later.
    def get_enhancer(_):  # type: ignore[override]
        return None


class TextBlockDetector:
    """
    Detector for finding text blocks in images.

    A wrapper around the various detection engines that optionally applies
    pre‑processing to improve image quality before running detection.  The
    enhancement algorithm can be selected via the settings page under the
    ``image_enhancer`` key.  If no enhancer is selected or the specified
    enhancer is unavailable, the image is passed through unchanged.
    """

    def __init__(self, settings_page):
        self.settings = settings_page
        # Default detector if nothing is chosen in settings
        self.detector = "RT-DETR-V2"

    def detect(self, img: np.ndarray) -> list[TextBlock]:
        """
        Detect text blocks in the provided image.

        Prior to detection, this method consults the settings page for an
        ``image_enhancer`` selection.  If a valid enhancer is returned,
        the image is passed through the enhancer.  Enhancers are expected
        to preserve the input's dimensions to maintain coordinate consistency.

        Parameters
        ----------
        img :
            A NumPy array representing the image to analyse.

        Returns
        -------
        list[TextBlock]
            A list of detected text blocks.
        """
        # Refresh detector selection based on settings (if available)
        try:
            selected_detector = self.settings.get_tool_selection("detector")
            if selected_detector:
                self.detector = selected_detector
        except Exception:
            # If settings or method is missing, stick with the existing value
            pass

        # Apply optional image enhancement prior to detection.  Failure to
        # retrieve an enhancer or to enhance the image should not interrupt
        # detection.  Any errors are logged in the enhancement module.
        try:
            enhancer_name = None
            if hasattr(self.settings, "get_tool_selection"):
                enhancer_name = self.settings.get_tool_selection("image_enhancer")
            enhancer = get_enhancer(enhancer_name)
            if enhancer:
                img = enhancer(img)
        except Exception:
            # Ignore enhancement errors and proceed with the original image
            pass

        # Create the appropriate detection engine
        engine = DetectionEngineFactory.create_engine(self.settings, self.detector)
        return engine.detect(img)
