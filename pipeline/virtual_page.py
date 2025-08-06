from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

from enum import Enum, auto

class PageStatus(Enum):
    UNPROCESSED = auto()
    DATA_FINALIZED = auto()
    RENDERED = auto()
    LIVE_DATA_FINALIZED = auto()

@dataclass
class VirtualPage:
    """
    Represents a virtual subdivision of a physical webtoon page.
    Virtual pages allow processing of very long webtoon images in manageable chunks
    while maintaining text boundary detection.
    """
    physical_page_index: int  # Index of the original physical page
    physical_page_path: str   # Path to the original image file
    virtual_index: int        # Index within the physical page (0, 1, 2...)
    
    # Crop coordinates within the physical page
    crop_top: int
    crop_bottom: int
    crop_height: int
    
    # Full physical page dimensions for reference
    physical_width: int
    physical_height: int
    
    # Virtual page identifier for tracking
    virtual_id: str
    
    def __post_init__(self):
        """Validate virtual page parameters."""
        if self.crop_bottom <= self.crop_top:
            raise ValueError(f"Invalid crop coordinates: bottom ({self.crop_bottom}) <= top ({self.crop_top})")
        
        if self.crop_height != (self.crop_bottom - self.crop_top):
            raise ValueError(f"Crop height mismatch: {self.crop_height} != {self.crop_bottom - self.crop_top}")
        
        if self.crop_bottom > self.physical_height:
            raise ValueError(f"Crop bottom ({self.crop_bottom}) exceeds physical height ({self.physical_height})")
    
    @property
    def is_first_virtual(self) -> bool:
        """Check if this is the first virtual page of the physical page."""
        return self.virtual_index == 0
    
    @property
    def is_last_virtual(self) -> bool:
        """Check if this is the last virtual page of the physical page."""
        return self.crop_bottom >= self.physical_height
    
    def extract_virtual_image(self, physical_image: np.ndarray) -> np.ndarray:
        """
        Extract the virtual page region from the physical image.
        
        Args:
            physical_image: The full physical page image
            
        Returns:
            Cropped image for this virtual page
        """
        if physical_image.shape[0] != self.physical_height:
            logger.warning(f"Physical image height mismatch: expected {self.physical_height}, got {physical_image.shape[0]}")
        
        return physical_image[self.crop_top:self.crop_bottom, :].copy()
    
    def virtual_to_physical_coords(self, virtual_coords: List[float]) -> List[float]:
        """
        Convert coordinates from virtual page space to physical page space.
        
        Args:
            virtual_coords: [x1, y1, x2, y2] in virtual page coordinates
            
        Returns:
            [x1, y1, x2, y2] in physical page coordinates
        """
        if len(virtual_coords) != 4:
            raise ValueError("Coordinates must be [x1, y1, x2, y2]")
        
        x1, y1, x2, y2 = virtual_coords
        
        # X coordinates remain the same (no horizontal cropping)
        # Y coordinates are offset by crop_top
        return [x1, y1 + self.crop_top, x2, y2 + self.crop_top]
    
    def physical_to_virtual_coords(self, physical_coords: List[float]) -> List[float]:
        """
        Convert coordinates from physical page space to virtual page space.
        
        Args:
            physical_coords: [x1, y1, x2, y2] in physical page coordinates
            
        Returns:
            [x1, y1, x2, y2] in virtual page coordinates
        """
        if len(physical_coords) != 4:
            raise ValueError("Coordinates must be [x1, y1, x2, y2]")
        
        x1, y1, x2, y2 = physical_coords
        
        # X coordinates remain the same
        # Y coordinates are offset by -crop_top
        return [x1, y1 - self.crop_top, x2, y2 - self.crop_top]
    
    def intersects_virtual_bounds(self, physical_coords: List[float]) -> bool:
        """
        Check if physical coordinates intersect with this virtual page bounds.
        
        Args:
            physical_coords: [x1, y1, x2, y2] in physical page coordinates
            
        Returns:
            True if the coordinates intersect with this virtual page
        """
        if len(physical_coords) != 4:
            return False
        
        x1, y1, x2, y2 = physical_coords
        
        # Check vertical overlap
        return not (y2 <= self.crop_top or y1 >= self.crop_bottom)
    
    def clip_to_virtual_bounds(self, physical_coords: List[float]) -> Optional[List[float]]:
        """
        Clip physical coordinates to virtual page bounds and convert to virtual space.
        
        Args:
            physical_coords: [x1, y1, x2, y2] in physical page coordinates
            
        Returns:
            Clipped coordinates in virtual space, or None if no intersection
        """
        if not self.intersects_virtual_bounds(physical_coords):
            return None
        
        x1, y1, x2, y2 = physical_coords
        
        # Clip to virtual bounds
        clipped_y1 = max(y1, self.crop_top)
        clipped_y2 = min(y2, self.crop_bottom)
        
        # Convert to virtual coordinates
        return [x1, clipped_y1 - self.crop_top, x2, clipped_y2 - self.crop_top]
    
    def __str__(self) -> str:
        return f"VirtualPage({self.virtual_id}, crop={self.crop_top}:{self.crop_bottom})"
    
    def __repr__(self) -> str:
        return (f"VirtualPage(physical_page_index={self.physical_page_index}, "
                f"virtual_index={self.virtual_index}, crop_top={self.crop_top}, "
                f"crop_bottom={self.crop_bottom}, virtual_id='{self.virtual_id}')")


