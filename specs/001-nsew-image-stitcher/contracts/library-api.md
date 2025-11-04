# Library API Contracts: NSEW Image Stitcher

**Phase**: 1 (Design)  
**Date**: 2025-11-04  
**Purpose**: Function signatures and contracts for core processing library (src/lib/)

All library functions are pure (no side effects except file I/O where explicitly documented) and framework-agnostic (no GUI dependencies).

---

## Module: io.py

### load_image

**Purpose**: Load microscopy image from file and return as NumPy array with metadata.

**Signature**:
```python
def load_image(file_path: str, channel_index: int = 0) -> tuple[np.ndarray, ImageMetadata]:
    """
    Load image from .czi, .lsm, .tif, or .tiff file.
    
    Args:
        file_path: Absolute path to image file
        channel_index: Channel to extract if multi-channel (0-indexed)
    
    Returns:
        tuple: (image_data, metadata)
            - image_data: NumPy array, dtype uint8 or uint16, shape (H, W) for grayscale
            - metadata: ImageMetadata object with pixel_size_um, magnification, etc.
    
    Raises:
        FileNotFoundError: If file_path does not exist
        UnsupportedFormatError: If file extension not in [.czi, .lsm, .tif, .tiff]
        CorruptedFileError: If file cannot be read (corrupted, wrong format, etc.)
        ChannelIndexError: If channel_index >= num_channels in file
    
    Performance:
        - Typical: 0.5-2 seconds for 2000x2000 uint16 image
        - Large: Up to 5 seconds for 4000x4000 uint16 image
    
    Side Effects:
        - Reads from disk
    """
```

**Behavior**:
- Automatically detects format from file extension
- For .czi files: uses czifile library
- For .lsm/.tif/.tiff: uses tifffile library
- Extracts first channel by default if multi-channel
- Returns metadata dict with keys: pixel_size_um, magnification, acquisition_date (all optional)
- If metadata unavailable, returns ImageMetadata with None values

**Test Cases**:
- Valid .czi file → returns array + metadata
- Valid .tif file → returns array + metadata
- Non-existent file → raises FileNotFoundError
- Corrupted file → raises CorruptedFileError
- .bmp file → raises UnsupportedFormatError
- Multi-channel file, channel_index=1 → returns second channel
- channel_index=5, file has 3 channels → raises ChannelIndexError

---

### save_image

**Purpose**: Save NumPy array as image file with optional compression.

**Signature**:
```python
def save_image(
    image_data: np.ndarray,
    output_path: str,
    format: str = "tiff",
    compression_level: int | None = None,
    metadata: ImageMetadata | None = None
) -> None:
    """
    Save image data to disk.
    
    Args:
        image_data: NumPy array to save
        output_path: Destination file path (extension auto-added if missing)
        format: One of ["tiff", "png", "jpeg"]
        compression_level: Compression (0-9 for PNG/TIFF, 0-100 for JPEG). None=default
        metadata: Optional metadata to embed (pixel_size, magnification, etc.)
    
    Raises:
        ValueError: If format not supported or compression_level out of range
        IOError: If cannot write to output_path (permissions, disk full, etc.)
    
    Performance:
        - TIFF (uncompressed): ~500 MB/s
        - TIFF (compressed level 6): ~100 MB/s
        - PNG (level 6): ~50 MB/s
    
    Side Effects:
        - Writes to disk (creates or overwrites file at output_path)
    """
```

**Behavior**:
- Appends file extension if not present (.tif for tiff, .png, .jpg for jpeg)
- For TIFF: embeds ImageJ-compatible metadata tags if metadata provided
- For uint16 data: TIFF supports full range, PNG supports full range, JPEG downcasts to uint8
- Creates parent directories if they don't exist

**Test Cases**:
- Save uint16 array as TIFF → file readable by tifffile
- Save with compression_level=6 → file size < uncompressed
- Save to read-only directory → raises IOError
- format="bmp" → raises ValueError

---

## Module: keyword_detector.py

### detect_quadrant

**Purpose**: Extract spatial quadrant from filename using keyword matching.

**Signature**:
```python
def detect_quadrant(filename: str) -> Quadrant | None:
    """
    Detect spatial quadrant (NE/NW/SE/SW) from filename.
    
    Args:
        filename: Filename (with or without path/extension)
    
    Returns:
        Quadrant enum value (NE/NW/SE/SW) if unambiguous, None if ambiguous or not detected
    
    Raises:
        ValueError: If filename is empty string
    
    Performance:
        - <1 ms (regex matching)
    
    Side Effects:
        - None
    """
```

