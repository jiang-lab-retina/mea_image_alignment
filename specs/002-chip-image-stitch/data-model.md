# Data Model: Chip Image Stitching

**Feature**: 002-chip-image-stitch  
**Date**: 2025-11-05  
**Phase**: 1 (Design)

## Overview

This document defines the data entities for chip image stitching with alignment reuse. These entities extend the existing 001-nsew-image-stitcher data model to support parameter persistence, chip image discovery, and alignment reuse workflows.

---

## Entity: AlignmentParameters

**Purpose**: Stores X and Y position shift parameters from the original quadrant stitching for reuse in chip image stitching.

**File**: `src/models/alignment_parameters.py`

### Fields

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `version` | `str` | Yes | Schema version for future compatibility | Must be "1.0" |
| `timestamp` | `str` | Yes | ISO 8601 timestamp of parameter generation | Valid ISO 8601 format (YYYY-MM-DDTHH:MM:SS) |
| `stitched_image_path` | `Path` | Yes | Path to the original stitched image | Must be valid path |
| `quadrants` | `List[QuadrantAlignment]` | Yes | Per-quadrant alignment data | Non-empty list, 1-4 elements |

### Nested Type: QuadrantAlignment

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `quadrant` | `Quadrant` | Yes | Quadrant position (NE, NW, SE, SW) | Valid Quadrant enum value |
| `original_image_path` | `Path` | Yes | Path to original quadrant image | Must be valid path |
| `dimensions` | `Tuple[int, int]` | Yes | (width, height) of original image | Both > 0 |
| `position_shift` | `Tuple[float, float]` | Yes | (dx, dy) position shift in pixels | Can be negative |

### Serialization

**Format**: JSON

**Example**:
```json
{
  "version": "1.0",
  "timestamp": "2025-11-05T14:30:22",
  "stitched_image_path": "/path/to/stitched_result.tiff",
  "quadrants": [
    {
      "quadrant": "NE",
      "original_image_path": "/path/to/sample_NE.czi",
      "dimensions": [2048, 2048],
      "position_shift": [50.5, 30.2]
    },
    {
      "quadrant": "NW",
      "original_image_path": "/path/to/sample_NW.czi",
      "dimensions": [2048, 2048],
      "position_shift": [0.0, 0.0]
    }
  ]
}
```

### Lifecycle

1. **Creation**: Generated automatically when `stitch_quadrants()` completes successfully
2. **Persistence**: Saved to disk as JSON file in same directory as stitched image
3. **Loading**: Loaded automatically on application start if found in working directory
4. **Validation**: Validated on load (format, completeness, image file existence)
5. **Usage**: Passed to `stitch_chip_images()` to apply position shifts
6. **Archival**: Remains on disk indefinitely; users can delete if no longer needed

---

## Entity: ChipImageSet

**Purpose**: Represents the collection of chip images discovered for a chip stitching operation.

**File**: `src/models/chip_image_set.py` (new)

### Fields

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `alignment_params` | `AlignmentParameters` | Yes | Source alignment parameters | Valid AlignmentParameters |
| `chip_images` | `Dict[Quadrant, Optional[Path]]` | Yes | Discovered chip image paths | Keys match alignment params quadrants |
| `missing_quadrants` | `List[Quadrant]` | Yes | Quadrants without chip images | Subset of alignment params quadrants |
| `dimension_mismatches` | `List[DimensionMismatch]` | Yes | Chip images needing resize | Can be empty list |

### Nested Type: DimensionMismatch

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `quadrant` | `Quadrant` | Yes | Which quadrant has mismatch | Valid Quadrant enum |
| `chip_image_path` | `Path` | Yes | Path to chip image | Must exist |
| `original_dimensions` | `Tuple[int, int]` | Yes | Chip image's current size | Both > 0 |
| `target_dimensions` | `Tuple[int, int]` | Yes | Size to resize to | Both > 0, matches alignment params |

### Lifecycle

1. **Creation**: Built by `find_chip_images()` function
2. **Validation**: Dimension checks performed during creation
3. **Usage**: Passed to GUI for preview notification if mismatches exist
4. **Processing**: Used by `stitch_chip_images()` to load/resize/placeholder chips

---

## Entity Extension: StitchedResult (from 001)

**Purpose**: Extends existing `StitchedResult` to include alignment parameters.

**File**: `src/models/stitched_result.py` (modified)

### New Fields

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `alignment_parameters` | `Optional[AlignmentParameters]` | No | Parameters captured during stitching | Valid AlignmentParameters if present |
| `is_chip_stitch` | `bool` | Yes | Whether this is chip stitching result | Defaults to False |
| `chip_metadata` | `Optional[ChipStitchMetadata]` | No | Chip-specific result metadata | Required if is_chip_stitch=True |

### Nested Type: ChipStitchMetadata

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `chip_images_found` | `int` | Yes | Number of chip images discovered | >= 0, <= 4 |
| `placeholders_generated` | `int` | Yes | Number of black placeholders used | >= 0, <= 4 |
| `dimension_transformations` | `List[DimensionTransformation]` | Yes | Resizes performed | Can be empty |
| `source_alignment_file` | `Path` | Yes | Path to alignment parameters JSON | Must be valid path |
| `source_alignment_timestamp` | `str` | Yes | When parameters were created | ISO 8601 format |

