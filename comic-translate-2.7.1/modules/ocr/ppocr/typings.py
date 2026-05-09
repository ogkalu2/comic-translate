from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class DetResult:
	"""Detection result: polygons (N,4,2) int32 and scores length N."""
	polys: np.ndarray  # (N, 4, 2) int32
	scores: List[float]


@dataclass
class RecLine:
	text: str
	score: float
	box: Optional[np.ndarray] = None  # optional word/line box


@dataclass
class RecResult:
	texts: List[str]
	scores: List[float]
	boxes: Optional[List[np.ndarray]] = None


@dataclass
class OCRResult:
	polys: np.ndarray
	texts: List[str]
	scores: List[float]
