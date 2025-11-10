# Quickstart: Chip Image Stitching Implementation

**Feature**: 002-chip-image-stitch  
**For**: Developers implementing this feature  
**Last Updated**: 2025-11-05

## TL;DR

Add a "Stitch Chip Images" button that reuses alignment parameters from the first stitching to stitch a second set of "chip" images without re-computing expensive feature detection.

**Key Files to Create/Modify**:
- ✅ `src/models/alignment_parameters.py` - NEW
- ✅ `src/lib/alignment_manager.py` - NEW
- ✅ `src/lib/chip_image_finder.py` - NEW
- ✅ `src/lib/chip_stitcher.py` - NEW
- ⚠️ `src/models/stitched_result.py` - EXTEND
- ⚠️ `src/lib/stitching.py` - EXTEND
- ⚠️ `src/gui/main_window.py` - EXTEND
- ⚠️ `src/gui/result_window.py` - EXTEND
- ✅ `src/gui/dimension_preview_dialog.py` - NEW

---

## Tech Stack

**Core** (from 001-nsew-image-stitcher):
- Python 3.10+
- PyQt6 (GUI)
- NumPy (arrays)
- OpenCV (stitching)
- czifile, tifffile, Pillow (image I/O)

**New Dependencies**:
- None - all functionality uses existing dependencies

---

## Architecture Overview

```
┌─────────────────────────────────────────┐
│ MainWindow (GUI)                        │
│  ├─ "Stitch Chip Images" button         │
│  │   └─ enabled when params available   │
│  └─ State: self.alignment_parameters    │
└─────────────────────────────────────────┘
        │
        │ on_chip_stitch_clicked()
        │
        v
┌─────────────────────────────────────────┐
│ chip_image_finder.find_chip_images()    │
│  ├─ Discovers chip files by pattern     │
│  ├─ Checks dimensions                   │
│  └─ Returns: ChipImageSet               │
└─────────────────────────────────────────┘
        │
        │ if dimension_mismatches
        │
        v
┌─────────────────────────────────────────┐
│ DimensionPreviewDialog (GUI)            │
│  ├─ Shows resize operations              │
│  ├─ Proceed / Cancel buttons            │
│  └─ Returns: user_choice                │
└─────────────────────────────────────────┘
        │
        │ if user proceeds
        │
        v
┌─────────────────────────────────────────┐
│ chip_stitcher.stitch_chip_images()      │
│  ├─ Loads/resizes chip images           │
│  ├─ Generates placeholders              │
│  ├─ Applies position shifts             │
│  └─ Returns: StitchedResult             │
└─────────────────────────────────────────┘
        │
        v
┌─────────────────────────────────────────┐
│ ResultWindow (GUI)                      │
│  ├─ Displays stitched chip image        │
│  └─ Shows chip metadata                 │
└─────────────────────────────────────────┘
```

---

## Data Flow

### Original Stitching (Captures Parameters)

```
User clicks "Stitch Images"
    │
    v
stitch_quadrants(quadrant_images, config)
    │
    ├─ Performs OpenCV stitching
    ├─ Captures position shifts: [dx_NE, dy_NE, dx_NW, dy_NW, ...]
    └─ Returns: StitchedResult with alignment_parameters
    │
    v
User saves result (or automatic)
    │
    ├─ Save stitched image: "result.tiff"
    └─ Save alignment params: "result_alignment.json"
```

### Chip Stitching (Reuses Parameters)

```
User clicks "Stitch Chip Images"
    │
    v
load_alignment_params("result_alignment.json")
    │
    ├─ Parse JSON
    ├─ Validate (format, completeness, existence)
    └─ Returns: AlignmentParameters
    │
    v
find_chip_images(alignment_params)
    │
    ├─ For each quadrant: generate_chip_filename()
    ├─ Check if chip files exist
    ├─ Check dimensions
    └─ Returns: ChipImageSet
    │
    v
[If dimension mismatches] Show DimensionPreviewDialog
    │
    ├─ User sees resize operations
    └─ User chooses: Proceed / Cancel
    │
    v
stitch_chip_images(chip_image_set, alignment_params, config)
    │
    ├─ Load chip images (or placeholders)
    ├─ Resize to match original dimensions
    ├─ Apply position shifts (NO feature detection)
    ├─ Blend images
    └─ Returns: StitchedResult with chip_metadata
    │
    v
Display result in ResultWindow
```

