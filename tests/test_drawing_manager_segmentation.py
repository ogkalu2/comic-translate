import numpy as np

from app.ui.canvas.drawing_manager import DrawingManager


def test_make_segmentation_stroke_data_accepts_numpy_bboxes():
    bboxes = np.array([[10, 20, 40, 60]], dtype=np.int32)

    stroke = DrawingManager.make_segmentation_stroke_data(None, bboxes)

    assert stroke is not None
    assert stroke["path"].isEmpty() is False


def test_make_segmentation_stroke_data_empty_numpy_returns_none():
    bboxes = np.empty((0, 4), dtype=np.int32)

    assert DrawingManager.make_segmentation_stroke_data(None, bboxes) is None
