# Research: NSEW Image Stitcher

**Phase**: 0 (Research)  
**Date**: 2025-11-04  
**Purpose**: Technical research and decision documentation for implementation planning

## Research Questions

This document addresses all technical unknowns from the Technical Context section and provides rationale for technology choices.

---

## 1. GUI Framework Selection

**Question**: Which Python GUI framework best supports cross-platform desktop development with image display capabilities?

**Decision**: PyQt6

**Rationale**:
- **Mature & Stable**: PyQt has 20+ years of development, extensive documentation, and proven track record in scientific applications
- **Image Handling**: Native QPixmap and QImage classes optimized for large image display with efficient memory management
- **Cross-Platform**: Identical behavior across Windows, macOS, Linux without platform-specific code
- **Scientific Adoption**: Widely used in microscopy software (napari, ImageJ plugins, CellProfiler UI components)
- **Layout Flexibility**: Qt's layout system easily supports 2x2 quadrant grid with synchronized zoom/pan
- **Threading Support**: QThread for non-blocking stitching operations with signals/slots for progress updates
- **File Dialogs**: Native platform file pickers via QFileDialog

**Alternatives Considered**:
- **tkinter**: Built-in but limited image handling (PIL required), less polished UI, weaker for large images
- **wxPython**: Good cross-platform support but smaller community, less scientific adoption
- **Kivy**: More mobile-focused, overkill for desktop-only app
- **Dear PyGui**: Newer, less mature, smaller ecosystem

**Implementation Notes**:
- Use QGraphicsView for each quadrant viewer to enable smooth zoom/pan with large images
- Leverage QThread + signals for background stitching operations
- Use QSettings for persistent application configuration

---

## 2. Microscopy File Format Libraries

**Question**: How to reliably read .czi, .lsm, and .tif/.tiff microscopy formats with metadata extraction?

**Decision**: 
- **czifile** for .czi (Carl Zeiss Image) format
- **tifffile** for .tif/.tiff and .lsm (LSM is TIFF-based) formats

**Rationale**:

### czifile (https://pypi.org/project/czifile/)
- **Purpose-Built**: Specifically designed for Zeiss CZI format, handles proprietary compression
- **Metadata Access**: Exposes full CZI XML metadata (acquisition parameters, pixel size, magnification)
- **NumPy Integration**: Returns image data as NumPy arrays directly
- **Maintained**: Active development, used in scientific Python ecosystem
- **Multi-Channel Support**: Handles fluorescence channels, z-stacks, time series

### tifffile (https://pypi.org/project/tifffile/)
- **Comprehensive**: Handles all TIFF variants including BigTIFF, multi-page, ImageJ format
- **LSM Support**: Zeiss LSM files are TIFF-based with custom tags - tifffile handles them
- **Metadata Extraction**: Reads ImageJ metadata, TIFF tags, embedded descriptions
- **NumPy Integration**: Returns as NumPy arrays with correct dtype (uint16 for 16-bit images)
- **Scientific Standard**: De facto standard for TIFF reading in Python scientific computing

**Alternatives Considered**:
- **Pillow (PIL)**: Basic TIFF support only, no CZI/LSM, limited metadata, struggles with 16-bit scientific images
- **imageio**: Higher-level but delegates to other libraries, adds abstraction overhead
- **python-bioformats**: Comprehensive (supports 150+ formats) but requires Java runtime (JVM), heavy dependency
- **aicsimageio**: Wrapper around multiple readers, overkill for our 3-format requirement

**Implementation Notes**:
- Detect format by file extension: `.czi` → czifile, `.tif/.tiff/.lsm` → tifffile
- Extract pixel size, magnification, acquisition date from metadata for QuadrantImage entity
- Handle multi-channel files: extract first channel by default, provide channel selector in future enhancement

---

## 3. Image Stitching Algorithm

**Question**: What stitching approach balances quality, performance, and implementation complexity?

**Decision**: OpenCV stitching module with custom extensions

**Rationale**:

