"""
StitchingConfig Data Model
Configuration parameters for image stitching operations
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class StitchingConfig:
    """
    Configuration for stitching quadrant images together.
    
    Immutable configuration that defines all parameters for a stitching operation.
    Used for reproducibility and parameter tracking.
    
    Attributes:
        alignment_method: Algorithm for detecting alignment between images
            - "orb": Oriented FAST and Rotated BRIEF (fast, good for texture)
            - "sift": Scale-Invariant Feature Transform (robust, slower)
            - "akaze": Accelerated KAZE (balance of speed and quality)
            - "skimage": Scikit-image phase correlation (sub-pixel accurate, best for uniform textures)
        
        blend_mode: Method for blending overlapping regions
            - "linear": Simple linear blend based on distance from edge
            - "multiband": Multi-resolution blending (seamless, best quality)
            - "feather": Feathered edge blending
        
        overlap_threshold_percent: Minimum expected overlap between adjacent images (5-50%)
            Lower values (5-10%) allow stitching with minimal overlap
            Higher values (20-50%) require more overlap but improve alignment
        
        resize_strategy: How to handle images with different dimensions
            - "largest": Resize all to match largest image (preserves detail)
            - "smallest": Resize all to match smallest image (faster)
            - "average": Resize all to average dimension
        
        interpolation_method: Pixel interpolation for resizing
            - "linear": Fast, good for most cases
            - "cubic": Higher quality, slower
            - "lanczos": Best quality, slowest
        
        confidence_threshold: Minimum confidence score (0.0-1.0) to accept alignment
            0.6 = acceptable quality
            0.8 = good quality
            1.0 = perfect match (rarely achieved)
        
        output_format: File format for saved stitched image
            - "tiff": Lossless, supports 16-bit, large files
            - "png": Lossless, 8-bit, smaller files
            - "jpeg": Lossy, 8-bit, smallest files
        
        compression_level: Compression for output file (0-9)
            0 = no compression (fastest, largest)
            5 = balanced (recommended)
            9 = maximum compression (slowest, smallest)
        
        missing_quadrant_fill: Strategy for handling missing quadrants
            - "black": Fill with black pixels
            - "white": Fill with white pixels
            - "interpolate": Estimate from adjacent quadrants (experimental)
        
        max_rotation_degrees: Maximum allowed rotation angle in degrees (0.0-180.0)
            Rotation angles exceeding this limit will generate warnings
            Default 10.0 degrees allows ±10° rotation
        
        max_zoom_percent: Maximum allowed zoom/scale adjustment in percent (0.0-20.0)
            Allows ±max_zoom_percent scaling during alignment
            Default 5.0 allows ±5% zoom (scale 0.95 to 1.05)
    
    Validation Rules:
    - overlap_threshold_percent must be in range [5, 50]
    - confidence_threshold must be in range [0.0, 1.0]
    - compression_level must be in range [0, 9]
    - max_rotation_degrees must be in range [0.0, 180.0]
    - max_zoom_percent must be in range [0.0, 20.0]
    """
    
    alignment_method: Literal["orb", "sift", "akaze", "skimage"] = "orb"
    blend_mode: Literal["linear", "multiband", "feather"] = "multiband"
    overlap_threshold_percent: float = 15.0
    resize_strategy: Literal["largest", "smallest", "average"] = "largest"
    interpolation_method: Literal["linear", "cubic", "lanczos"] = "linear"
    confidence_threshold: float = 0.6
    output_format: Literal["tiff", "png", "jpeg"] = "tiff"
    compression_level: int = 5
    missing_quadrant_fill: Literal["black", "white", "interpolate"] = "black"
    max_rotation_degrees: float = 5.0
    max_zoom_percent: float = 5.0  # Allow ±5% zoom by default
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if not (5.0 <= self.overlap_threshold_percent <= 50.0):
            raise ValueError(
                f"overlap_threshold_percent must be in range [5, 50], "
                f"got {self.overlap_threshold_percent}"
            )
        
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(
                f"confidence_threshold must be in range [0.0, 1.0], "
                f"got {self.confidence_threshold}"
            )
        
        if not (0 <= self.compression_level <= 9):
            raise ValueError(
                f"compression_level must be in range [0, 9], "
                f"got {self.compression_level}"
            )
        
        if not (0.0 <= self.max_rotation_degrees <= 180.0):
            raise ValueError(
                f"max_rotation_degrees must be in range [0.0, 180.0], "
                f"got {self.max_rotation_degrees}"
            )
        
        if not (0.0 <= self.max_zoom_percent <= 20.0):
            raise ValueError(
                f"max_zoom_percent must be in range [0.0, 20.0], "
                f"got {self.max_zoom_percent}"
            )
    
    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary for serialization.
        
        Returns:
            Dictionary with all configuration parameters
        """
        return {
            "alignment_method": self.alignment_method,
            "blend_mode": self.blend_mode,
            "overlap_threshold_percent": self.overlap_threshold_percent,
            "resize_strategy": self.resize_strategy,
            "interpolation_method": self.interpolation_method,
            "confidence_threshold": self.confidence_threshold,
            "output_format": self.output_format,
            "compression_level": self.compression_level,
            "missing_quadrant_fill": self.missing_quadrant_fill,
            "max_rotation_degrees": self.max_rotation_degrees,
            "max_zoom_percent": self.max_zoom_percent,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StitchingConfig':
        """
        Create configuration from dictionary.
        
        Args:
            data: Dictionary with configuration parameters
            
        Returns:
            New StitchingConfig instance
        """
        # Handle backward compatibility - use defaults for missing fields
        valid_fields = {
            'alignment_method', 'blend_mode', 'overlap_threshold_percent',
            'resize_strategy', 'interpolation_method', 'confidence_threshold',
            'output_format', 'compression_level', 'missing_quadrant_fill',
            'max_rotation_degrees', 'max_zoom_percent'
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    @classmethod
    def default(cls) -> 'StitchingConfig':
        """
        Get default configuration optimized for typical MEA microscopy.
        
        Returns:
            StitchingConfig with recommended default values
        """
        return cls(
            alignment_method="orb",
            blend_mode="multiband",
            overlap_threshold_percent=15.0,
            resize_strategy="largest",
            interpolation_method="linear",
            confidence_threshold=0.6,
            output_format="tiff",
            compression_level=5,
            missing_quadrant_fill="black",
            max_rotation_degrees=5.0,
            max_zoom_percent=5.0,
        )

