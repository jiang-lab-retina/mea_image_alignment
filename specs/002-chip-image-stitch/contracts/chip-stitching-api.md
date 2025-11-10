# Library API Contract: Chip Image Stitching

**Feature**: 002-chip-image-stitch  
**Date**: 2025-11-05  
**Module**: `src.lib`

## Overview

This document specifies the public API contracts for chip image stitching functionality. These functions extend the existing `src.lib` module to support alignment parameter persistence, chip image discovery, and parameter-based stitching.

---

## Module: `alignment_manager`

**File**: `src/lib/alignment_manager.py`

### Function: `save_alignment_params`

**Purpose**: Save alignment parameters to JSON file on disk.

**Signature**:
```python
def save_alignment_params(
    params: AlignmentParameters,
    output_path: Path
) -> None:
    """
    Save alignment parameters to JSON file.
    
    Args:
        params: AlignmentParameters instance to save
        output_path: Path to output JSON file (will be created/overwritten)
        
    Raises:
        IOError: If file cannot be written
        ValidationError: If params fails validation before save
        
    Side Effects:
        - Creates JSON file at output_path
        - Overwrites existing file if present
        - Creates parent directories if needed
    """
```

**Behavior**:
- Validates parameters before saving (ensures all required fields present)
- Serializes to JSON with 2-space indentation for readability
- Converts Path objects to strings
- Uses UTF-8 encoding
- Atomic write (writes to temp file, then renames)

**Example**:
```python
params = AlignmentParameters(...)
output_file = Path("./stitched_result_alignment.json")
save_alignment_params(params, output_file)
# Result: JSON file created at output_file
```

---

### Function: `load_alignment_params`

**Purpose**: Load alignment parameters from JSON file.

**Signature**:
```python
def load_alignment_params(
    input_path: Path
) -> AlignmentParameters:
    """
    Load alignment parameters from JSON file.
    
    Args:
        input_path: Path to JSON file to load
        
    Returns:
        AlignmentParameters instance loaded from file
        
    Raises:
        FileNotFoundError: If input_path does not exist
        ParameterFileCorruptedError: If JSON is invalid/malformed
        ParameterFileIncompleteError: If required fields missing
        ValidationError: If loaded parameters fail validation
    """
```

**Behavior**:
- Reads JSON file from disk
- Parses JSON into dict
- Converts dict to AlignmentParameters dataclass
- Performs validation (format, completeness)
- Converts string paths back to Path objects
- Does NOT check if referenced image files exist (see `validate_alignment_params`)

**Example**:
```python
params = load_alignment_params(Path("./stitched_result_alignment.json"))
# Returns: AlignmentParameters instance
```

---

### Function: `validate_alignment_params`

**Purpose**: Perform comprehensive 3-layer validation on alignment parameters.

**Signature**:
```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    layer: int  # 1=format, 2=completeness, 3=existence

def validate_alignment_params(
    params: AlignmentParameters,
    check_file_existence: bool = True
) -> ValidationResult:
    """
    Validate alignment parameters comprehensively.
    
    Args:
        params: AlignmentParameters instance to validate
        check_file_existence: Whether to check if referenced images exist
        
    Returns:
        ValidationResult with is_valid, errors, warnings, layer
        
    Raises:
        Never raises - all validation failures returned in ValidationResult
        
    Validation Layers:
        1. Format: Field types correct (str, int, float, Path)
        2. Completeness: All required fields present and non-empty
        3. Existence: Referenced image files exist on disk (if check_file_existence=True)
    """
```

**Behavior**:
- Layer 1 (Format): Checks field types match schema
- Layer 2 (Completeness): Checks all required fields present
- Layer 3 (Existence): Checks original_image_path files exist (optional)
- Returns first layer that fails
- Warnings for non-critical issues (e.g., missing images but dimensions present)
- Errors for critical issues (e.g., corrupted format, missing fields)

**Example**:
```python
result = validate_alignment_params(params, check_file_existence=True)
if not result.is_valid:
    print(f"Validation failed at layer {result.layer}: {result.errors}")
```

---

## Module: `chip_image_finder`

**File**: `src/lib/chip_image_finder.py`

### Function: `find_chip_images`

**Purpose**: Discover chip images based on original quadrant filenames and alignment parameters.

