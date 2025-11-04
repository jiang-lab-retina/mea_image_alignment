# GUI Components Specification: NSEW Image Stitcher

**Phase**: 1 (Design)  
**Date**: 2025-11-04  
**Purpose**: Component specifications for PyQt6 GUI (src/gui/)

All GUI components follow PyQt6 conventions and connect to library functions (src/lib/) without embedding processing logic.

---

## Component: MainWindow

**Purpose**: Root application window containing 2x2 quadrant viewer grid and control buttons.

**Class**: `MainWindow(QMainWindow)`

**Layout**:
```
┌──────────────────────────────────────────────┐
│ File  Edit  View  Help                   │ Menu Bar
├──────────────────────────────────────────────┤
│ [Open Files...] [Stitch] [Save Config]   │ Toolbar
├──────────────────────────────────────────────┤
│ ┌──────────────┬──────────────┐             │
│ │  NW Viewer   │  NE Viewer   │             │
│ │   (empty)    │   (empty)    │             │
│ ├──────────────┼──────────────┤             │
│ │  SW Viewer   │  SE Viewer   │             │
│ │   (empty)    │   (empty)    │             │
│ └──────────────┴──────────────┘             │
├──────────────────────────────────────────────┤
│ Status: No files loaded                   │ Status Bar
└──────────────────────────────────────────────┘
```

**Signals**:
- `files_loaded` → emitted when images successfully loaded
- `stitch_requested` → emitted when user clicks Stitch button
- `config_saved` → emitted when configuration saved to disk

**Slots**:
- `on_open_files_clicked()` → Opens file picker dialog
- `on_stitch_clicked()` → Initiates stitching operation
- `on_save_config_clicked()` → Saves current configuration to JSON

**State**:
- `loaded_quadrants: dict[Quadrant, QuadrantImage]` → Currently loaded images (0-4 items)
- `stitching_config: StitchingConfig` → Current configuration
- `last_result: StitchedResult | None` → Most recent stitch result

**Behavior**:
- **File Loading**:
  1. User clicks "Open Files..." → QFileDialog appears
  2. User selects 1-4 files → `load_files()` called
  3. For each file:
     - Call `lib.io.load_image()`
     - Call `lib.keyword_detector.detect_quadrant()`
     - If quadrant detected → create QuadrantImage, display in viewer
     - If ambiguous/missing → show AssignmentDialog
     - If corrupted → show error message, continue with other files
  4. Update status bar: "Loaded X of Y files"
  5. Enable/disable Stitch button based on loaded count

- **Stitching**:
  1. User clicks "Stitch" → validate at least 1 image loaded
  2. Show StitchDialog to confirm/adjust parameters
  3. User confirms → create StitchingThread (QThread)
  4. Show QProgressDialog with cancel button
  5. Thread emits progress signals → update dialog
  6. Thread completes → show ResultWindow with stitched image
  7. Thread errors → show error QMessageBox

- **Configuration**:
  - User clicks "Save Config" → QFileDialog to choose location
  - Call `lib.config_manager.save_config(last_result)`
  - Show success message

**Keyboard Shortcuts**:
- `Ctrl+O`: Open files
- `Ctrl+S`: Save config
- `Ctrl+Return`: Stitch (if enabled)

**Test Cases**:
- Open 4 files with clear keywords → all display in correct positions
- Open file with ambiguous keyword → AssignmentDialog appears
- Click Stitch with 0 files → error message "No files loaded"
- Click Stitch with 2 files → proceeds (missing quadrants interpolated)

---

## Component: QuadrantViewer

**Purpose**: Display individual quadrant image with zoom/pan controls.

**Class**: `QuadrantViewer(QWidget)`

**Layout**:
```
┌──────────────────────┐
│ NW (Quadrant Label)  │ Header
├──────────────────────┤
│                      │
│    [Image Display]   │ QGraphicsView
│                      │
├──────────────────────┤
│ 2000x2000 | 8.3 MB   │ Footer (dimensions | file size)
└──────────────────────┘
```

