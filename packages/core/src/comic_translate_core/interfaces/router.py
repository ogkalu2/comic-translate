"""
Semantic router interface for translation routing decisions.
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from ..models.block_v2 import Block
from ..models.routing import RoutingDecision


class ISemanticRouter(ABC):
    """
    Interface for semantic routing of comic blocks to appropriate translators.
    
    Routes blocks based on content analysis (NSFW, SFX, block type, etc.)
    """

    @abstractmethod
    def route(self, block: Block) -> RoutingDecision:
        """
        Route a single block to the appropriate translator.

        Args:
            block: The comic block to route

        Returns:
            RoutingDecision with translator type and flags
        """
        ...

    @abstractmethod
    def route_batch(self, blocks: List[Block]) -> Dict[str, RoutingDecision]:
        """
        Route multiple blocks at once.

        Args:
            blocks: List of blocks to route

        Returns:
            Dictionary mapping block_uid to RoutingDecision
        """
        ...
