"""
NSEW Image Stitcher - Core Data Models
Defines data structures for quadrant images, stitching configuration, and results
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


class Quadrant(Enum):
    """Spatial quadrant positions for MEA microscopy images."""
    
    NE = "NE"  # North-East (top-right)
    NW = "NW"  # North-West (top-left)
    SE = "SE"  # South-East (bottom-right)
    SW = "SW"  # South-West (bottom-left)
    
    def position_indices(self) -> tuple[int, int]:
        """
        Get grid position indices for 2x2 layout.
        
        Returns:
            (row, col): Row and column indices (0 or 1)
            
        Grid layout:
            [0,0] NW | [0,1] NE
            ---------|----------
            [1,0] SW | [1,1] SE
        """
        positions = {
            Quadrant.NW: (0, 0),
            Quadrant.NE: (0, 1),
            Quadrant.SW: (1, 0),
            Quadrant.SE: (1, 1),
        }
        return positions[self]
    
    @property
    def label(self) -> str:
        """Get human-readable label."""
        labels = {
            Quadrant.NE: "North-East",
            Quadrant.NW: "North-West",
            Quadrant.SE: "South-East",
            Quadrant.SW: "South-West",
        }
        return labels[self]
    
    @classmethod
    def from_keyword(cls, keyword: str) -> Optional['Quadrant']:
        """
        Parse quadrant from spatial keyword.
        
        Args:
            keyword: Spatial keyword (e.g., "NE", "northeast", "north_east")
            
        Returns:
            Quadrant enum or None if not recognized
        """
        keyword_clean = keyword.upper().replace("_", "").replace("-", "")
        
        # Direct matches
        if keyword_clean in ("NE", "NORTHEAST", "TOPRIGHT", "RIGHTTTOP"):
            return Quadrant.NE
        if keyword_clean in ("NW", "NORTHWEST", "TOPLEFT", "LEFTTOP"):
            return Quadrant.NW
        if keyword_clean in ("SE", "SOUTHEAST", "BOTTOMRIGHT", "RIGHTBOTTOM"):
            return Quadrant.SE
        if keyword_clean in ("SW", "SOUTHWEST", "BOTTOMLEFT", "LEFTBOTTOM"):
            return Quadrant.SW
        
        # Single letter combinations
        if keyword_clean in ("N", "NORTH", "TOP"):
            return None  # Ambiguous - could be NE or NW
        if keyword_clean in ("S", "SOUTH", "BOTTOM"):
            return None  # Ambiguous - could be SE or SW
        if keyword_clean in ("E", "EAST", "RIGHT"):
            return None  # Ambiguous - could be NE or SE
        if keyword_clean in ("W", "WEST", "LEFT"):
            return None  # Ambiguous - could be NW or SW
        
        return None


@dataclass
class ImageMetadata:
    """
    Metadata extracted from microscopy image files.
    
    Attributes:
        pixel_size_um: Physical size of each pixel in micrometers
        magnification: Objective magnification (e.g., 10x, 20x)
        acquisition_date: When the image was acquired
        objective: Objective lens used for acquisition
        channel_names: Names of fluorescence channels
    """
    pixel_size_um: Optional[float] = None
    magnification: Optional[str] = None
    acquisition_date: Optional[datetime] = None
    objective: Optional[str] = None
    channel_names: Optional[list[str]] = None


# Import from submodules
from .quadrant_image import QuadrantImage
from .stitching_config import StitchingConfig
from .stitched_result import StitchedResult, QualityMetrics

# Export all public symbols
__all__ = [
    "Quadrant",
    "ImageMetadata",
    "QuadrantImage",
    "StitchingConfig",
    "StitchedResult",
    "QualityMetrics",
]