**Properties**:
- `quadrant: Quadrant` → Spatial position (NE/NW/SE/SW)
- `image: QuadrantImage | None` → Loaded image data
- `zoom_level: float` → Current zoom (1.0 = 100%)

**Signals**:
- `zoom_changed(float)` → Emitted when zoom level changes
- `pan_changed(QPointF)` → Emitted when pan position changes

**Slots**:
- `set_image(image: QuadrantImage)` → Load and display image
- `clear()` → Remove image, show empty state
- `sync_zoom(zoom: float)` → Set zoom level (for synchronization)
- `sync_pan(pos: QPointF)` → Set pan position (for synchronization)

**Behavior**:
- **Image Display**:
  - Convert NumPy array to QPixmap using `QImage.fromData()`
  - Display in QGraphicsView for smooth zoom/pan
  - Show placeholder text "Empty" if no image loaded
  - Show label with quadrant position (NW/NE/SW/SE)

- **Zoom**:
  - Mouse wheel zooms in/out (Ctrl+Wheel for fine control)
  - Zoom range: 10% to 400%
  - Emit `zoom_changed` signal → MainWindow syncs other viewers

- **Pan**:
  - Click-and-drag to pan
  - Emit `pan_changed` signal → MainWindow syncs other viewers

- **Visual Indicators**:
  - Border: Green if image loaded, gray if empty
  - Footer shows dimensions and file size when loaded

**Test Cases**:
- set_image() with valid image → displays correctly
- Mouse wheel up → zoom increases, signal emitted
- Drag mouse → pan position changes, signal emitted
- sync_zoom(2.0) called externally → viewer zooms to 200%

---

## Component: AssignmentDialog

**Purpose**: Modal dialog for manually assigning quadrant position when auto-detection fails.

**Class**: `AssignmentDialog(QDialog)`

**Layout**:
```
┌──────────────────────────────────────────┐
│ Assign Quadrant Position                 │
├──────────────────────────────────────────┤
│ File: image_unknown.czi                  │
│                                          │
│ ┌────────────────────┐                  │
│ │  [Thumbnail]       │                  │
│ │   400x400          │                  │
│ └────────────────────┘                  │
│                                          │
│ Select quadrant position:                │
│ ○ Northwest (NW)                         │
│ ○ Northeast (NE)                         │
│ ○ Southwest (SW)                         │
│ ○ Southeast (SE)                         │
│                                          │
│        [Cancel]  [Assign]                │
└──────────────────────────────────────────┘
```

**Constructor**:
```python
def __init__(self, image_path: str, thumbnail: np.ndarray, parent=None):
    """
    Args:
        image_path: Path to image file (for display)
        thumbnail: Small version of image for preview (e.g., 400x400)
        parent: Parent widget
    """
```

**Return Value**:
- `exec_() -> Quadrant | None` → Selected quadrant or None if cancelled

**Behavior**:
- Display filename and thumbnail preview
- Radio buttons for 4 quadrant choices
- "Assign" button enabled only when radio selected
- "Cancel" returns None
- "Assign" returns selected Quadrant enum value

**Test Cases**:
- Select NW, click Assign → returns Quadrant.NW
- Click Cancel → returns None
- Click Assign without selection → disabled (not clickable)

---

## Component: StitchDialog

**Purpose**: Configuration dialog for adjusting stitching parameters before execution.

**Class**: `StitchDialog(QDialog)`

**Layout**:
```
┌──────────────────────────────────────────┐
│ Stitching Parameters                     │
├──────────────────────────────────────────┤
│ Blend Mode:                              │
│   [Multiband ▼]   (dropdown)            │
│   ℹ️ Multiband blending provides...     │
│                                          │
│ Overlap Threshold: [====●====] 10%      │
│   (slider 5-50%)                         │
│                                          │
│ Alignment Method:                        │
│   [Feature-based ▼]                     │
│                                          │
│ Output Format:                           │
│   [TIFF ▼]   Compression: [==●=] 6      │
│                                          │
│        [Cancel]  [Start Stitching]       │
└──────────────────────────────────────────┘
```

