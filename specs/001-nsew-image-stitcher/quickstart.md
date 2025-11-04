# Quickstart Guide: NSEW Image Stitcher

**Phase**: 1 (Design)  
**Date**: 2025-11-04  
**Purpose**: Quick reference for developers and future code generation

This guide provides the essential information needed to implement the NSEW Image Stitcher feature.

---

## Feature Overview

**What**: GUI application for loading, visualizing, and stitching Multi-Electrode Array (MEA) microscopy images arranged in spatial quadrants (N/S/E/W).

**Why**: Researchers need to combine multiple microscopy image captures into seamless panoramas for analysis and publication while maintaining data integrity and reproducibility.

**Key Capabilities**:
- Load 1-4 images in .czi, .lsm, or .tif/.tiff formats
- Auto-detect spatial position from filename keywords (NE, NW, SE, SW)
- Display in synchronized 2x2 quadrant layout with zoom/pan
- Stitch images with configurable parameters
- Handle dimension mismatches, missing quadrants, and large outputs
- Save full stitching configuration for reproducibility

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.10+ | Core development language |
| **GUI Framework** | PyQt6 | Cross-platform desktop UI |
| **Image Processing** | NumPy + OpenCV | Array operations and stitching algorithms |
| **File I/O** | czifile, tifffile, Pillow | Read microscopy formats |
| **Testing** | pytest, pytest-qt | Unit and integration testing |
| **Config** | JSON (stdlib) | Parameter serialization |

**Dependencies** (requirements.txt):
```
PyQt6>=6.6.0
numpy>=1.24.0
opencv-python>=4.8.0
czifile>=2019.7.2
tifffile>=2023.7.10
Pillow>=10.0.0
pytest>=7.4.0
pytest-qt>=4.2.0
```

---

## Project Structure (Quick Reference)

```
src/
├── models/          # Data entities (QuadrantImage, StitchingConfig, StitchedResult)
├── lib/             # Core processing (I/O, stitching, dimension handling)
└── gui/             # PyQt6 UI components (MainWindow, dialogs, viewers)

tests/
├── unit/            # Fast isolated tests
└── integration/     # GUI workflow tests

specs/001-nsew-image-stitcher/
├── spec.md          # Requirements and user stories
├── plan.md          # This implementation plan
├── research.md      # Technology decisions
├── data-model.md    # Entity definitions
├── contracts/       # API specifications
└── quickstart.md    # This file
```

---

## Key Files to Implement

### Phase 1: Core Library (src/lib/)

**Priority Order**:

1. **models/quadrant_image.py** → QuadrantImage dataclass
   - Fields: file_path, quadrant, dimensions, dtype, image_data, metadata
   - Enum: Quadrant (NE, NW, SE, SW)

2. **lib/io.py** → File loading/saving
   - `load_image(file_path) -> (np.ndarray, ImageMetadata)`
   - `save_image(image_data, output_path, format, compression)`

3. **lib/keyword_detector.py** → Spatial keyword extraction
   - `detect_quadrant(filename) -> Quadrant | None`

4. **lib/dimension_handler.py** → Dimension normalization
   - `normalize_dimensions(images, strategy, interpolation)`
   - `downsample_for_display(image, max_dimension)`

5. **lib/stitching.py** → Core stitching algorithm
   - `stitch_quadrants(quadrants, config) -> StitchedResult`

6. **lib/config_manager.py** → Configuration persistence
   - `save_config(result, output_path)`
   - `load_config(config_path) -> StitchingConfig`

### Phase 2: GUI (src/gui/)

**Priority Order**:

1. **gui/quadrant_viewer.py** → Individual image display widget
   - QGraphicsView-based with zoom/pan
   - Sync signals for coordinated viewing

2. **gui/main_window.py** → Root application window
   - 2x2 grid of QuadrantViewers
   - File loading, stitching initiation
   - State management for loaded images

3. **gui/assignment_dialog.py** → Manual quadrant assignment
   - Modal dialog with thumbnail + radio buttons

4. **gui/stitch_dialog.py** → Parameter configuration
   - Blend mode, overlap threshold, output format

5. **gui/result_window.py** → Stitched image display
   - Show result with quality metrics
   - Save As functionality

