# Data Model: NSEW Image Stitcher

**Phase**: 1 (Design)  
**Date**: 2025-11-04  
**Purpose**: Entity definitions and relationships for the NSEW Image Stitcher

## Overview

The data model consists of three primary entities that capture the complete lifecycle of image loading, stitching configuration, and result generation. All entities are designed for JSON serialization to support the Reproducibility principle.

---

## Entities

### 1. QuadrantImage

**Purpose**: Represents a single microscopy image loaded from disk with its spatial position and metadata.

**Fields**:

| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `file_path` | `str` | Yes | Absolute path to source image file | Must be readable file with .czi, .lsm, .tif, or .tiff extension |
| `quadrant` | `Quadrant` (enum) | Yes | Spatial position: NE, NW, SE, SW | One of the four quadrant values |
| `filename` | `str` | Yes | Original filename (for display) | Non-empty string |
| `dimensions` | `tuple[int, int]` | Yes | Image dimensions (height, width) in pixels | Both values > 0 |
| `dtype` | `str` | Yes | NumPy data type (e.g., 'uint16', 'uint8') | Valid NumPy dtype string |
| `num_channels` | `int` | Yes | Number of color/fluorescence channels | >= 1 |
| `file_size_bytes` | `int` | Yes | File size on disk in bytes | >= 0 |
| `image_data` | `np.ndarray` | Yes* | Loaded image pixel data | Shape matches dimensions; dtype matches dtype field |
| `metadata` | `ImageMetadata` | No | Extracted microscopy metadata | See ImageMetadata sub-entity |
| `md5_checksum` | `str` | No | MD5 hash of file for integrity checking | 32-character hex string |

**\*Note**: `image_data` is transient (not serialized to JSON); only loaded into memory during active session.

**Enum: Quadrant**
```python
from enum import Enum

class Quadrant(Enum):
    NE = "NE"  # Top-right
    NW = "NW"  # Top-left
    SE = "SE"  # Bottom-right
    SW = "SW"  # Bottom-left
    
    @property
    def position_indices(self) -> tuple[int, int]:
        """Return (row, col) indices for 2x2 grid layout."""
        positions = {
            Quadrant.NW: (0, 0),
            Quadrant.NE: (0, 1),
            Quadrant.SW: (1, 0),
            Quadrant.SE: (1, 1)
        }
        return positions[self]
```

**Sub-Entity: ImageMetadata**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pixel_size_um` | `float` | No | Physical size of one pixel in micrometers |
| `magnification` | `float` | No | Optical magnification (e.g., 10.0, 20.0, 40.0) |
| `acquisition_date` | `str` | No | ISO 8601 formatted acquisition timestamp |
| `objective` | `str` | No | Microscope objective description |
| `channel_names` | `list[str]` | No | Names of fluorescence channels |

**Business Rules**:
- A QuadrantImage must have unique quadrant position within a session
- If `num_channels > 1`, default to displaying first channel (index 0)
- Image data must be loaded before stitching operations
- If dimensions differ from other quadrants, flag for normalization

**Lifecycle**:
1. **Created**: User selects file(s) → keyword detection or manual assignment → QuadrantImage instantiated
2. **Loaded**: File read from disk → image_data populated → displayed in GUI
3. **Normalized**: If dimensions differ → image_data resized → updated dimensions
4. **Stitched**: image_data used in stitching algorithm → referenced in StitchedResult

---

### 2. StitchingConfig

**Purpose**: Configuration parameters for the stitching operation. Saved to JSON for reproducibility.

**Fields**:

| Field | Type | Required | Description | Default | Validation Rules |
|-------|------|----------|-------------|---------|------------------|
| `alignment_method` | `str` | Yes | Feature detection algorithm | "feature-based" | One of: "feature-based", "phase-correlation" |
| `blend_mode` | `str` | Yes | Seam blending technique | "multiband" | One of: "multiband", "feather", "linear" |
| `overlap_threshold_percent` | `float` | Yes | Minimum required overlap between quadrants | 10.0 | Range: [5.0, 50.0] |
| `resize_strategy` | `str` | Yes | How to normalize mismatched dimensions | "largest" | One of: "largest", "smallest" |
| `interpolation_method` | `str` | Yes | Interpolation for resizing | "bicubic" | One of: "bicubic", "lanczos", "linear" |
| `confidence_threshold` | `float` | Yes | Minimum alignment confidence to accept match | 0.7 | Range: [0.0, 1.0] |
| `output_format` | `str` | Yes | File format for saving stitched result | "tiff" | One of: "tiff", "png", "jpeg" |
| `compression_level` | `int` | No | Compression level (format-dependent) | None | Range: [0, 9] for PNG/TIFF |
| `missing_quadrant_fill` | `str` | Yes | How to handle missing quadrants | "interpolate" | One of: "interpolate", "black", "extend" |

**Business Rules**:
- `overlap_threshold_percent` must be reasonable (5-50%); values outside range trigger warning
- If `blend_mode == "multiband"`, requires sufficient image overlap (>15% recommended)
- `output_format` determines file extension and compression options
- `confidence_threshold` affects stitching success rate; lower = more permissive but risk misalignment

**JSON Serialization Example**:
```json
{
  "alignment_method": "feature-based",
  "blend_mode": "multiband",
  "overlap_threshold_percent": 10.0,
  "resize_strategy": "largest",
  "interpolation_method": "bicubic",
  "confidence_threshold": 0.7,
  "output_format": "tiff",
  "compression_level": 6,
  "missing_quadrant_fill": "interpolate"
}
```

**Lifecycle**:
1. **Default**: Application starts with hard-coded defaults
2. **User-Modified**: User adjusts sliders/dropdowns in GUI → config updated
3. **Pre-Stitch**: Config validated → passed to stitching library function
4. **Saved**: After successful stitch → config serialized to JSON alongside output image

---

### 3. StitchedResult

**Purpose**: Output of stitching operation including image data, quality metrics, and processing metadata.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stitched_image_data` | `np.ndarray` | Yes | Final stitched image pixel data |
| `full_resolution` | `tuple[int, int]` | Yes | Dimensions of full-resolution output (height, width) |
| `display_resolution` | `tuple[int, int]` | Yes | Dimensions of downsampled version for display (if applicable) |
| `output_file_path` | `str` | Yes | Absolute path where full-resolution image was saved |
| `source_quadrants` | `list[QuadrantImage]` | Yes | References to input quadrants (1-4 items) |
| `stitching_config` | `StitchingConfig` | Yes | Configuration used for this stitch operation |
| `quality_metrics` | `QualityMetrics` | Yes | Computed quality/confidence metrics |
| `processing_time_seconds` | `float` | Yes | Total wall-clock time for stitching operation |
| `timestamp` | `str` | Yes | ISO 8601 timestamp when stitching completed |
| `software_version` | `str` | Yes | Application version string (e.g., "0.1.0") |
| `was_downsampled` | `bool` | Yes | True if display_resolution < full_resolution |