**Constructor**:
```python
def __init__(self, current_config: StitchingConfig, parent=None):
    """
    Args:
        current_config: Current stitching configuration (provides defaults)
        parent: Parent widget
    """
```

**Return Value**:
- `exec_() -> StitchingConfig | None` → Updated config or None if cancelled

**Behavior**:
- Load current configuration values into UI controls
- Each control has tooltip with scientific explanation
- "Start Stitching" validates inputs and returns updated StitchingConfig
- "Cancel" returns None (uses original config)

**Validation**:
- Overlap threshold: 5% ≤ value ≤ 50%
- Compression level: 0 ≤ value ≤ 9

**Test Cases**:
- Adjust overlap to 15%, click Start → returns config with overlap_threshold_percent=15.0
- Set invalid value → error message, cannot proceed
- Click Cancel → returns None

---

## Component: ResultWindow

**Purpose**: Display stitched image result with quality metrics.

**Class**: `ResultWindow(QWidget)`

**Layout**:
```
┌──────────────────────────────────────────┐
│ Stitched Result                          │
├──────────────────────────────────────────┤
│ ┌────────────────────────────────────┐   │
│ │                                    │   │
│ │     [Stitched Image Display]       │   │
│ │                                    │   │
│ └────────────────────────────────────┘   │
│                                          │
│ Quality Metrics:                         │
│   Overall Confidence: 0.89 (89%)         │
│   Alignment: NE-NW: 0.92  NE-SE: 0.87    │
│   Overlap: NE-NW: 15.2%  NE-SE: 12.8%    │
│   Processing Time: 45.3 seconds          │
│                                          │
│ Display: 4000x4000 | Saved: 4000x4000    │
│                                          │
│        [Save As...]  [Close]             │
└──────────────────────────────────────────┘
```

**Constructor**:
```python
def __init__(self, result: StitchedResult, parent=None):
    """
    Args:
        result: Stitching result with image and metrics
        parent: Parent widget
    """
```

**Behavior**:
- Display stitched image (downsampled version if was_downsampled==True)
- Show quality metrics from result.quality_metrics
- Display resolution information (display vs. saved)
- If downsampled, show info icon with message: "Full resolution saved to disk"
- "Save As..." allows user to save to different location/format
- "Close" closes window

**Visual Feedback**:
- High confidence (>0.8): Green checkmark icon
- Medium confidence (0.6-0.8): Yellow warning icon
- Low confidence (<0.6): Red error icon

**Test Cases**:
- Result with high confidence → green checkmark shown
- Downsampled result → info message about full resolution
- Click Save As → QFileDialog appears

---

## Component: StitchingThread

**Purpose**: Background thread for non-blocking stitching operation.

**Class**: `StitchingThread(QThread)`

**Signals**:
- `progress_updated(int, str)` → (percentage [0-100], status message)
- `finished(StitchedResult)` → Stitching completed successfully
- `error(str)` → Stitching failed with error message

**Constructor**:
```python
def __init__(self, quadrants: list[QuadrantImage], config: StitchingConfig):
    """
    Args:
        quadrants: List of loaded images to stitch
        config: Stitching configuration
    """
```

**Behavior**:
- Override `run()` method to perform stitching
- Emit progress updates at key stages:
  - 0%: "Loading images..."
  - 20%: "Normalizing dimensions..."
  - 40%: "Detecting features..."
  - 60%: "Computing alignment..."
  - 80%: "Blending borders..."
  - 100%: "Complete"
- Call `lib.stitching.stitch_quadrants()`
- Emit `finished` with result on success
- Emit `error` with message on exception

**Thread Safety**:
- All OpenCV and NumPy operations are thread-safe
- No GUI updates in thread (only emit signals)