### Nested Type: DimensionTransformation

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `quadrant` | `Quadrant` | Yes | Which chip image was resized | Valid Quadrant enum |
| `original_dimensions` | `Tuple[int, int]` | Yes | Size before resize | Both > 0 |
| `final_dimensions` | `Tuple[int, int]` | Yes | Size after resize | Both > 0 |

### Lifecycle

1. **Original Stitching**: `alignment_parameters` populated and saved to JSON
2. **Chip Stitching**: New `StitchedResult` created with `is_chip_stitch=True` and `chip_metadata` populated
3. **Display**: Result window shows chip metadata if present

---

## Entity: PlaceholderImage (Conceptual)

**Purpose**: Represents a generated black placeholder for missing chip images.

**Note**: Not a persistent dataclass - generated on-demand as NumPy array.

### Generation Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `width` | `int` | Width from AlignmentParameters for corresponding quadrant |
| `height` | `int` | Height from AlignmentParameters for corresponding quadrant |
| `color` | `Tuple[int, int, int]` | Always (0, 0, 0) - pure black |
| `dtype` | `np.dtype` | Always `np.uint8` |

### Generation

```python
def generate_placeholder(width: int, height: int) -> np.ndarray:
    """Generate pure black placeholder image."""
    return np.zeros((height, width, 3), dtype=np.uint8)
```

---

## Validation Rules

### Cross-Entity Rules

1. **Alignment-Chip Correspondence**: Each quadrant in `ChipImageSet.chip_images` must have corresponding entry in `AlignmentParameters.quadrants`

2. **Dimension Consistency**: If chip image found, its dimensions after resize must match `AlignmentParameters` dimensions for that quadrant

3. **Path Validation**: All file paths in `AlignmentParameters` must use absolute paths for reliability

4. **Quadrant Count**: Total quadrants in alignment parameters must match quadrants in original stitched result (1-4)

### Parameter File Validation

Performed by `alignment_manager.validate_alignment_params()`:

**Layer 1 - Format Validation**:
- File must be valid JSON
- Must parse without errors

**Layer 2 - Completeness Validation**:
- Required top-level fields present: `version`, `timestamp`, `stitched_image_path`, `quadrants`
- Each quadrant entry has: `quadrant`, `original_image_path`, `dimensions`, `position_shift`
- `dimensions` and `position_shift` are correct types (list/tuple of numbers)

**Layer 3 - Existence Validation**:
- `original_image_path` files exist (warn if missing but don't block)
- `stitched_image_path` is valid path (doesn't need to exist)

---

## State Transitions

### AlignmentParameters State Machine

```
[Not Exist] --stitch_quadrants()--> [Generated In Memory]
                                            |
                                            | save_alignment_params()
                                            v
                                        [Saved to Disk]
                                            |
                                            | load_alignment_params()
                                            v
                                        [Loaded & Validated]
                                            |
                                            +--[Valid]---> [Available for Chip Stitch]
                                            |
                                            +--[Invalid]-> [Error: User Notified]
```

### ChipImageSet State Machine

```
[AlignmentParameters Available] --find_chip_images()--> [Chip Images Discovered]
                                                                |
                                                                | check_dimensions()
                                                                v
                                                    [Dimension Mismatches Identified]
                                                                |
                                                                +--[Has Mismatches]---> [Preview Dialog]
                                                                |                              |
                                                                |                              +--[User Proceeds]--> [Processing]
                                                                |                              |
                                                                |                              +--[User Cancels]---> [Aborted]
                                                                |
                                                                +--[No Mismatches]---> [Processing]
```

---

## JSON Schema

### AlignmentParameters JSON Schema (v1.0)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "timestamp", "stitched_image_path", "quadrants"],
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "stitched_image_path": {
      "type": "string"
    },
    "quadrants": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "items": {
        "type": "object",
        "required": ["quadrant", "original_image_path", "dimensions", "position_shift"],
        "properties": {
          "quadrant": {
            "type": "string",
            "enum": ["NE", "NW", "SE", "SW"]
          },
          "original_image_path": {
            "type": "string"
          },
          "dimensions": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
            "minItems": 2,
            "maxItems": 2
          },
          "position_shift": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 2,
            "maxItems": 2
          }
        }
      }
    }
  }
}
```

---

## Relationships Diagram

```
AlignmentParameters (1) ----generated-from----> (1) StitchedResult [original]
        |
        | stored-as
        |
        v
 JSON File on Disk
        |
        | loaded-by
        |
        v
AlignmentParameters (1) ----used-to-find----> (1) ChipImageSet
        |                                              |
        | reused-in                                    | processed-by
        |                                              v
        +--------------------------> (1) stitch_chip_images() ---> (1) StitchedResult [chip]
                                                                            |
                                                                            | contains
                                                                            v
                                                                   ChipStitchMetadata
```

---

## Implementation Notes

### Python Type Hints

All dataclasses use comprehensive type hints for IDE support and static analysis:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from src.models import Quadrant

@dataclass
class QuadrantAlignment:
    quadrant: Quadrant
    original_image_path: Path
    dimensions: Tuple[int, int]
    position_shift: Tuple[float, float]

@dataclass
class AlignmentParameters:
    version: str
    timestamp: str
    stitched_image_path: Path
    quadrants: List[QuadrantAlignment]
```

### Serialization Helper

```python
def to_dict(params: AlignmentParameters) -> dict:
    """Convert AlignmentParameters to JSON-serializable dict."""
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
```

### Deserialization Helper

```python
def from_dict(data: dict) -> AlignmentParameters:
    """Create AlignmentParameters from JSON dict."""
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
```