**Behavior**:
- Case-insensitive matching
- Priority order: Exact 2-letter (NE/NW/SE/SW) > Full words (Northeast/etc.) > Cardinals (N+E)
- Returns None if multiple conflicting keywords (e.g., "North_South")
- Returns None if no spatial keywords detected
- Extracts from full path or filename only (both supported)

**Test Cases**:
- "data_NE.czi" → Quadrant.NE
- "image_northeast.tif" → Quadrant.NE
- "North_East_section.lsm" → Quadrant.NE
- "LINE_data.czi" (contains "NE") → None (word boundary check)
- "North_South.czi" → None (ambiguous)
- "sample_001.czi" → None (no keywords)
- "" (empty string) → raises ValueError

---

## Module: stitching.py

### stitch_quadrants

**Purpose**: Stitch 1-4 quadrant images into single panorama with quality metrics.

**Signature**:
```python
def stitch_quadrants(
    quadrants: list[QuadrantImage],
    config: StitchingConfig
) -> StitchedResult:
    """
    Stitch quadrant images into seamless panorama.
    
    Args:
        quadrants: List of 1-4 QuadrantImage objects with loaded image_data
        config: Stitching configuration parameters
    
    Returns:
        StitchedResult with stitched_image_data and quality_metrics
    
    Raises:
        ValueError: If quadrants list empty or contains duplicate quadrants
        InsufficientOverlapError: If detected overlap < config.overlap_threshold_percent
        AlignmentFailureError: If feature matching fails (confidence < config.confidence_threshold)
        DimensionMismatchError: If images have incompatible dtypes or channel counts
    
    Performance:
        - 4x(2000x2000) images: ~30-60 seconds typical
        - Dominated by feature detection and blending
    
    Side Effects:
        - None (operates on in-memory data only)
    """
```