### OpenCV Stitcher API (cv2.Stitcher_create())
- **Production-Ready**: Used in panorama creation, well-tested algorithm
- **Feature-Based Alignment**: Detects SIFT/ORB features, computes homography transform (handles rotation, perspective)
- **Seam Blending**: Multi-band blending for seamless transitions
- **Performance**: C++ implementation with Python bindings, optimized for large images
- **Configururable**: Adjustable parameters (confidence threshold, registration resol, seam finder type)
- **NumPy Integration**: Accepts/returns NumPy arrays (no format conversion overhead)

### Custom Extensions Required
- **Missing Quadrant Interpolation**: OpenCV stitcher expects all images; we need to handle 1-3 quadrants
  - Solution: Generate blank placeholders for missing quadrants, post-process to fill/mask
- **Quality Metrics**: OpenCV returns stitched image but limited quality feedback
  - Solution: Extract confidence scores from feature matching, compute overlap percentages
- **Spatial Constraint**: Enforce quadrant spatial relationships (NE must be top-right of SE, etc.)
  - Solution: Provide initial camera estimates based on quadrant positions to guide homography

**Alternatives Considered**:
- **Image-stitching library** (https://github.com/lukemelas/image-stitching): Pure Python, educational, but slower and less robust than OpenCV
- **Hugin-based**: Command-line interface to Hugin panorama tools - heavy dependency, harder to control programmatically
- **Custom Implementation**: Phase correlation + blending from scratch - high complexity, reinventing wheel
- **Deep Learning**: Newer approaches (e.g., SuperGlue) - overkill for controlled quadrant layout, inference overhead

**Implementation Notes**:
- Use `cv2.Stitcher_create(cv2.Stitcher_PANORAMA)` mode for planar stitching
- Set custom confidence threshold based on overlap requirements (FR-004: 10% minimum)
- For missing quadrants: create zero-filled placeholder with average dimensions, mask in post-processing
- Extract match counts and RANSAC inlier ratios for quality metrics

---

## 4. Dimension Normalization Strategy

**Question**: When quadrant images have different dimensions, should we resize to smallest, largest, or provide user choice?

**Decision**: Resize to largest dimension with user notification

**Rationale**:
- **Data Preservation**: Upsampling smaller images to largest dimensions preserves maximum detail from high-res images
- **Scientific Priority**: Microscopy workflows prefer avoiding downsampling (information loss) when possible
- **User Awareness**: Notification dialog before stitching shows original → target dimensions, maintains transparency
- **Consistent Output**: All quadrants at same resolution simplifies stitching algorithm (uniform pixel spacing)

**Interpolation Method**: Bicubic (OpenCV's `cv2.INTER_CUBIC`) for upsampling, Lanczos (`cv2.INTER_LANCZOS4`) for downsampling

**Edge Case Handling**:
- If dimensions differ by >2x, warn user (likely indicates wrong magnification/zoom level)
- Preserve aspect ratio: if one image is non-square, pad others to match aspect

**Alternative Considered**:
- Resize to smallest: Avoids interpolation artifacts but loses high-res detail
- User choice: Adds UI complexity; most users lack expertise to choose appropriately

---

## 5. Memory Management for Large Images

**Question**: How to handle images approaching or exceeding RAM limits (4GB display threshold, potentially larger stitched outputs)?

**Decision**: Multi-tier strategy based on image size

### Tier 1: Small-Medium Images (<4GB total)
- Load fully into NumPy arrays
- Display at native resolution (scaled to viewport)
- Fast processing, no special handling

### Tier 2: Large Stitched Output (>4GB)
- Process at full resolution in memory (assuming sufficient RAM for processing)
- Save full-resolution TIFF to disk immediately after stitching
- Generate downsampled version for display (resize to fit 4000x4000 max using `cv2.resize`)
- Display downsampled version in result window with resolution indicator

### Tier 3: Input Images Exceeding RAM (Future Enhancement)
- Chunked processing using Dask arrays or zarr format
- Not implemented in Phase 1 (scope: images up to 4000x4000 per quadrant)

**Downsampling Algorithm**:
```python
def downsample_for_display(image, max_pixels=4000*4000):
    h, w = image.shape[:2]
    total_pixels = h * w
    if total_pixels <= max_pixels:
        return image  # No downsampling needed
    
    scale_factor = np.sqrt(max_pixels / total_pixels)
    new_h, new_w = int(h * scale_factor), int(w * scale_factor)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
```

**Rationale**:
- 16-bit grayscale image at 4000x4000 = 32MB per quadrant, 128MB for 4 quadrants - well within RAM
- Stitched output could be 8000x8000 = 128MB (16-bit) - still manageable
- Conservative 4GB threshold chosen to ensure UI responsiveness on 8GB RAM systems
- INTER_AREA interpolation best for downsampling (anti-aliasing, no artifacts)

---

## 6. Configuration File Format

**Question**: What format for saving/loading stitching parameters for reproducibility?

**Decision**: JSON with structured schema

**Rationale**:
- **Human-Readable**: Text format, easy to inspect/edit in text editor
- **Standard**: Native Python support via `json` module, no external deps
- **Version Control**: Plain text, git-friendly, diffable
- **Cross-Platform**: No platform-specific encoding issues
- **Scientific Standard**: Widely used in scientific workflows (config files, metadata)

**Schema Structure**:
```json
{
  "version": "1.0.0",
  "timestamp": "2025-11-04T10:30:45Z",
  "software": {
    "name": "Image MEA Dulce",
    "version": "0.1.0"
  },
  "source_files": [
    {
      "path": "/path/to/data_NE.czi",
      "quadrant": "NE",
      "original_dimensions": [2000, 2000],
      "file_size_bytes": 8000000,
      "md5_checksum": "abc123..."
    }
  ],
  "stitching_parameters": {
    "alignment_method": "feature-based",
    "blend_mode": "multiband",
    "overlap_threshold_percent": 10,
    "resize_strategy": "largest",
    "target_dimensions": [2000, 2000],
    "interpolation_method": "bicubic"
  },
  "output": {
    "stitched_file": "/path/to/output_stitched.tif",
    "full_resolution": [4000, 4000],
    "display_resolution": [4000, 4000],
    "processing_time_seconds": 45.3
  },
  "quality_metrics": {
    "alignment_confidence": 0.92,
    "overlap_ne_nw_percent": 15.2,
    "overlap_ne_se_percent": 12.8
  }
}
```

**Alternative Considered**:
- **YAML**: More readable for nested data, but requires PyYAML dependency
- **TOML**: Growing in Python ecosystem, but less universal than JSON
- **HDF5**: Binary format, excellent for large numeric data but overkill for config
- **Pickle**: Python-specific, not human-readable, security concerns

---

## 7. Keyword Detection Algorithm

**Question**: How to robustly extract spatial keywords from varied filename conventions?

**Decision**: Case-insensitive regex matching with priority order

**Algorithm**:
```python
import re
from enum import Enum

class Quadrant(Enum):
    NE = "NE"
    NW = "NW"
    SE = "SE"
    SW = "SW"

def detect_quadrant(filename: str) -> Quadrant | None:
    """
    Detect spatial quadrant from filename.
    Returns None if ambiguous or not detected (triggers manual assignment).
    """
    filename_upper = filename.upper()
    
    # Priority 1: Exact 2-letter abbreviations (most specific)
    exact_matches = {
        'NE': Quadrant.NE,
        'NW': Quadrant.NW,
        'SE': Quadrant.SE,
        'SW': Quadrant.SW
    }
    
    for pattern, quadrant in exact_matches.items():
        if re.search(rf'\b{pattern}\b', filename_upper):
            return quadrant
    
    # Priority 2: Full words
    word_matches = {
        'NORTHEAST': Quadrant.NE,
        'NORTHWEST': Quadrant.NW,
        'SOUTHEAST': Quadrant.SE,
        'SOUTHWEST': Quadrant.SW
    }
    
    for pattern, quadrant in word_matches.items():
        if pattern in filename_upper:
            return quadrant
    
    # Priority 3: Cardinal directions (only if unambiguous)
    # Check for N/S first, then E/W to determine quadrant
    has_north = re.search(r'\bNORTH\b', filename_upper) or re.search(r'\bN\b', filename_upper)
    has_south = re.search(r'\bSOUTH\b', filename_upper) or re.search(r'\bS\b', filename_upper)
    has_east = re.search(r'\bEAST\b', filename_upper) or re.search(r'\bE\b', filename_upper)
    has_west = re.search(r'\bWEST\b', filename_upper) or re.search(r'\bW\b', filename_upper)
    
    # Ambiguity checks
    if (has_north and has_south) or (has_east and has_west):
        return None  # Ambiguous - triggers manual assignment dialog
    
    # Unambiguous single directions
    if has_north and has_east:
        return Quadrant.NE
    if has_north and has_west:
        return Quadrant.NW
    if has_south and has_east:
        return Quadrant.SE
    if has_south and has_west:
        return Quadrant.SW
    
    # No clear quadrant detected
    return None
```

**Rationale**:
- **Word Boundaries**: `\b` ensures "NE" in "LINE" doesn't match
- **Priority Order**: More specific patterns checked first (NE before N+E)
- **Ambiguity Detection**: Multiple conflicting keywords return None, triggering user dialog
- **Case Insensitive**: Handles NORTH, North, north, NoRtH equally
- **Conservative**: When unsure, prompt user rather than guess incorrectly

---

## 8. Testing Strategy

**Question**: What testing approach ensures scientific validity and UI correctness?

**Decision**: Three-tier testing strategy

### Tier 1: Unit Tests (pytest)
**Coverage**:
- File I/O: Test loading .czi, .lsm, .tif with known dimensions/dtypes
- Keyword Detection: Test all combinations (exact, words, ambiguous, none)
- Dimension Handling: Test resize algorithms, aspect ratio preservation
- Config Manager: Test JSON serialization/deserialization round-trip

**Test Data**:
- Synthetic images: Small NumPy arrays (100x100) for fast tests
- Fixtures: Pre-generated test images with known properties

### Tier 2: Integration Tests (pytest-qt)
**Coverage**:
- GUI Workflow: Load images → display in quadrants → stitch → show result
- Dialog Interactions: Manual quadrant assignment, parameter adjustment
- Error Handling: Corrupted files, missing files, insufficient overlap

**Test Data**:
- Small real images: 200x200 microscopy crops for realistic testing

### Tier 3: Validation Testing (Manual)
**Coverage**:
- Real MEA data: Full-size .czi files from actual experiments
- Visual inspection: Verify no seams, alignment quality
- Performance: Measure load times, stitching duration, memory usage

**Test Data Source**:
- Use actual data from `raw_data/2025.10.22_opnT2/` and `raw_data/2025.10.23_opnT2/`
- Document expected outcomes in `specs/001-nsew-image-stitcher/test-data/README.md`

**Rationale**:
- **Automated Fast Tests**: Unit tests run in CI, provide rapid feedback
- **GUI Coverage**: pytest-qt enables automated GUI testing without manual clicking
- **Real-World Validation**: Manual testing with actual research data ensures scientific validity
- **No Regression**: Automated tests prevent breaking existing functionality

---

## 9. Progress Feedback Implementation

**Question**: How to provide responsive progress updates during long-running operations (loading, stitching)?

**Decision**: QThread + QProgressDialog with granular status messages

**Implementation Pattern**:
```python
class StitchingThread(QThread):
    progress_updated = pyqtSignal(int, str)  # (percentage, status_message)
    finished = pyqtSignal(object)  # StitchedResult
    error = pyqtSignal(str)
    
    def run(self):
        try:
            self.progress_updated.emit(0, "Loading images...")
            # ... load images ...
            
            self.progress_updated.emit(20, "Detecting features...")
            # ... feature detection ...
            
            self.progress_updated.emit(40, "Computing alignment...")
            # ... homography estimation ...
            
            self.progress_updated.emit(60, "Blending borders...")
            # ... multiband blending ...
            
            self.progress_updated.emit(80, "Finalizing output...")
            # ... save to disk, create result object ...
            
            self.progress_updated.emit(100, "Complete")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

# Usage in GUI
def on_stitch_clicked(self):
    self.progress_dialog = QProgressDialog("Stitching...", "Cancel", 0, 100, self)
    self.stitch_thread = StitchingThread(self.images, self.config)
    self.stitch_thread.progress_updated.connect(
        lambda pct, msg: (self.progress_dialog.setValue(pct), 
                          self.progress_dialog.setLabelText(msg))
    )
    self.stitch_thread.finished.connect(self.on_stitch_complete)
    self.stitch_thread.error.connect(self.on_stitch_error)
    self.stitch_thread.start()
```

**Rationale**:
- **Non-Blocking**: QThread keeps GUI responsive during processing
- **Granular Updates**: Specific status messages ("Detecting features...") more informative than generic "Processing..."
- **Cancellation**: QProgressDialog provides cancel button (honor in thread)
- **Error Handling**: Separate error signal ensures exceptions don't crash GUI

---

## 10. Error Handling Strategy

**Question**: How to gracefully handle errors (corrupted files, stitching failures) without crashing?

**Decision**: Try-catch at boundary layers with user-friendly messages

**Principles**:
- **Library Functions**: Raise specific exceptions (e.g., `CorruptedFileError`, `InsufficientOverlapError`)
- **GUI Layer**: Catch exceptions, show QMessageBox with actionable message
- **Partial Success**: Allow continuing after non-fatal errors (e.g., one corrupted file of four)

**Example**:
```python
# Library function
def load_image(filepath: str) -> np.ndarray:
    """Load image from file. Raises CorruptedFileError if unreadable."""
    try:
        if filepath.endswith('.czi'):
            return czifile.imread(filepath)
        elif filepath.endswith(('.tif', '.tiff', '.lsm')):
            return tifffile.imread(filepath)
    except Exception as e:
        raise CorruptedFileError(f"Cannot read {filepath}: {str(e)}")

# GUI handler
def load_files(self, filepaths: list[str]):
    loaded_images = []
    errors = []
    for path in filepaths:
        try:
            img = load_image(path)
            loaded_images.append(img)
        except CorruptedFileError as e:
            errors.append(str(e))
            # Continue loading other files
    
    if errors:
        QMessageBox.warning(self, "Some Files Failed", 
                           f"{len(errors)} file(s) could not be loaded:\n" + 
                           "\n".join(errors[:5]))  # Show first 5
    
    if loaded_images:
        self.display_images(loaded_images)
```

**Rationale**:
- **User-Friendly**: Error messages identify specific file and issue
- **Resilience**: System continues operating after recoverable errors
- **Debugging**: Specific exception types enable better logging/debugging
- **Scientific Integrity**: Errors logged to help users identify data quality issues

---

## Summary of Key Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| GUI Framework | PyQt6 | Mature, cross-platform, strong image handling |
| File I/O | czifile + tifffile | Format-specific libraries, NumPy integration |
| Stitching | OpenCV + custom extensions | Production-ready, configurable, performant |
| Dimension Normalization | Resize to largest | Preserves maximum detail |
| Memory Management | Downsample >4GB for display | Balances quality and responsiveness |
| Configuration | JSON with schema | Human-readable, standard, git-friendly |
| Keyword Detection | Regex with priority order | Robust, handles ambiguity |
| Testing | 3-tier (unit/integration/validation) | Fast automation + real-world validation |
| Progress Feedback | QThread + signals | Non-blocking, granular status |
| Error Handling | Try-catch with friendly messages | Resilient, user-focused |

**Next Phase**: Proceed to Phase 1 (Design) to create data model, API contracts, and quickstart guide.