6. **gui/stitching_thread.py** → Background processing
   - QThread for non-blocking stitch operation
   - Progress signals

7. **main.py** → Application entry point

### Phase 3: Tests

**Priority Order**:

1. **tests/unit/test_io.py** → File loading tests
2. **tests/unit/test_keyword_detector.py** → Keyword detection tests
3. **tests/unit/test_stitching.py** → Stitching algorithm tests (with small synthetic images)
4. **tests/integration/test_gui_workflow.py** → End-to-end GUI tests

---

## Implementation Roadmap

### Milestone 1: File Loading & Display (Week 1)
- ✅ Implement QuadrantImage model
- ✅ Implement load_image() for .czi, .lsm, .tif
- ✅ Implement detect_quadrant()
- ✅ Create QuadrantViewer widget
- ✅ Create MainWindow with 4 viewers
- ✅ Test: Load 4 files, display in correct positions

### Milestone 2: Stitching Core (Week 2)
- ✅ Implement normalize_dimensions()
- ✅ Implement stitch_quadrants() (OpenCV integration)
- ✅ Handle missing quadrants (interpolation logic)
- ✅ Compute quality metrics
- ✅ Test: Stitch 4 images, verify output

### Milestone 3: Configuration & Persistence (Week 3)
- ✅ Implement StitchingConfig model
- ✅ Implement StitchedResult model
- ✅ Implement save_config() / load_config()
- ✅ Create StitchDialog for parameter adjustment
- ✅ Test: Save/load config round-trip

### Milestone 4: Full GUI Integration (Week 4)
- ✅ Implement StitchingThread
- ✅ Add progress dialog
- ✅ Create ResultWindow
- ✅ Create AssignmentDialog
- ✅ Implement synchronized zoom/pan
- ✅ Test: Complete end-to-end workflow

### Milestone 5: Polish & Edge Cases (Week 5)
- ✅ Implement downsample_for_display()
- ✅ Handle corrupted files gracefully
- ✅ Add error messages and validation
- ✅ Implement save_image()
- ✅ Test: All edge cases from spec

### Milestone 6: Documentation & Validation (Week 6)
- ✅ Write README with installation instructions
- ✅ Test with real MEA data from raw_data/
- ✅ Performance validation (load times, memory usage)
- ✅ User acceptance testing
- ✅ Create package (setup.py)

---

## Critical Implementation Details

### 1. Keyword Detection Algorithm

```python
def detect_quadrant(filename: str) -> Quadrant | None:
    """Priority: Exact 2-letter > Full words > Cardinals"""
    filename_upper = filename.upper()
    
    # Priority 1: NE, NW, SE, SW
    if re.search(r'\bNE\b', filename_upper):
        return Quadrant.NE
    # ... (see research.md for full algorithm)
    
    # Priority 2: Northeast, Northwest, etc.
    if 'NORTHEAST' in filename_upper:
        return Quadrant.NE
    
    # Priority 3: N+E, N+W, etc. (with ambiguity check)
    has_north = 'NORTH' in filename_upper or re.search(r'\bN\b', filename_upper)
    # ... check for conflicts, return None if ambiguous
```

### 2. Stitching with Missing Quadrants

```python
def stitch_quadrants(quadrants, config):
    # Fill missing positions
    all_positions = {Quadrant.NE, Quadrant.NW, Quadrant.SE, Quadrant.SW}
    loaded_positions = {q.quadrant for q in quadrants}
    missing = all_positions - loaded_positions
    
    if missing:
        # Create placeholder images
        avg_dims = compute_average_dimensions(quadrants)
        for pos in missing:
            placeholder = create_placeholder(avg_dims, config.missing_quadrant_fill)
            quadrants.append(QuadrantImage(quadrant=pos, image_data=placeholder))
    
    # Proceed with full 4-quadrant stitch
    return opencv_stitch(quadrants, config)
```

### 3. Downsampling for Large Results

```python
def downsample_for_display(image, max_dimension=4000):
    h, w = image.shape[:2]
    if h <= max_dimension and w <= max_dimension:
        return image  # No downsampling needed
    
    # Scale to fit max_dimension
    scale = min(max_dimension / h, max_dimension / w)
    new_h, new_w = int(h * scale), int(w * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
```

### 4. Thread-Safe Progress Updates

