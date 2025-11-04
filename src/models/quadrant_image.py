"""
QuadrantImage Data Model
Represents a single microscopy image with spatial position and metadata
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import numpy as np
import hashlib

from . import Quadrant, ImageMetadata


@dataclass
class QuadrantImage:
    """
    Represents a single microscopy image loaded from a file with spatial position.
    
    Lifecycle:
    1. Created empty with file_path
    2. Populated with metadata after format detection
    3. image_data loaded on-demand for processing
    4. md5_checksum computed for data integrity verification
    
    Attributes:
        file_path: Full path to source image file
        quadrant: Spatial position (NE, NW, SE, SW) or None if unassigned
        filename: Original filename for display
        dimensions: (height, width) in pixels
        dtype: NumPy data type (e.g., uint8, uint16, float32)
        num_channels: Number of color/fluorescence channels
        file_size_bytes: Size of source file in bytes
        image_data: Loaded pixel data as NumPy array (None until loaded)
        metadata: Microscopy-specific metadata (acquisition params, etc.)
        md5_checksum: MD5 hash of image_data for integrity checking
    
    Validation Rules:
    - file_path must exist and be readable
    - dimensions must be positive integers
    - num_channels must be 1, 3, or 4
    - image_data shape must match (dimensions, num_channels)
    - md5_checksum must match recomputed hash if image_data is present
    """
    
    file_path: Path
    quadrant: Optional[Quadrant] = None
    filename: str = field(default="")
    dimensions: tuple[int, int] = field(default=(0, 0))
    dtype: Optional[np.dtype] = None
    num_channels: int = 1
    file_size_bytes: int = 0
    image_data: Optional[np.ndarray] = None
    metadata: ImageMetadata = field(default_factory=ImageMetadata)
    md5_checksum: Optional[str] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if not self.filename:
            self.filename = self.file_path.name
    
    def compute_checksum(self) -> Optional[str]:
        """
        Compute MD5 checksum of image_data for integrity verification.
        
        Returns:
            Hex string of MD5 hash, or None if image_data not loaded
        """
        if self.image_data is None:
            return None
        
        # Compute hash on raw bytes
        md5 = hashlib.md5()
        md5.update(self.image_data.tobytes())
        return md5.hexdigest()
    
    def validate_checksum(self) -> bool:
        """
        Verify that stored checksum matches current image_data.
        
        Returns:
            True if checksums match or no checksum stored, False if mismatch
        """
        if self.md5_checksum is None:
            return True
        
        computed = self.compute_checksum()
        return computed == self.md5_checksum
    
    def is_loaded(self) -> bool:
        """Check if image data is loaded in memory."""
        return self.image_data is not None
    
    def memory_size_mb(self) -> float:
        """
        Calculate memory footprint of loaded image_data.
        
        Returns:
            Size in megabytes, or 0 if not loaded
        """
        if self.image_data is None:
            return 0.0
        
        return self.image_data.nbytes / (1024 * 1024)
    
    @property
    def height(self) -> int:
        """Get image height in pixels."""
        return self.dimensions[0]
    
    @property
    def width(self) -> int:
        """Get image width in pixels."""
        return self.dimensions[1]
    
    @property
    def aspect_ratio(self) -> float:
        """Get width/height aspect ratio."""
        if self.height == 0:
            return 1.0
        return self.width / self.height
    
    @property
    def position_label(self) -> str:
        """Get human-readable position label."""
        if self.quadrant is None:
            return "Unassigned"
        return self.quadrant.label
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        loaded = "loaded" if self.is_loaded() else "metadata only"
        return (
            f"QuadrantImage({self.filename}, "
            f"{self.position_label}, "
            f"{self.width}x{self.height}, "
            f"{loaded})"
        )

