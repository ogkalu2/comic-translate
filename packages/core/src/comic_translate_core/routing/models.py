"""
Core signal contracts for the signal-based routing architecture.

Detectors emit signals. Router is the ONLY decision maker.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Signal:
    """
    A single observation from a detector.
    
    Detectors emit signals, never decisions.
    """
    name: str                    # "language", "nsfw_score", "sfx", "url_detected"
    value: Any                   # flexible: str, float, dict, bool
    confidence: float            # 0.0–1.0
    source: str                  # detector id (e.g., "unicode_heuristic", "keyword_nsfw")
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalBundle:
    """
    Collection of all signals for a single routing decision.
    """
    signals: List[Signal]

    def get(self, name: str) -> List[Signal]:
        """Get all signals with the given name."""
        return [s for s in self.signals if s.name == name]

    def get_best(self, name: str) -> Optional[Signal]:
        """Get the signal with the highest confidence for the given name."""
        matches = self.get(name)
        return max(matches, key=lambda s: s.confidence) if matches else None


@dataclass(frozen=True)
class RoutingContext:
    """
    Input context for routing — everything the router needs.
    """
    text: str
    bbox: Optional[List[int]] = None
    block_type: Optional[str] = None
    nsfw_flag: bool = False
    panel_meta: Dict[str, Any] = field(default_factory=dict)
