"""
Detector interface for the signal-based routing architecture.

Detectors emit signals. They NEVER make routing decisions.
"""

from abc import ABC, abstractmethod
from typing import List

from .models import RoutingContext, Signal


class IDetector(ABC):
    """
    Base interface for all routing detectors.
    
    Detectors emit signals. They NEVER make routing decisions.
    The Router is the ONLY decision maker.
    """
    
    name: str = "base"

    @abstractmethod
    def detect(self, ctx: RoutingContext) -> List[Signal]:
        """
        Detect signals from the given routing context.
        
        Args:
            ctx: The routing context containing text, bbox, block_type, etc.
            
        Returns:
            List of Signal objects. Never returns a RoutingDecision.
        """
        ...
