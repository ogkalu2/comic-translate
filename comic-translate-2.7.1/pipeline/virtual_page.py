from dataclasses import dataclass
from typing import List


@dataclass
class VirtualPage:
    """
    Represents a virtual subdivision of a physical webtoon page.
    """

    physical_page_index: int
    physical_page_path: str
    virtual_index: int
    crop_top: int
    crop_bottom: int
    crop_height: int
    physical_width: int
    physical_height: int
    virtual_id: str

    def __post_init__(self) -> None:
        if self.crop_bottom <= self.crop_top:
            raise ValueError(
                f"Invalid crop coordinates: bottom ({self.crop_bottom}) <= top ({self.crop_top})"
            )
        expected_height = self.crop_bottom - self.crop_top
        if self.crop_height != expected_height:
            raise ValueError(
                f"Crop height mismatch: {self.crop_height} != {expected_height}"
            )
        if self.crop_bottom > self.physical_height:
            raise ValueError(
                f"Crop bottom ({self.crop_bottom}) exceeds physical height ({self.physical_height})"
            )

    @property
    def is_first_virtual(self) -> bool:
        return self.virtual_index == 0

    @property
    def is_last_virtual(self) -> bool:
        return self.crop_bottom >= self.physical_height

    def virtual_to_physical_coords(self, virtual_coords: List[float]) -> List[float]:
        if len(virtual_coords) != 4:
            raise ValueError("Coordinates must be [x1, y1, x2, y2]")
        x1, y1, x2, y2 = virtual_coords
        return [x1, y1 + self.crop_top, x2, y2 + self.crop_top]

    def __str__(self) -> str:
        return f"VirtualPage({self.virtual_id}, crop={self.crop_top}:{self.crop_bottom})"

    def __repr__(self) -> str:
        return (
            f"VirtualPage(physical_page_index={self.physical_page_index}, "
            f"virtual_index={self.virtual_index}, crop_top={self.crop_top}, "
            f"crop_bottom={self.crop_bottom}, virtual_id='{self.virtual_id}')"
        )