---

## Implementation Phases

### Phase 1: Core Data Models ✓

**Tasks**:
1. Create `src/models/alignment_parameters.py`
   - Define `AlignmentParameters` dataclass
   - Define `QuadrantAlignment` nested dataclass
   - Add JSON serialization helpers

2. Extend `src/models/stitched_result.py`
   - Add `alignment_parameters: Optional[AlignmentParameters]`
   - Add `is_chip_stitch: bool`
   - Add `chip_metadata: Optional[ChipStitchMetadata]`

3. Create `src/models/chip_image_set.py`
   - Define `ChipImageSet` dataclass
   - Define `DimensionMismatch` nested dataclass

**Validation**: Unit tests for serialization/deserialization

---

### Phase 2: Parameter Persistence ✓

**Tasks**:
1. Create `src/lib/alignment_manager.py`
   - `save_alignment_params(params, path)` - JSON write
   - `load_alignment_params(path)` - JSON read
   - `validate_alignment_params(params)` - 3-layer validation

2. Extend `src/lib/stitching.py`
   - Modify `stitch_quadrants()` to capture position shifts
   - Populate `result.alignment_parameters` before return

**Validation**: 
- Unit tests for save/load round-trip
- Unit tests for each validation layer
- Integration test: stitch → save → load → validate

---

### Phase 3: Chip Discovery ✓

**Tasks**:
1. Create `src/lib/chip_image_finder.py`
   - `generate_chip_filename(original_path)` - filename pattern
   - `find_chip_images(alignment_params)` - directory search
   - Dimension checking logic

**Validation**:
- Unit tests with test files
- Edge cases: missing chips, dimension mismatches, different extensions

---

### Phase 4: Chip Stitching ✓

**Tasks**:
1. Create `src/lib/chip_stitcher.py`
   - `generate_placeholder_image(width, height)` - black placeholder
   - `stitch_chip_images(chip_set, params, config)` - main stitcher
   - Progress callback integration

2. Implement alignment reuse
   - Apply position shifts without feature detection
   - Dimension normalization (resize)
   - Placeholder generation

**Validation**:
- Unit tests for placeholder generation
- Unit tests for dimension normalization
- Integration test: full chip stitching workflow with mixed present/missing chips

---

### Phase 5: GUI Integration ✓

**Tasks**:
1. Extend `src/gui/main_window.py`
   - Add "Stitch Chip Images" button to toolbar
   - Add `self.alignment_parameters` state variable
   - Add button enablement logic
   - Add `on_chip_stitch_clicked()` handler
   - Auto-load parameters on startup if found

2. Create `src/gui/dimension_preview_dialog.py`
   - Table showing resize operations
   - Proceed / Cancel buttons
   - Clear visual layout

3. Extend `src/gui/result_window.py`
   - Display chip metadata section
   - Show: chip images found, placeholders used, dimension transformations

**Validation**:
- GUI testing with pytest-qt
- Manual testing of complete workflows

---

## Key Code Snippets

### Capture Alignment Parameters (in `stitch_quadrants`)

```python
# After OpenCV stitching completes, capture position shifts
def stitch_quadrants(quadrant_images, config):
    # ... existing stitching logic ...
    
    # NEW: Capture alignment parameters
    alignment_params = AlignmentParameters(
        version="1.0",
        timestamp=datetime.now().isoformat(),
        stitched_image_path=output_path,
        quadrants=[
            QuadrantAlignment(
                quadrant=qi.quadrant,
                original_image_path=qi.file_path,
                dimensions=(qi.image_data.shape[1], qi.image_data.shape[0]),
                position_shift=position_shifts[qi.quadrant]  # Captured from stitcher
            )
            for qi in quadrant_images
        ]
    )
    
    # Populate result
    result = StitchedResult(...)
    result.alignment_parameters = alignment_params
    
    return result
```

### Generate Chip Filename