**Signature**:
```python
def find_chip_images(
    alignment_params: AlignmentParameters
) -> ChipImageSet:
    """
    Find chip images corresponding to original quadrant images.
    
    Args:
        alignment_params: Parameters containing original image paths and quadrants
        
    Returns:
        ChipImageSet with discovered chip images, missing quadrants, dimension mismatches
        
    Raises:
        FileNotFoundError: If original image directory doesn't exist
        ValidationError: If alignment_params invalid
        
    Behavior:
        - Extracts directory and extension from original image paths
        - Generates chip image filenames using generate_chip_filename()
        - Searches for chip images in same directory as originals
        - Loads dimensions of found chip images
        - Identifies dimension mismatches
        - Returns ChipImageSet even if some/all chips missing
    """
```

**Behavior**:
- For each quadrant in alignment_params:
  - Extract original image path
  - Generate expected chip filename (insert "chip" before quadrant)
  - Check if chip file exists
  - If exists: load dimensions, check against alignment params
  - If missing: add to missing_quadrants list
- Returns ChipImageSet with complete discovery results

**Example**:
```python
chip_set = find_chip_images(alignment_params)
print(f"Found {len(chip_set.chip_images)} chip images")
print(f"Missing {len(chip_set.missing_quadrants)} quadrants")
print(f"Need resize: {len(chip_set.dimension_mismatches)}")
```

---

### Function: `generate_chip_filename`

**Purpose**: Generate chip image filename from original quadrant filename.

**Signature**:
```python
def generate_chip_filename(
    original_path: Path
) -> str:
    """
    Generate chip image filename by inserting 'chip' before quadrant identifier.
    
    Args:
        original_path: Path to original quadrant image
        
    Returns:
        Expected chip image filename (without path)
        
    Raises:
        ValueError: If original_path doesn't contain valid quadrant identifier
        
    Examples:
        original_path: "sample_NE.czi" -> "sample_chipNE.czi"
        original_path: "2025.10.22_opnT2_SW.czi" -> "2025.10.22_opnT2_chipSW.czi"
    """
```

**Behavior**:
- Extracts filename stem (without extension)
- Detects quadrant identifier (NE, NW, SE, SW) at end of stem
- Inserts "chip" immediately before quadrant identifier
- Appends original file extension
- Raises ValueError if no valid quadrant found

**Example**:
```python
chip_name = generate_chip_filename(Path("sample_NE.czi"))
# Returns: "sample_chipNE.czi"
```

---

## Module: `chip_stitcher`

**File**: `src/lib/chip_stitcher.py`

### Function: `stitch_chip_images`

**Purpose**: Stitch chip images using stored alignment parameters (bypassing feature detection).

**Signature**:
```python
def stitch_chip_images(
    chip_image_set: ChipImageSet,
    alignment_params: AlignmentParameters,
    config: StitchingConfig,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> StitchedResult:
    """
    Stitch chip images using alignment parameters from original stitching.
    
    Args:
        chip_image_set: Discovered chip images (from find_chip_images())
        alignment_params: Position shifts to apply
        config: Stitching configuration (blending, quality, etc.)
        progress_callback: Optional callback(percent, message) for progress updates
        
    Returns:
        StitchedResult with is_chip_stitch=True and chip_metadata populated
        
    Raises:
        ChipImageDimensionError: If resize fails
        StitchingError: If stitching fails
        ValidationError: If parameters/chip_set invalid
        
    Behavior:
        - Loads chip images (or generates placeholders for missing)
        - Resizes chip images to match alignment params dimensions
        - Applies position shifts from alignment_params
        - Blends images using config settings
        - Returns StitchedResult with chip metadata
        
    Progress Callbacks:
        0%: "Loading chip images..."
        25%: "Normalizing dimensions..."
        50%: "Applying alignment..."
        75%: "Blending images..."
        100%: "Complete"
    """
```

**Behavior**:
- **Load Phase (0-25%)**:
  - Load each chip image from chip_image_set
  - Generate black placeholders for missing quadrants
  - Record which are placeholders vs. real images
  
- **Normalize Phase (25-50%)**:
  - Resize chip images to match alignment params dimensions
  - Use high-quality interpolation (LANCZOS)
  - Record dimension transformations
  
- **Alignment Phase (50-75%)**:
  - Apply position shifts from alignment params
  - Use affine transformation matrices
  - No feature detection performed
  
- **Blending Phase (75-100%)**:
  - Blend overlapping regions using config settings
  - Composite into final stitched image
  - Generate quality metrics
  
- **Metadata**:
  - Populate ChipStitchMetadata with discovery/transformation details
  - Include reference to alignment params file