```python
class StitchingThread(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    
    def run(self):
        self.progress_updated.emit(0, "Loading images...")
        images = load_and_normalize(self.quadrants)
        
        self.progress_updated.emit(40, "Detecting features...")
        features = detect_features(images)
        
        self.progress_updated.emit(80, "Blending...")
        result = blend_and_finalize(features)
        
        self.finished.emit(result)
```

---

## Testing Strategy

### Unit Tests (Fast, Isolated)

```python
# tests/unit/test_keyword_detector.py
def test_detect_exact_match():
    assert detect_quadrant("data_NE.czi") == Quadrant.NE

def test_detect_ambiguous():
    assert detect_quadrant("North_South.czi") is None
```

### Integration Tests (GUI Workflows)

```python
# tests/integration/test_gui_workflow.py
def test_load_and_stitch(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Simulate file selection
    files = ["test_NE.tif", "test_NW.tif", "test_SE.tif", "test_SW.tif"]
    window.load_files(files)
    
    # Verify all loaded
    assert len(window.loaded_quadrants) == 4
    
    # Trigger stitch
    qtbot.mouseClick(window.stitch_button, Qt.LeftButton)
    
    # Wait for completion (use qtbot.waitSignal)
    qtbot.waitSignal(window.stitch_thread.finished, timeout=30000)
    
    # Verify result window opened
    assert window.result_window is not None
```

### Validation Tests (Real Data)

- Use actual .czi files from `raw_data/2025.10.22_opnT2/`
- Manually inspect stitched output for seams/misalignments
- Measure load times, memory usage, processing duration
- Compare quality metrics to expected ranges

---

## Common Pitfalls to Avoid

1. **NumPy Array Copying**:
   - Use `image.copy()` before modifying to avoid aliasing bugs
   - OpenCV may return views, not copies

2. **PyQt Thread Safety**:
   - Never call GUI methods from QThread.run()
   - Always use signals to communicate with main thread

3. **File Path Handling**:
   - Use `pathlib.Path` for cross-platform compatibility
   - Always use absolute paths in QuadrantImage

4. **Dtype Mismatches**:
   - Validate all images have same dtype before stitching
   - Convert uint8 ↔ uint16 explicitly if needed

5. **Memory Management**:
   - Delete large NumPy arrays explicitly when done: `del image_data`
   - Use garbage collection hints for large stitching operations

---

## Performance Targets (Constitution Compliance)

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| Load 4x(2000x2000) images | <15 sec | TBD | ⏳ |
| Stitch 4 images | <60 sec | TBD | ⏳ |
| Memory usage | <4GB | TBD | ⏳ |
| UI responsiveness | <100ms | TBD | ⏳ |
| Progress updates | Every 2 sec | TBD | ⏳ |

Measure during Milestone 6 validation phase.

---

## Debugging Tips

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Profile Stitching Performance

```python
import cProfile
cProfile.run('stitch_quadrants(quadrants, config)', 'stitch_profile.prof')
```

### Visualize Feature Matches

```python
# In lib/stitching.py
def debug_draw_matches(img1, img2, kp1, kp2, matches):
    match_img = cv2.drawMatches(img1, kp1, img2, kp2, matches[:50], None)
    cv2.imwrite('debug_matches.png', match_img)
```

---

## Next Steps After Phase 1 (Design)

1. **Run `/speckit.tasks`** → Generate detailed task list
2. **Begin implementation** → Start with Milestone 1 (File Loading & Display)
3. **Iterate with tests** → Write tests first (TDD), then implement
4. **Validate with real data** → Use actual MEA microscopy files
5. **Package for distribution** → Create standalone executable (PyInstaller)

---

## Resources

- **PyQt6 Documentation**: https://doc.qt.io/qtforpython-6/
- **OpenCV Stitching Tutorial**: https://docs.opencv.org/4.x/d8/d19/tutorial_stitcher.html
- **czifile Documentation**: https://pypi.org/project/czifile/
- **tifffile Documentation**: https://pypi.org/project/tifffile/
- **Project Constitution**: `/.specify/memory/constitution.md`
- **Feature Specification**: `specs/001-nsew-image-stitcher/spec.md`

---

**Status**: Design Complete ✅ | Ready for task generation and implementation