```python
def generate_chip_filename(original_path: Path) -> str:
    stem = original_path.stem  # "sample_NE"
    ext = original_path.suffix  # ".czi"
    
    # Find quadrant at end
    for quadrant in ["NE", "NW", "SE", "SW"]:
        if stem.endswith(quadrant):
            # Insert "chip" before quadrant
            prefix = stem[:-len(quadrant)]  # "sample_"
            return f"{prefix}chip{quadrant}{ext}"  # "sample_chipNE.czi"
    
    raise ValueError(f"No quadrant identifier in {original_path.name}")
```

### Find Chip Images

```python
def find_chip_images(alignment_params: AlignmentParameters) -> ChipImageSet:
    chip_images = {}
    missing_quadrants = []
    dimension_mismatches = []
    
    for qa in alignment_params.quadrants:
        original_dir = qa.original_image_path.parent
        chip_filename = generate_chip_filename(qa.original_image_path)
        chip_path = original_dir / chip_filename
        
        if chip_path.exists():
            # Load and check dimensions
            chip_data = load_image(chip_path)
            chip_dims = (chip_data.shape[1], chip_data.shape[0])
            
            if chip_dims != qa.dimensions:
                dimension_mismatches.append(
                    DimensionMismatch(
                        quadrant=qa.quadrant,
                        chip_image_path=chip_path,
                        original_dimensions=chip_dims,
                        target_dimensions=qa.dimensions
                    )
                )
            
            chip_images[qa.quadrant] = chip_path
        else:
            missing_quadrants.append(qa.quadrant)
            chip_images[qa.quadrant] = None
    
    return ChipImageSet(
        alignment_params=alignment_params,
        chip_images=chip_images,
        missing_quadrants=missing_quadrants,
        dimension_mismatches=dimension_mismatches
    )
```

### Apply Position Shifts (No Feature Detection)

```python
def stitch_chip_images(chip_set, alignment_params, config):
    # Load/resize/placeholder chips
    processed_chips = {}
    
    for qa in alignment_params.quadrants:
        chip_path = chip_set.chip_images[qa.quadrant]
        
        if chip_path:
            # Load and resize
            chip_data = load_image(chip_path)
            resized = cv2.resize(chip_data, qa.dimensions, interpolation=cv2.INTER_LANCZOS4)
            processed_chips[qa.quadrant] = resized
        else:
            # Generate placeholder
            h, w = qa.dimensions[1], qa.dimensions[0]
            processed_chips[qa.quadrant] = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Apply position shifts (NO FEATURE DETECTION)
    canvas = np.zeros((final_height, final_width, 3), dtype=np.uint8)
    
    for qa in alignment_params.quadrants:
        chip = processed_chips[qa.quadrant]
        dx, dy = qa.position_shift
        
        # Apply affine transformation with stored shifts
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        transformed = cv2.warpAffine(chip, M, (final_width, final_height))
        
        # Blend into canvas
        canvas = blend_images(canvas, transformed, config.blend_mode)
    
    return StitchedResult(
        image_data=canvas,
        is_chip_stitch=True,
        chip_metadata=ChipStitchMetadata(...)
    )
```

### GUI Button State Management

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.alignment_parameters = None
        
        # Create button (initially disabled)
        self.chip_stitch_action = QAction("Stitch Chip Images", self)
        self.chip_stitch_action.setEnabled(False)
        self.chip_stitch_action.triggered.connect(self.on_chip_stitch_clicked)
        
        # Auto-load parameters if found
        self.load_saved_alignment_params()
    
    def load_saved_alignment_params(self):
        # Search for *_alignment.json in current directory
        param_files = list(Path.cwd().glob("*_alignment.json"))
        if param_files:
            try:
                params = load_alignment_params(param_files[0])
                validation = validate_alignment_params(params)
                if validation.is_valid:
                    self.alignment_parameters = params
                    self.chip_stitch_action.setEnabled(True)
            except Exception as e:
                logger.error(f"Failed to load alignment params: {e}")
    
    def on_original_stitch_complete(self, result: StitchedResult):
        # Store parameters from original stitching
        if result.alignment_parameters:
            self.alignment_parameters = result.alignment_parameters
            self.chip_stitch_action.setEnabled(True)
            
            # Auto-save parameters
            param_file = result.output_path.parent / f"{result.output_path.stem}_alignment.json"
            save_alignment_params(result.alignment_parameters, param_file)
    
    def on_new_images_loaded(self):
        # Disable button when new images loaded
        self.alignment_parameters = None
        self.chip_stitch_action.setEnabled(False)