**Example**:
```python
def progress(percent, msg):
    print(f"{percent}%: {msg}")

result = stitch_chip_images(
    chip_image_set=chip_set,
    alignment_params=params,
    config=config,
    progress_callback=progress
)
# Returns: StitchedResult with chip metadata
```

---

### Function: `generate_placeholder_image`

**Purpose**: Generate pure black placeholder image for missing chip image.

**Signature**:
```python
def generate_placeholder_image(
    width: int,
    height: int
) -> np.ndarray:
    """
    Generate pure black placeholder image.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        
    Returns:
        NumPy array of shape (height, width, 3) with dtype uint8, all zeros (black)
        
    Raises:
        ValueError: If width or height <= 0
    """
```

**Behavior**:
- Creates NumPy array of zeros
- Shape: (height, width, 3) for RGB
- Data type: uint8 (0-255 range)
- All values: 0 (pure black)

**Example**:
```python
placeholder = generate_placeholder_image(2048, 2048)
# Returns: 2048x2048x3 array of zeros
```

---

## Module Extensions: `stitching`

**File**: `src/lib/stitching.py` (modified)

### Function: `stitch_quadrants` (Modified)

**Changes**: Capture and return alignment parameters

**New Signature**:
```python
def stitch_quadrants(
    quadrant_images: List[QuadrantImage],
    config: StitchingConfig,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> StitchedResult:  # Now includes alignment_parameters field
    """
    Stitch quadrant images into single composite.
    
    [Existing parameters and behavior unchanged]
    
    NEW Behavior:
        - Captures position shifts (dx, dy) during alignment phase
        - Populates alignment_parameters field in StitchedResult
        - alignment_parameters can be saved to disk for chip stitching
    """
```

**Implementation Notes**:
- Extract position shift values after OpenCV stitching completes
- Create AlignmentParameters instance with quadrant data
- Populate StitchedResult.alignment_parameters before return
- No change to existing stitching algorithm

---

## Error Handling

### Exception Hierarchy

```python
# In src/lib/__init__.py

class AlignmentParameterError(ImageProcessingError):
    """Base exception for alignment parameter issues."""
    pass

class ParameterFileCorruptedError(AlignmentParameterError):
    """Raised when alignment parameter file is invalid JSON."""
    pass

class ParameterFileIncompleteError(AlignmentParameterError):
    """Raised when alignment parameter file missing required fields."""
    pass

class ParameterImageMismatchError(AlignmentParameterError):
    """Raised when referenced original images don't exist."""
    pass

class ChipImageError(ImageProcessingError):
    """Base exception for chip image issues."""
    pass

class ChipImageNotFoundError(ChipImageError):
    """Raised when expected chip images cannot be found."""
    pass

class ChipImageDimensionError(ChipImageError):
    """Raised when chip image dimension operations fail."""
    pass
```

---

## Usage Examples

### Complete Workflow: Original + Chip Stitching

```python
from pathlib import Path
from src.lib.stitching import stitch_quadrants
from src.lib.alignment_manager import save_alignment_params, load_alignment_params
from src.lib.chip_image_finder import find_chip_images
from src.lib.chip_stitcher import stitch_chip_images
from src.models import StitchingConfig

# Step 1: Stitch original quadrants
result = stitch_quadrants(quadrant_images, config)

# Step 2: Save alignment parameters
output_path = result.output_path.parent / f"{result.output_path.stem}_alignment.json"
save_alignment_params(result.alignment_parameters, output_path)

# Step 3 (later/different session): Load parameters
params = load_alignment_params(output_path)

# Step 4: Validate parameters
validation = validate_alignment_params(params)
if not validation.is_valid:
    raise ValueError(f"Invalid parameters: {validation.errors}")

# Step 5: Find chip images
chip_set = find_chip_images(params)

# Step 6: Stitch chip images
chip_result = stitch_chip_images(chip_set, params, config)

print(f"Chip stitching complete!")
print(f"Found {chip_result.chip_metadata.chip_images_found} chips")
print(f"Used {chip_result.chip_metadata.placeholders_generated} placeholders")
```

---

## API Versioning

**Current Version**: 1.0

**Backward Compatibility**:
- Alignment parameter JSON schema version 1.0
- Future versions must support loading v1.0 files
- Breaking changes require major version bump

**Future Enhancements** (Not in Scope):
- Support for rotation parameters (not just translation)
- Support for different alignment algorithms
- Support for confidence scores in parameters