**Behavior**:
- Normalizes dimensions if images differ (according to config.resize_strategy)
- Handles missing quadrants by interpolating or filling (according to config.missing_quadrant_fill)
- Uses OpenCV stitcher with custom camera estimates based on quadrant positions
- Computes quality metrics from feature matches and RANSAC inliers
- Returns stitched image at full resolution (no automatic downsampling - caller's responsibility)

**Algorithm Steps**:
1. Validate inputs (non-empty, unique quadrants, compatible dtypes/channels)
2. Normalize dimensions if needed (resize to common resolution)
3. Fill missing quadrants (if <4 quadrants provided)
4. Estimate initial camera positions from quadrant spatial layout
5. Detect features using SIFT/ORB
6. Compute pairwise homographies with RANSAC
7. Optimize global bundle adjustment
8. Perform multiband blending at seam boundaries
9. Compute quality metrics (confidence scores, overlap percentages)
10. Return StitchedResult

**Test Cases**:
- 4 quadrants, 15% overlap → successful stitch, high confidence
- 2 quadrants (NE, NW), config.missing_quadrant_fill="black" → stitched with black fill
- 4 quadrants, 5% overlap, threshold=10% → raises InsufficientOverlapError
- Empty list → raises ValueError
- Two images with same quadrant (both NE) → raises ValueError
- Images with different dtypes (uint8 vs uint16) → raises DimensionMismatchError

---

### compute_overlap_percentage

**Purpose**: Calculate overlap percentage between two aligned images.

**Signature**:
```python
def compute_overlap_percentage(
    img1: np.ndarray,
    img2: np.ndarray,
    homography: np.ndarray
) -> float:
    """
    Compute overlap percentage between two images given their homography.
    
    Args:
        img1: First image (reference)
        img2: Second image to be warped
        homography: 3x3 homography matrix transforming img2 to img1 coordinates
    
    Returns:
        Overlap percentage [0.0, 100.0] of shared pixel area
    
    Raises:
        ValueError: If homography not 3x3 or contains NaN/Inf
    
    Performance:
        - <100 ms for typical images
    
    Side Effects:
        - None
    """
```

**Behavior**:
- Warps img2 to img1 coordinate space using homography
- Computes intersection area of valid pixel regions
- Returns percentage relative to smaller image area

---

## Module: dimension_handler.py

### normalize_dimensions

**Purpose**: Resize images to common resolution.

**Signature**:
```python
def normalize_dimensions(
    images: list[QuadrantImage],
    strategy: str = "largest",
    interpolation: str = "bicubic"
) -> list[QuadrantImage]:
    """
    Resize all images to common dimensions.
    
    Args:
        images: List of QuadrantImage objects with loaded image_data
        strategy: "largest" (upscale to max) or "smallest" (downscale to min)
        interpolation: One of ["bicubic", "lanczos", "linear"]
    
    Returns:
        New list of QuadrantImage objects with resized image_data and updated dimensions
    
    Raises:
        ValueError: If strategy or interpolation invalid
        EmptyListError: If images list is empty
    
    Performance:
        - Resize 2000x2000 to 3000x3000: ~200 ms (bicubic)
    
    Side Effects:
        - None (returns new QuadrantImage objects, originals unchanged)
    """
```

**Behavior**:
- Computes target dimensions from max or min across all images
- Resizes each image using OpenCV with specified interpolation
- Preserves aspect ratio (pads if necessary)
- Returns new QuadrantImage instances (immutable operation)

**Test Cases**:
- 3 images: 2000x2000, 2500x2500, 3000x3000, strategy="largest" → all resized to 3000x3000
- strategy="smallest" → all resized to 2000x2000
- interpolation="invalid" → raises ValueError

---

### downsample_for_display

**Purpose**: Downsample large image for memory-efficient display.

**Signature**:
```python
def downsample_for_display(
    image: np.ndarray,
    max_dimension: int = 4000
) -> np.ndarray:
    """
    Downsample image if dimensions exceed threshold.
    
    Args:
        image: Input image array
        max_dimension: Maximum allowed width or height
    
    Returns:
        Downsampled image (original if already small enough)
    
    Raises:
        ValueError: If max_dimension < 100
    
    Performance:
        - Downsample 8000x8000 to 4000x4000: ~300 ms
    
    Side Effects:
        - None
    """
```

**Behavior**:
- If both dimensions ≤ max_dimension, returns original image unchanged
- Otherwise, scales down preserving aspect ratio using INTER_AREA (best for downsampling)
- Ensures at least one dimension equals max_dimension

---

## Module: config_manager.py

### save_config

**Purpose**: Serialize StitchedResult to JSON file.

**Signature**:
```python
def save_config(result: StitchedResult, output_path: str) -> None:
    """
    Save stitching result metadata to JSON file.
    
    Args:
        result: StitchedResult object to serialize
        output_path: Destination file path for JSON
    
    Raises:
        IOError: If cannot write to output_path
    
    Performance:
        - <10 ms (config files ~2KB)
    
    Side Effects:
        - Writes JSON file to disk
    """
```

**Behavior**:
- Serializes all StitchedResult fields except stitched_image_data
- Includes source file paths, config parameters, quality metrics
- Pretty-printed JSON with 2-space indentation
- Includes software version and timestamp

---

### load_config

**Purpose**: Deserialize stitching configuration from JSON file.

**Signature**:
```python
def load_config(config_path: str) -> StitchingConfig:
    """
    Load stitching configuration from JSON file.
    
    Args:
        config_path: Path to JSON config file
    
    Returns:
        StitchingConfig object populated from JSON
    
    Raises:
        FileNotFoundError: If config_path does not exist
        JSONDecodeError: If file is not valid JSON
        ValidationError: If JSON structure doesn't match expected schema
    
    Performance:
        - <10 ms
    
    Side Effects:
        - Reads from disk
    """
```

**Behavior**:
- Parses JSON file
- Validates all required fields present
- Constructs StitchingConfig object
- Logs warning if config version differs from current application version

---

## Error Hierarchy

```
Exception
├── ImageProcessingError (base for all library errors)
│   ├── FileError
│   │   ├── UnsupportedFormatError
│   │   ├── CorruptedFileError
│   │   └── ChannelIndexError
│   ├── StitchingError
│   │   ├── InsufficientOverlapError
│   │   ├── AlignmentFailureError
│   │   └── DimensionMismatchError
│   ├── ValidationError
│   └── EmptyListError
```

All custom exceptions inherit from `ImageProcessingError` for easy catch-all handling in GUI layer.

---

## Testability

All functions designed for unit testing:
- **Pure functions**: No global state, deterministic outputs
- **Explicit parameters**: All inputs passed as arguments
- **Type hints**: Enable static type checking with mypy
- **Small scope**: Each function has single responsibility
- **Mockable dependencies**: File I/O isolated, can be mocked in tests

**Example Test**:
```python
def test_detect_quadrant_exact_match():
    assert detect_quadrant("data_NE.czi") == Quadrant.NE
    assert detect_quadrant("image_SW.tif") == Quadrant.SW

def test_detect_quadrant_ambiguous():
    assert detect_quadrant("North_South.czi") is None
```

---

## Performance Guarantees

| Function | Input Size | Max Time | Memory |
|----------|-----------|----------|--------|
| load_image | 2000x2000 | 2 sec | 8 MB |
| detect_quadrant | any | 1 ms | <1 KB |
| stitch_quadrants | 4x(2000x2000) | 60 sec | 100 MB |
| normalize_dimensions | 4x(2000x2000) | 1 sec | 64 MB |
| downsample_for_display | 8000x8000 | 0.5 sec | 128 MB |
| save_image | 4000x4000 | 2 sec | 32 MB |

These guarantees ensure compliance with constitution Performance Standards.