```

---

## Testing Strategy

### Unit Tests

**Alignment Parameters**:
- ✅ Serialization: dataclass → dict → JSON
- ✅ Deserialization: JSON → dict → dataclass
- ✅ Round-trip: params → save → load → equal
- ✅ Validation layer 1 (format)
- ✅ Validation layer 2 (completeness)
- ✅ Validation layer 3 (existence)

**Chip Image Finder**:
- ✅ `generate_chip_filename()` with various patterns
- ✅ `find_chip_images()` with all chips present
- ✅ `find_chip_images()` with some chips missing
- ✅ `find_chip_images()` with dimension mismatches

**Chip Stitcher**:
- ✅ `generate_placeholder_image()` with various sizes
- ✅ Dimension normalization/resizing
- ✅ Position shift application

### Integration Tests

- ✅ Full workflow: original stitch → save params → load params → chip stitch
- ✅ Cross-session: parameters saved in one session, loaded in another
- ✅ Error recovery: corrupted parameter file, missing chips, dimension mismatches

### GUI Tests (pytest-qt)

- ✅ Button state management
- ✅ DimensionPreviewDialog accept/reject
- ✅ Result window chip metadata display

---

## Performance Targets

From success criteria in spec.md:

- ✅ **File Discovery**: <2 seconds for directories with up to 100 files
- ✅ **Chip Stitching**: 50% faster than original (bypassing feature detection)
- ✅ **Parameter Validation**: <500ms
- ✅ **Pixel-Perfect Alignment**: ±0 pixels compared to original

---

## Common Pitfalls

❌ **Don't**: Run feature detection again for chip images
✅ **Do**: Apply stored position shifts directly

❌ **Don't**: Match any dimension - position shifts are pixel-based
✅ **Do**: Resize chips to original dimensions before applying shifts

❌ **Don't**: Fail if some chips are missing
✅ **Do**: Use black placeholders and continue

❌ **Don't**: Enable button without validating parameters
✅ **Do**: Perform 3-layer validation before enabling

❌ **Don't**: Silent auto-resize with no user notification
✅ **Do**: Show preview dialog with proceed/cancel option

---

## Debug Tips

**Issue**: Alignment parameters not saved
- Check: `result.alignment_parameters` is not None after stitching
- Check: Position shifts were captured during stitching
- Check: File permissions for output directory

**Issue**: Chip images not found
- Check: Expected filename pattern matches actual files
- Check: Using same directory as original images
- Check: File extensions match
- Debug: Print `generate_chip_filename()` output

**Issue**: Dimension mismatches not detected
- Check: Loading chip image dimensions correctly
- Check: Comparing (width, height) not (height, width)
- Debug: Print dimensions before comparison

**Issue**: Position shifts not applied correctly
- Check: Affine transformation matrix construction
- Check: Position shifts are (dx, dy) not (dy, dx)
- Check: Canvas size matches final expected dimensions
- Debug: Visualize transformed images before blending

---

## Quick Reference

**Key Files**:
- Models: `src/models/alignment_parameters.py`
- Persistence: `src/lib/alignment_manager.py`
- Discovery: `src/lib/chip_image_finder.py`
- Stitching: `src/lib/chip_stitcher.py`
- GUI: `src/gui/main_window.py`, `src/gui/dimension_preview_dialog.py`

**Key Functions**:
- Save: `alignment_manager.save_alignment_params()`
- Load: `alignment_manager.load_alignment_params()`
- Validate: `alignment_manager.validate_alignment_params()`
- Find: `chip_image_finder.find_chip_images()`
- Stitch: `chip_stitcher.stitch_chip_images()`

**Key Data Structures**:
- `AlignmentParameters` - Stored parameters
- `ChipImageSet` - Discovery results
- `StitchedResult` - Stitching output
- `ChipStitchMetadata` - Result metadata

---

## Next Steps

1. Read `spec.md` for detailed requirements
2. Read `plan.md` for full context
3. Read `data-model.md` for entity details
4. Read `contracts/chip-stitching-api.md` for API specs
5. Implement phases in order (data → persistence → discovery → stitching → GUI)
6. Run tests after each phase
7. Validate with real .czi test data

**Ready to start? Begin with Phase 1: Core Data Models!**

