"""
Alignment Parameters Data Model

This module defines data structures for storing and managing alignment parameters
from quadrant stitching operations, enabling parameter reuse for chip image stitching.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
from src.models import Quadrant


@dataclass
class QuadrantAlignment:
    """
    Alignment data for a single quadrant in the stitching operation.
    
    Attributes:
        quadrant: Quadrant position (NE, NW, SE, SW)
        original_image_path: Path to the original quadrant image file
        dimensions: (width, height) of the original image in pixels
        position_shift: (dx, dy) position shift in pixels for alignment
    """
    quadrant: Quadrant
    original_image_path: Path
    dimensions: Tuple[int, int]
    position_shift: Tuple[float, float]


@dataclass
class AlignmentParameters:
    """
    Complete set of alignment parameters from a quadrant stitching operation.
    
    These parameters can be saved to disk and reused for chip image stitching,
    bypassing expensive feature detection and matching.
    
    Attributes:
        version: Schema version for future compatibility (currently "1.0")
        timestamp: ISO 8601 timestamp of parameter generation
        stitched_image_path: Path to the stitched output image
        quadrants: List of per-quadrant alignment data
    """
    version: str
    timestamp: str
    stitched_image_path: Path
    quadrants: List[QuadrantAlignment]


def to_dict(params: AlignmentParameters) -> dict:
    """
    Convert AlignmentParameters to JSON-serializable dictionary.
    
    Args:
        params: AlignmentParameters instance to serialize
        
    Returns:
        Dictionary suitable for JSON serialization
    """
    return {
        "version": params.version,
        "timestamp": params.timestamp,
        "stitched_image_path": str(params.stitched_image_path),
        "quadrants": [
            {
                "quadrant": qa.quadrant.value,
                "original_image_path": str(qa.original_image_path),
                "dimensions": list(qa.dimensions),
                "position_shift": list(qa.position_shift)
            }
            for qa in params.quadrants
        ]
    }


def from_dict(data: dict) -> AlignmentParameters:
    """
    Create AlignmentParameters from JSON dictionary.
    
    Args:
        data: Dictionary loaded from JSON file
        
    Returns:
        AlignmentParameters instance
        
    Raises:
        KeyError: If required fields are missing
        ValueError: If field values are invalid
    """
    return AlignmentParameters(
        version=data["version"],
        timestamp=data["timestamp"],
        stitched_image_path=Path(data["stitched_image_path"]),
        quadrants=[
            QuadrantAlignment(
                quadrant=Quadrant[qa["quadrant"]],
                original_image_path=Path(qa["original_image_path"]),
                dimensions=tuple(qa["dimensions"]),
                position_shift=tuple(qa["position_shift"])
            )
            for qa in data["quadrants"]
        ]
    )