**Sub-Entity: QualityMetrics**

| Field | Type | Description |
|-------|------|-------------|
| `overall_confidence` | `float` | Aggregate confidence score [0.0, 1.0] |
| `alignment_confidence_ne_nw` | `float` | Confidence for NE-NW border alignment |
| `alignment_confidence_ne_se` | `float` | Confidence for NE-SE border alignment |
| `alignment_confidence_nw_sw` | `float` | Confidence for NW-SW border alignment |
| `alignment_confidence_se_sw` | `float` | Confidence for SE-SW border alignment |
| `overlap_percent_ne_nw` | `float` | Detected overlap percentage between NE and NW |
| `overlap_percent_ne_se` | `float` | Detected overlap percentage between NE and SE |
| `overlap_percent_nw_sw` | `float` | Detected overlap percentage between NW and SW |
| `overlap_percent_se_sw` | `float` | Detected overlap percentage between SE and SW |
| `feature_matches_total` | `int` | Total number of feature matches found |
| `inlier_ratio` | `float` | RANSAC inlier ratio [0.0, 1.0] |
| `warnings` | `list[str]` | List of warning messages (e.g., "Low overlap detected") |

**Business Rules**:
- If `overall_confidence < confidence_threshold`, stitching operation should fail (or warn heavily)
- Missing quadrants have corresponding alignment/overlap metrics set to `null` or `0.0`
- `display_resolution == full_resolution` when `was_downsampled == False`
- Quality metrics used to populate info panel in result window

**JSON Serialization Example** (saved as `<output_name>_config.json`):
```json
{
  "timestamp": "2025-11-04T10:45:23Z",
  "software_version": "0.1.0",
  "source_files": [
    {
      "path": "/data/image_NE.czi",
      "quadrant": "NE",
      "dimensions": [2000, 2000],
      "file_size_bytes": 8000000,
      "md5": "abc123..."
    }
  ],
  "stitching_config": {
    "alignment_method": "feature-based",
    "blend_mode": "multiband",
    "overlap_threshold_percent": 10.0,
    "resize_strategy": "largest",
    "interpolation_method": "bicubic"
  },
  "output": {
    "file_path": "/output/stitched_2025-11-04_104523.tif",
    "full_resolution": [4000, 4000],
    "display_resolution": [4000, 4000],
    "was_downsampled": false
  },
  "quality_metrics": {
    "overall_confidence": 0.89,
    "alignment_confidence_ne_nw": 0.92,
    "overlap_percent_ne_nw": 15.2,
    "feature_matches_total": 1247,
    "inlier_ratio": 0.87,
    "warnings": []
  },
  "processing_time_seconds": 45.3
}
```