class VirtualPageCreator:
    """
    Creates virtual pages from physical webtoon pages to handle very long images.
    """
    
    def __init__(self, max_virtual_height: int = 3000, overlap_height: int = 200):
        """
        Initialize the virtual page creator.
        
        Args:
            max_virtual_height: Maximum height for a virtual page in pixels
            overlap_height: Overlap between consecutive virtual pages for text detection
        """
        self.max_virtual_height = max_virtual_height
        self.overlap_height = overlap_height
    
    def create_virtual_pages(self, physical_page_index: int, physical_page_path: str, 
                           physical_image: np.ndarray) -> List[VirtualPage]:
        """
        Create virtual pages from a physical page.
        
        Args:
            physical_page_index: Index of the physical page
            physical_page_path: Path to the physical image file
            physical_image: The physical page image
            
        Returns:
            List of VirtualPage objects
        """
        physical_height, physical_width = physical_image.shape[:2]
        
        # If the image is already small enough, create a single virtual page
        if physical_height <= self.max_virtual_height:
            virtual_page = VirtualPage(
                physical_page_index=physical_page_index,
                physical_page_path=physical_page_path,
                virtual_index=0,
                crop_top=0,
                crop_bottom=physical_height,
                crop_height=physical_height,
                physical_width=physical_width,
                physical_height=physical_height,
                virtual_id=f"p{physical_page_index}_v0"
            )
            return [virtual_page]
        
        virtual_pages = []
        virtual_index = 0
        current_top = 0
        
        while current_top < physical_height:
            # Calculate the bottom of this virtual page
            current_bottom = min(current_top + self.max_virtual_height, physical_height)
            
            # For non-final pages, extend bottom by overlap_height for text detection
            if current_bottom < physical_height:
                extended_bottom = min(current_bottom + self.overlap_height, physical_height)
            else:
                extended_bottom = current_bottom
            
            virtual_page = VirtualPage(
                physical_page_index=physical_page_index,
                physical_page_path=physical_page_path,
                virtual_index=virtual_index,
                crop_top=current_top,
                crop_bottom=extended_bottom,
                crop_height=extended_bottom - current_top,
                physical_width=physical_width,
                physical_height=physical_height,
                virtual_id=f"p{physical_page_index}_v{virtual_index}"
            )
            
            virtual_pages.append(virtual_page)
            
            # Move to next virtual page, accounting for overlap
            # The actual content boundary is at current_bottom, but we process
            # up to extended_bottom to catch split text
            current_top = current_bottom
            virtual_index += 1
        
        logger.info(f"Created {len(virtual_pages)} virtual pages for physical page {physical_page_index}")
        return virtual_pages
    
    def get_virtual_chunk_pairs(self, virtual_pages: List[VirtualPage]) -> List[Tuple[VirtualPage, VirtualPage]]:
        """
        Generate overlapping pairs of virtual pages for chunk processing.
        This maintains the dual-checking approach across virtual page boundaries.
        
        Args:
            virtual_pages: List of all virtual pages
            
        Returns:
            List of (virtual_page1, virtual_page2) tuples for processing
        """
        if len(virtual_pages) < 1:
            return []
        
        chunk_pairs = []
        
        # Handle single virtual page by creating a self-paired chunk
        if len(virtual_pages) == 1:
            single_vpage = virtual_pages[0]
            chunk_pairs.append((single_vpage, single_vpage))
        else:
            # For multiple virtual pages, create pairs for consecutive pages
            for i in range(len(virtual_pages) - 1):
                current_vpage = virtual_pages[i]
                next_vpage = virtual_pages[i + 1]
                
                # Only create pairs for consecutive virtual pages
                # This ensures we check boundaries between all adjacent virtual sections
                chunk_pairs.append((current_vpage, next_vpage))
        
        return chunk_pairs