---

## Inter-Component Communication

### MainWindow ↔ QuadrantViewer (Zoom/Pan Synchronization)

```python
# In MainWindow.__init__():
for viewer in self.quadrant_viewers:
    viewer.zoom_changed.connect(self.sync_zoom_to_all)
    viewer.pan_changed.connect(self.sync_pan_to_all)

def sync_zoom_to_all(self, zoom: float):
    """When one viewer zooms, update all others."""
    sender_viewer = self.sender()
    for viewer in self.quadrant_viewers:
        if viewer != sender_viewer:
            viewer.sync_zoom(zoom)
```

### MainWindow → AssignmentDialog (Manual Assignment)

```python
def handle_ambiguous_file(self, file_path: str, thumbnail: np.ndarray):
    dialog = AssignmentDialog(file_path, thumbnail, parent=self)
    result = dialog.exec_()
    if result:  # User selected quadrant
        quadrant = result
        # Create QuadrantImage with assigned quadrant
```

### MainWindow → StitchingThread (Background Processing)

```python
def on_stitch_clicked(self):
    dialog = StitchDialog(self.stitching_config, parent=self)
    config = dialog.exec_()
    if config:
        self.stitch_thread = StitchingThread(
            list(self.loaded_quadrants.values()), 
            config
        )
        self.progress_dialog = QProgressDialog("Stitching...", "Cancel", 0, 100, self)
        self.stitch_thread.progress_updated.connect(self.on_progress_update)
        self.stitch_thread.finished.connect(self.on_stitch_finished)
        self.stitch_thread.error.connect(self.on_stitch_error)
        self.stitch_thread.start()
```

---

## Styling & Theme

**Color Palette**:
- Primary: #2196F3 (Blue) - buttons, active elements
- Success: #4CAF50 (Green) - loaded images, high confidence
- Warning: #FF9800 (Orange) - medium confidence
- Error: #F44336 (Red) - errors, low confidence
- Background: #FAFAFA (Light gray)
- Text: #212121 (Dark gray)

**Typography**:
- Headers: 14pt Bold
- Body: 10pt Regular
- Status: 9pt Italic

**Icons**: Use QIcon from system theme or bundled Material Design Icons

---

## Accessibility

- **Keyboard Navigation**: All dialogs fully keyboard-navigable (Tab/Shift+Tab)
- **Tooltips**: Every control has informative tooltip
- **High Contrast**: Support system high-contrast themes
- **Screen Reader**: Labels properly associated with controls

---

## Error Handling in GUI

**Pattern**:
```python
def some_gui_action(self):
    try:
        result = lib.some_function()
        # Success: update UI
    except lib.CorruptedFileError as e:
        QMessageBox.warning(self, "File Error", str(e))
    except lib.InsufficientOverlapError as e:
        QMessageBox.critical(self, "Stitching Failed", 
            f"{str(e)}\n\nTry adjusting overlap threshold or check image alignment.")
    except Exception as e:
        QMessageBox.critical(self, "Unexpected Error",
            f"An unexpected error occurred:\n{str(e)}\n\nPlease report this issue.")
        logging.exception("Unexpected error in some_gui_action")
```

**Principles**:
- Specific exceptions → informative messages with actionable guidance
- Generic exceptions → logged with stack trace, show basic user message
- Never crash GUI → always catch at top level
- Partial success → allow continuing (e.g., 3 of 4 files loaded)

---

## Performance Requirements

| Operation | Max Time | Notes |
|-----------|----------|-------|
| File loading | 2 sec | Per file, progress shown if >0.5 sec |
| Display update | 100 ms | Image rendering in viewer |
| Dialog opening | 50 ms | Any modal dialog |
| Zoom/pan | 16 ms | 60 FPS target |
| Stitching | 60 sec | Background thread, progress updates |

These requirements ensure constitution Performance Standards compliance (responsive UI, progress feedback).

