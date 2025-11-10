"""
Chip Image Set Data Model

This module defines data structures for representing discovered chip images
and their relationships to original quadrant images.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from src.models import Quadrant
from src.models.alignment_parameters import AlignmentParameters


@dataclass
class DimensionMismatch:
    """
    Represents a dimension mismatch between a chip image and its original quadrant.
    
    Attributes:
        quadrant: Which quadrant has the mismatch
        chip_image_path: Path to the chip image file
        original_dimensions: Current (width, height) of chip image
        target_dimensions: Target (width, height) to resize to (from alignment params)
    """
    quadrant: Quadrant
    chip_image_path: Path
    original_dimensions: Tuple[int, int]
    target_dimensions: Tuple[int, int]


@dataclass
class ChipImageSet:
    """
    Collection of chip images discovered for a chip stitching operation.
    
    This represents the result of automatic chip image discovery based on
    alignment parameters from the original quadrant stitching.
    
    Attributes:
        alignment_params: Source alignment parameters from original stitching
        chip_images: Dictionary mapping Quadrant -> Optional[Path]
                     None indicates chip image was not found for that quadrant
        missing_quadrants: List of quadrants without corresponding chip images
        dimension_mismatches: List of chip images requiring resize before stitching
    """
    alignment_params: AlignmentParameters
    chip_images: Dict[Quadrant, Optional[Path]]
    missing_quadrants: List[Quadrant]
    dimension_mismatches: List[DimensionMismatch]