**Lifecycle**:
1. **Initiated**: Stitching operation starts → StitchedResult object created
2. **Populated**: Stitching completes → image_data, metrics, timing populated
3. **Saved**: Full-resolution image written to disk → path recorded
4. **Displayed**: Downsampled (if needed) image shown in result window
5. **Persisted**: Config JSON saved alongside image for reproducibility

---

## Relationships

```
┌──────────────────┐
│ QuadrantImage    │
│ (1-4 instances)  │
└────────┬─────────┘
         │ 1..*
         │ references
         ▼
┌──────────────────┐      ┌──────────────────┐
│ StitchingConfig  │────► │ StitchedResult   │
│ (1 instance)     │ used │ (1 instance)     │
└──────────────────┘  by  └──────────────────┘
                            │
                            │ contains
                            ▼
                       ┌──────────────────┐
                       │ QualityMetrics   │
                       │ (embedded)       │
                       └──────────────────┘
```

**Cardinality**:
- **QuadrantImage → StitchingConfig**: Many-to-One (1-4 images use 1 config)
- **StitchingConfig → StitchedResult**: One-to-One (1 config produces 1 result)
- **QuadrantImage → StitchedResult**: Many-to-One (1-4 images produce 1 result)

**Data Flow**:
1. User loads 1-4 images → QuadrantImage instances created
2. User adjusts parameters → StitchingConfig updated
3. User clicks "Stitch" → stitching algorithm processes QuadrantImages using StitchingConfig
4. Algorithm completes → StitchedResult created with references to inputs and config
5. Result displayed → QualityMetrics shown to user
6. User saves → StitchedResult serialized to JSON, image saved to disk

---

## State Transitions

### QuadrantImage States

```
[Not Loaded] → load_from_file() → [Loaded] → resize() → [Normalized] → stitch() → [Stitched]
                                      ↓
                                  [Error: Corrupted]
```

- **Not Loaded**: File path assigned, but image_data not yet read
- **Loaded**: image_data populated, ready for display
- **Normalized**: Dimensions adjusted to match other quadrants (if needed)
- **Stitched**: Used in stitching operation (terminal state)
- **Error**: File couldn't be read (terminal state)

### StitchedResult States

```
[In Progress] → complete() → [Complete] → save() → [Saved]
                    ↓
                [Error: Insufficient Overlap]
```

- **In Progress**: Stitching algorithm running
- **Complete**: Stitching finished, result populated
- **Saved**: Image and config JSON written to disk (terminal state)
- **Error**: Stitching failed validation (terminal state)

---

## Validation Rules

### Cross-Entity Validation

1. **Dimension Compatibility**: All QuadrantImages in a session must have compatible aspect ratios (within 10% difference) before stitching
2. **Data Type Consistency**: All QuadrantImages must have same dtype (all uint8 or all uint16)
3. **Channel Consistency**: All QuadrantImages must have same num_channels
4. **Overlap Requirement**: Detected overlap between adjacent quadrants must exceed `StitchingConfig.overlap_threshold_percent`

### Invariants

- A session must have at least 1 QuadrantImage before stitching can proceed
- QuadrantImage.quadrant values must be unique within a session (no duplicate quadrants)
- StitchedResult.source_quadrants list length must match number of QuadrantImages provided
- If StitchedResult.was_downsampled == True, then display_resolution < full_resolution

---

## Performance Considerations

### Memory Footprint

**QuadrantImage**:
- Single 2000x2000 uint16 image: 2000 × 2000 × 2 bytes = 8 MB
- Four quadrants: 32 MB
- With metadata overhead: ~35 MB total

**StitchedResult**:
- 4000x4000 uint16 output: 32 MB
- Downsampled display version (if applicable): ~8 MB
- Total for result: ~40 MB

**Maximum Memory Usage** (4 input quadrants + stitched result):
- ~35 MB (inputs) + ~40 MB (output) + ~25 MB (OpenCV processing buffers) = ~100 MB
- Well within target <4GB RAM constraint

### Storage Footprint

**JSON Config File**: ~2 KB per stitching operation  
**Output Image** (TIFF, compressed): ~10-50 MB depending on complexity  
**Total per session**: ~12-52 MB

---

## Implementation Notes

- Use `dataclasses` with `@dataclass` decorator for QuadrantImage, StitchingConfig, StitchedResult
- Implement `to_dict()` and `from_dict()` methods for JSON serialization
- QuadrantImage.image_data should be excluded from JSON serialization (use `field(repr=False, compare=False)`)
- Validate all entities at creation time using `__post_init__()` in dataclasses
- Store QualityMetrics as nested dict in StitchedResult JSON

