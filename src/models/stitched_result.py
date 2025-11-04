"""
StitchedResult and QualityMetrics Data Models
Results and quality metrics from stitching operations
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np

from .stitching_config import StitchingConfig
from .quadrant_image import QuadrantImage


@dataclass
class QualityMetrics:
    """
    Quality metrics for stitching result assessment.
    
    Provides quantitative measures of stitching quality to help users
    evaluate the reliability of the stitched image.
    
    Attributes:
        overall_confidence: Overall stitching quality (0.0-1.0)
            <0.6 = poor (visible artifacts likely)
            0.6-0.8 = acceptable (minor artifacts possible)
            >0.8 = good (high quality result)
        
        alignment_confidence_n: Confidence for North border alignment (NW-NE)
        alignment_confidence_s: Confidence for South border alignment (SW-SE)
        alignment_confidence_e: Confidence for East border alignment (NE-SE)
        alignment_confidence_w: Confidence for West border alignment (NW-SW)
        
        overlap_percent_n: Detected overlap percentage at North border
        overlap_percent_s: Detected overlap percentage at South border
        overlap_percent_e: Detected overlap percentage at East border
        overlap_percent_w: Detected overlap percentage at West border
        
        feature_matches_total: Total number of feature points matched
        inlier_ratio: Ratio of inlier matches to total matches (0.0-1.0)
            >0.7 = reliable alignment
            0.5-0.7 = moderate reliability
            <0.5 = low reliability (manual review recommended)
        
        warnings: List of quality warnings or issues detected
            e.g., ["Low overlap detected at North border (8%)",
                   "Insufficient feature matches in SE quadrant"]
    """
    
    overall_confidence: float = 0.0
    
    # Border-specific alignment confidence
    alignment_confidence_n: Optional[float] = None  # North border (NW-NE)
    alignment_confidence_s: Optional[float] = None  # South border (SW-SE)
    alignment_confidence_e: Optional[float] = None  # East border (NE-SE)
    alignment_confidence_w: Optional[float] = None  # West border (NW-SW)
    
    # Border-specific overlap percentages
    overlap_percent_n: Optional[float] = None
    overlap_percent_s: Optional[float] = None
    overlap_percent_e: Optional[float] = None
    overlap_percent_w: Optional[float] = None
    
    # Feature matching statistics
    feature_matches_total: int = 0
    inlier_ratio: float = 0.0
    
    # Quality warnings
    warnings: list[str] = field(default_factory=list)
    
    def quality_category(self) -> str:
        """
        Classify overall quality into human-readable category.
        
        Returns:
            "Excellent", "Good", "Acceptable", or "Poor"
        """
        if self.overall_confidence >= 0.9:
            return "Excellent"
        elif self.overall_confidence >= 0.8:
            return "Good"
        elif self.overall_confidence >= 0.6:
            return "Acceptable"
        else:
            return "Poor"
    
    def has_warnings(self) -> bool:
        """Check if any quality warnings were generated."""
        return len(self.warnings) > 0
    
    def border_confidences(self) -> dict[str, Optional[float]]:
        """Get all border confidences as a dictionary."""
        return {
            "north": self.alignment_confidence_n,
            "south": self.alignment_confidence_s,
            "east": self.alignment_confidence_e,
            "west": self.alignment_confidence_w,
        }
    
    def border_overlaps(self) -> dict[str, Optional[float]]:
        """Get all border overlaps as a dictionary."""
        return {
            "north": self.overlap_percent_n,
            "south": self.overlap_percent_s,
            "east": self.overlap_percent_e,
            "west": self.overlap_percent_w,
        }


@dataclass
class StitchedResult:
    """
    Complete result of a stitching operation.
    
    Contains the stitched image data, quality metrics, and all metadata
    needed for reproducibility and validation.
    
    Lifecycle:
    1. Created during stitching operation
    2. stitched_image_data populated with result
    3. quality_metrics computed from alignment process
    4. Saved to disk with output_file_path
    5. May be downsampled for display if too large
    
    Attributes:
        stitched_image_data: Final stitched image as NumPy array
        full_resolution: (height, width) of full-resolution result
        display_resolution: (height, width) of display version (if downsampled)
        output_file_path: Path where full-resolution image was saved
        source_quadrants: List of QuadrantImages used in stitching
        stitching_config: Configuration parameters used
        quality_metrics: Quality assessment of stitching result
        processing_time_seconds: Time taken for stitching operation
        timestamp: When stitching was completed
        software_version: Version of application used
        was_downsampled: Whether image was downsampled for display
    
    Validation Rules:
    - stitched_image_data dimensions must match full_resolution
    - source_quadrants must contain 1-4 images
    - processing_time_seconds must be positive
    - was_downsampled=True implies display_resolution != full_resolution
    """
    
    stitched_image_data: Optional[np.ndarray] = None
    full_resolution: tuple[int, int] = (0, 0)
    display_resolution: tuple[int, int] = (0, 0)
    output_file_path: Optional[Path] = None
    source_quadrants: list[QuadrantImage] = field(default_factory=list)
    stitching_config: StitchingConfig = field(default_factory=StitchingConfig.default)
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)
    processing_time_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    software_version: str = "0.1.0"
    was_downsampled: bool = False
    
    def memory_size_mb(self) -> float:
        """
        Calculate memory footprint of stitched image data.
        
        Returns:
            Size in megabytes, or 0 if not loaded
        """
        if self.stitched_image_data is None:
            return 0.0
        
        return self.stitched_image_data.nbytes / (1024 * 1024)
    
    def num_quadrants_used(self) -> int:
        """Get count of source quadrants used."""
        return len(self.source_quadrants)
    
    def quadrant_positions(self) -> list[str]:
        """Get list of quadrant position labels."""
        return [q.position_label for q in self.source_quadrants if q.quadrant]
    
    def is_complete_set(self) -> bool:
        """Check if all 4 quadrants were used."""
        return self.num_quadrants_used() == 4
    
    @property
    def full_width(self) -> int:
        """Get full-resolution width in pixels."""
        return self.full_resolution[1]
    
    @property
    def full_height(self) -> int:
        """Get full-resolution height in pixels."""
        return self.full_resolution[0]
    
    @property
    def display_width(self) -> int:
        """Get display resolution width in pixels."""
        return self.display_resolution[1]
    
    @property
    def display_height(self) -> int:
        """Get display resolution height in pixels."""
        return self.display_resolution[0]
    
    def to_dict(self) -> dict:
        """
        Convert result to dictionary for serialization (excluding image data).
        
        Used for saving configuration and metadata to JSON without large image arrays.
        
        Returns:
            Dictionary with metadata and parameters (no image_data)
        """
        return {
            "full_resolution": self.full_resolution,
            "display_resolution": self.display_resolution,
            "output_file_path": str(self.output_file_path) if self.output_file_path else None,
            "num_quadrants": self.num_quadrants_used(),
            "quadrant_positions": self.quadrant_positions(),
            "stitching_config": self.stitching_config.to_dict(),
            "quality_metrics": {
                "overall_confidence": self.quality_metrics.overall_confidence,
                "feature_matches": self.quality_metrics.feature_matches_total,
                "inlier_ratio": self.quality_metrics.inlier_ratio,
                "quality_category": self.quality_metrics.quality_category(),
                "warnings": self.quality_metrics.warnings,
            },
            "processing_time_seconds": self.processing_time_seconds,
            "timestamp": self.timestamp.isoformat(),
            "software_version": self.software_version,
            "was_downsampled": self.was_downsampled,
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"StitchedResult({self.num_quadrants_used()} quadrants, "
            f"{self.full_width}x{self.full_height}px, "
            f"quality={self.quality_metrics.quality_category()})"
        )

