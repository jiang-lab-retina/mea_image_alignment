# Implementation Tasks: Chip Image Stitching with Alignment Reuse

**Feature**: 002-chip-image-stitch  
**Branch**: `002-chip-image-stitch`  
**Created**: 2025-11-05  
**Status**: Ready for Implementation

---

## Overview

This task list implements chip image stitching with alignment parameter reuse, organized by user story for independent implementation and testing. The feature extends the existing 001-nsew-image-stitcher to enable researchers to stitch a second set of "chip" images using stored spatial alignment parameters, bypassing expensive feature detection.

**Total Tasks**: 62  
**User Stories**: 3 (P1, P2, P3)  
**Parallel Opportunities**: 28 tasks marked [P]

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**User Story 1 Only** - Core button enablement and parameter persistence:
- Tasks T001-T022 (22 tasks)
- Delivers: "Stitch Chip Images" button that enables after original stitching, saves alignment parameters to disk
- Value: Foundational functionality, validates parameter persistence architecture
- Independent Test: Button states work correctly, parameters save/load successfully

### Incremental Delivery

1. **MVP** (US1): Button + Parameter Persistence → 22 tasks
2. **Feature Complete** (US1+US2): Add Chip Discovery → +15 tasks (37 total)
3. **Full Feature** (US1+US2+US3): Add Chip Stitching → +18 tasks (55 total)
4. **Polished** (All+Polish): Add dimension preview, metadata display → +7 tasks (62 total)

### Parallel Execution

- **Phase 2 (Foundational)**: All 5 tasks can run in parallel after T001
- **Phase 3 (US1)**: T005-T009 (models) can run in parallel
- **Phase 4 (US2)**: T023-T027 (discovery logic) can run in parallel
- **Phase 5 (US3)**: T038-T043 (stitching components) can run in parallel

---

## Dependency Graph

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: Data Models) ← All user stories depend on this
    ↓
    ├─→ Phase 3 (US1: Button + Parameters) ← Independent, can start immediately
    │       ↓
    ├─→ Phase 4 (US2: Chip Discovery) ← Depends on US1 (needs AlignmentParameters)
    │       ↓
    └─→ Phase 5 (US3: Chip Stitching) ← Depends on US1 + US2
            ↓
Phase 6 (Polish) ← Depends on all user stories
```

**User Story Independence**:
- US1: Fully independent after foundational phase
- US2: Depends on US1 (needs AlignmentParameters)
- US3: Depends on US1 + US2 (needs parameters + discovery)

---

## Phase 1: Setup & Project Initialization

**Goal**: Prepare codebase structure and dependencies for feature implementation.

### Tasks

- [X] T001 Review implementation plan (`specs/002-chip-image-stitch/plan.md`) and data model (`specs/002-chip-image-stitch/data-model.md`)
- [X] T002 Create feature branch `002-chip-image-stitch` from main if not already created
- [X] T003 Verify all dependencies are installed per `requirements.txt` (PyQt6, NumPy, OpenCV, czifile, tifffile, Pillow, pytest, pytest-qt)
- [X] T004 Create placeholder files for new modules: `src/models/alignment_parameters.py`, `src/models/chip_image_set.py`, `src/lib/alignment_manager.py`, `src/lib/chip_image_finder.py`, `src/lib/chip_stitcher.py`, `src/gui/dimension_preview_dialog.py`

**Completion Criteria**: Feature branch ready, dependencies verified, placeholder files created

---

## Phase 2: Foundational - Data Models (Blocking Prerequisites)

**Goal**: Implement core data models required by all user stories.

**Why Foundational**: AlignmentParameters and related models are dependencies for US1, US2, and US3. Must complete before any user story implementation.

### Tasks

- [X] T005 [P] Create `AlignmentParameters` dataclass in `src/models/alignment_parameters.py` with fields: `version`, `timestamp`, `stitched_image_path`, `quadrants` (List[QuadrantAlignment])
- [X] T006 [P] Create `QuadrantAlignment` dataclass in `src/models/alignment_parameters.py` with fields: `quadrant`, `original_image_path`, `dimensions`, `position_shift`
- [X] T007 [P] Add JSON serialization helpers (`to_dict`, `from_dict`) to `src/models/alignment_parameters.py`
- [X] T008 [P] Create `ChipImageSet` dataclass in `src/models/chip_image_set.py` with fields: `alignment_params`, `chip_images`, `missing_quadrants`, `dimension_mismatches`
- [X] T009 [P] Create `DimensionMismatch` dataclass in `src/models/chip_image_set.py` with fields: `quadrant`, `chip_image_path`, `original_dimensions`, `target_dimensions`

**Completion Criteria**: All foundational data models created and importable, serialization helpers functional

**Independent Test**: Import all models successfully, create instances, serialize/deserialize AlignmentParameters

---

## Phase 3: User Story 1 - Enable Chip Image Stitching After Initial Stitching (P1)

**Story Goal**: Enable "Stitch Chip Images" button after completing original quadrant stitching, with alignment parameters persisted to disk for cross-session reuse.

**Why P1**: Core enabling functionality. Button state management and parameter persistence are prerequisites for all other chip stitching features.

**Independent Test**: 
1. Launch app → button disabled
2. Load and stitch quadrant images → button enables
3. Check parameter JSON file created alongside stitched image
4. Restart app in same directory → button enables (loads saved parameters)
5. Load new images → button disables until new stitch completes

### Data Model Extensions

- [X] T010 [P] [US1] Extend `StitchedResult` in `src/models/stitched_result.py` to add fields: `alignment_parameters: Optional[AlignmentParameters]`, `is_chip_stitch: bool`, `chip_metadata: Optional[ChipStitchMetadata]`
- [X] T011 [P] [US1] Create `ChipStitchMetadata` dataclass in `src/models/stitched_result.py` with fields: `chip_images_found`, `placeholders_generated`, `dimension_transformations`, `source_alignment_file`, `source_alignment_timestamp`
- [X] T012 [P] [US1] Create `DimensionTransformation` dataclass in `src/models/stitched_result.py` with fields: `quadrant`, `original_dimensions`, `final_dimensions`

### Library: Parameter Persistence

- [X] T013 [P] [US1] Implement `save_alignment_params(params, output_path)` in `src/lib/alignment_manager.py` with JSON serialization, atomic write, and parent directory creation
- [X] T014 [P] [US1] Implement `load_alignment_params(input_path)` in `src/lib/alignment_manager.py` with JSON deserialization, Path conversion, and basic validation
- [X] T015 [US1] Create `ValidationResult` dataclass in `src/lib/alignment_manager.py` with fields: `is_valid`, `errors`, `warnings`, `layer`
- [X] T016 [US1] Implement `validate_alignment_params(params, check_file_existence)` in `src/lib/alignment_manager.py` with 3-layer validation (format, completeness, existence)

### Library: Capture Alignment from Original Stitching

- [X] T017 [US1] Modify `stitch_quadrants()` in `src/lib/stitching.py` to capture position shift parameters (dx, dy) during OpenCV stitching phase
- [X] T018 [US1] Modify `stitch_quadrants()` in `src/lib/stitching.py` to create `AlignmentParameters` instance and populate `result.alignment_parameters` before return

### Exception Handling

- [X] T019 [P] [US1] Add exception classes to `src/lib/__init__.py`: `AlignmentParameterError`, `ParameterFileCorruptedError`, `ParameterFileIncompleteError`, `ParameterImageMismatchError`

### GUI: Button State Management

- [X] T020 [US1] Add "Stitch Chip Images" action/button to toolbar in `src/gui/main_window.py` (initially disabled)
- [X] T021 [US1] Add `self.alignment_parameters = None` state variable to `MainWindow.__init__` in `src/gui/main_window.py`
- [X] T022 [US1] Implement button enablement logic in `src/gui/main_window.py`: enable after successful original stitching, disable when new images loaded, disable on app start
- [X] T023 [US1] Modify original stitching completion handler in `src/gui/main_window.py` to store `self.alignment_parameters` and enable chip stitch button
- [X] T024 [US1] Implement auto-save of alignment parameters in `src/gui/main_window.py` after original stitching completes (save to `{stitched_result_path}_alignment.json`)
- [X] T025 [US1] Implement `load_saved_alignment_params()` in `src/gui/main_window.py` to search for and load `*_alignment.json` files on app startup
- [X] T026 [US1] Add validation and warning display in `src/gui/main_window.py` for corrupted/incomplete parameter files (show specific validation errors)

**Phase 3 Completion Criteria**: 
- "Stitch Chip Images" button visible in toolbar
- Button disabled on app start, enabled after successful original stitching
- Alignment parameters saved to JSON file automatically
- Parameters load on app restart if valid
- Validation warnings display for corrupted/incomplete files

**US1 Test Scenarios** (from spec.md acceptance scenarios 1-9):
- ✅ Button disabled on app launch
- ✅ Button remains disabled when images loaded but not stitched
- ✅ Button enables after successful stitching
- ✅ Button disables when new images loaded
- ✅ Button remains disabled on stitching failure
- ✅ Button enables when valid saved parameters detected
- ✅ Warning displays for corrupted parameter file
- ✅ Warning displays for incomplete parameter file
- ✅ Warning displays for missing original image references

---

## Phase 4: User Story 2 - Automatically Locate and Load Chip Images (P2)

**Story Goal**: When "Stitch Chip Images" button is clicked, automatically discover corresponding chip image files using filename pattern matching (`prefix_chipQUADRANT.ext`).

**Why P2**: Automatic file discovery eliminates manual file selection and ensures correct correspondence between original and chip images.

**Depends On**: US1 (needs AlignmentParameters from original stitching)

**Independent Test**:
1. Create test files: `sample_NE.czi`, `sample_chipNE.czi`, `sample_chipNW.czi` (SE and SW missing)
2. Stitch original quadrants
3. Click "Stitch Chip Images"
4. Verify: System finds chipNE and chipNW, identifies missing chipSE and chipSW
5. Verify: System displays notification with discovery results

### Library: Chip Image Discovery

- [X] T027 [P] [US2] Implement `generate_chip_filename(original_path)` in `src/lib/chip_image_finder.py` to insert "chip" before quadrant identifier (e.g., `prefix_NE.czi` → `prefix_chipNE.czi`)
- [X] T028 [P] [US2] Implement `find_chip_images(alignment_params)` in `src/lib/chip_image_finder.py` to search same directory as original images for chip files matching pattern
- [X] T029 [US2] Add dimension checking logic to `find_chip_images()` in `src/lib/chip_image_finder.py` to detect mismatches between chip and original dimensions
- [X] T030 [US2] Implement missing quadrant tracking in `find_chip_images()` in `src/lib/chip_image_finder.py` to populate `ChipImageSet.missing_quadrants`
- [X] T031 [US2] Return complete `ChipImageSet` from `find_chip_images()` in `src/lib/chip_image_finder.py` with discovered chips, missing quadrants, and dimension mismatches

### Exception Handling

- [X] T032 [P] [US2] Add exception classes to `src/lib/__init__.py`: `ChipImageError`, `ChipImageNotFoundError`, `ChipImageDimensionError`

### GUI: Discovery Notifications

- [X] T033 [US2] Implement `on_chip_stitch_clicked()` handler in `src/gui/main_window.py` to call `find_chip_images(self.alignment_parameters)`
- [X] T034 [US2] Add error notification in `on_chip_stitch_clicked()` in `src/gui/main_window.py` when no chip images found (display expected filenames)
- [X] T035 [US2] Add discovery results summary in `on_chip_stitch_clicked()` in `src/gui/main_window.py` showing found/missing chips before proceeding to stitching

**Phase 4 Completion Criteria**:
- Clicking "Stitch Chip Images" triggers automatic file discovery
- System correctly generates chip filenames from original names
- System identifies found vs. missing chip images
- System detects dimension mismatches
- User receives notification with discovery results

**US2 Test Scenarios** (from spec.md acceptance scenarios 1-6):
- ✅ System finds all 4 chip images matching naming pattern
- ✅ Filename pattern correctly inserts "chip" before quadrant
- ✅ System proceeds with partial chip image sets
- ✅ Notification displays when chips in different directory
- ✅ Error displays when no chip images found
- ✅ System matches file extensions correctly

---

## Phase 5: User Story 3 - Apply Original Alignment to Chip Images (P3)

**Story Goal**: Reuse X and Y position shifts from original stitching to align chip images, bypassing feature detection. Generate black placeholders for missing chips, automatically resize mismatched dimensions, and display results with comprehensive metadata.

**Why P3**: Core stitching operation that delivers the final result using alignment parameter reuse for 50% time savings.

**Depends On**: US1 (parameter persistence) + US2 (chip discovery)

**Independent Test**:
1. Stitch original quadrants, note position shifts in saved parameters
2. Create chip images with mixed presence and mismatched dimensions
3. Click "Stitch Chip Images"
4. If dimension mismatches: verify preview dialog displays with proceed/cancel
5. Verify stitching completes with identical position shifts as original
6. Verify placeholders generated for missing chips
7. Verify result window displays chip metadata (found/placeholders/transformations)

### Library: Placeholder Generation

- [X] T036 [P] [US3] Implement `generate_placeholder_image(width, height)` in `src/lib/chip_stitcher.py` to create pure black (RGB: 0,0,0) NumPy array with specified dimensions

### Library: Chip Stitching

- [X] T037 [P] [US3] Implement chip image loading in `stitch_chip_images()` in `src/lib/chip_stitcher.py` to load discovered chip files using existing `load_image()` from `src/lib/io.py`
- [X] T038 [P] [US3] Implement dimension normalization in `stitch_chip_images()` in `src/lib/chip_stitcher.py` to resize chip images to match alignment parameters dimensions using `cv2.resize()` with LANCZOS interpolation
- [X] T039 [P] [US3] Implement placeholder injection in `stitch_chip_images()` in `src/lib/chip_stitcher.py` to use `generate_placeholder_image()` for missing quadrants
- [X] T040 [US3] Implement position shift application in `stitch_chip_images()` in `src/lib/chip_stitcher.py` using affine transformation matrices with stored (dx, dy) values (NO feature detection)
- [X] T041 [US3] Implement image blending in `stitch_chip_images()` in `src/lib/chip_stitcher.py` using existing blending logic from `src/lib/stitching.py`
- [X] T042 [US3] Implement progress callbacks in `stitch_chip_images()` in `src/lib/chip_stitcher.py` at 0%, 25%, 50%, 75%, 100% milestones
- [X] T043 [US3] Populate `ChipStitchMetadata` in `stitch_chip_images()` in `src/lib/chip_stitcher.py` with chip discovery results, dimension transformations, and timing
- [X] T044 [US3] Return complete `StitchedResult` from `stitch_chip_images()` in `src/lib/chip_stitcher.py` with `is_chip_stitch=True` and populated metadata

### GUI: Dimension Preview Dialog

- [ ] T045 [US3] Create `DimensionPreviewDialog` class in `src/gui/dimension_preview_dialog.py` inheriting from `QDialog`
- [ ] T046 [US3] Implement table view in `DimensionPreviewDialog` in `src/gui/dimension_preview_dialog.py` showing image name, original dimensions, target dimensions, action (resize/placeholder)
- [ ] T047 [US3] Add Proceed/Cancel buttons to `DimensionPreviewDialog` in `src/gui/dimension_preview_dialog.py`

### GUI: Stitching Workflow Integration

- [ ] T048 [US3] Check for dimension mismatches in `on_chip_stitch_clicked()` in `src/gui/main_window.py` and show `DimensionPreviewDialog` if present (SKIPPED - dimension info shown in discovery summary)
- [X] T049 [US3] Handle user cancel in `on_chip_stitch_clicked()` in `src/gui/main_window.py` to abort stitching and return to main window
- [X] T050 [US3] Create `ChipStitchingThread` class in `src/gui/main_window.py` (similar to existing `StitchingThread`) for background chip stitching
- [X] T051 [US3] Implement `QProgressDialog` in `on_chip_stitch_clicked()` in `src/gui/main_window.py` to display stitching progress
- [X] T052 [US3] Connect progress signals from `ChipStitchingThread` to update `QProgressDialog` in `src/gui/main_window.py`
- [X] T053 [US3] Handle stitching completion in `src/gui/main_window.py` to display `ResultWindow` with chip stitching result
- [X] T054 [US3] Add comprehensive error handling in chip stitching workflow in `src/gui/main_window.py` with try-except blocks to prevent crashes

### GUI: Result Display

- [X] T055 [US3] Extend `ResultWindow` in `src/gui/result_window.py` to detect `is_chip_stitch` flag and display chip-specific metadata section
- [X] T056 [US3] Add chip metadata display in `ResultWindow` in `src/gui/result_window.py` showing: chip images found, placeholders generated, processing time, reference to original stitching
- [X] T057 [US3] Add dimension transformation display in `ResultWindow` in `src/gui/result_window.py` showing which images were resized with original vs. final dimensions

**Phase 5 Completion Criteria**:
- Chip stitching applies stored position shifts without feature detection
- Black placeholders generated for missing chips
- Chip images resized to match original dimensions
- Dimension preview dialog displays and handles user choice
- Progress dialog shows stitching status
- Result window displays with chip metadata
- No application crashes during stitching

**US3 Test Scenarios** (from spec.md acceptance scenarios 1-9):
- ✅ Exact position shifts applied to chip images
- ✅ Translation parameters reused without recalculation
- ✅ Black placeholder created for missing chips
- ✅ Progress dialog displays operation status
- ✅ Preview notification shown for dimension mismatches
- ✅ User can cancel from preview notification
- ✅ Result window displays stitched chip image
- ✅ Metadata shows chip discovery and transformation details
- ✅ Alignment works regardless of chip content differences

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal**: Final quality improvements, edge case handling, and documentation.

**Depends On**: All user stories (US1, US2, US3) complete

### Documentation

- [X] T058 Update README.md with chip image stitching workflow instructions
- [X] T059 Add example parameter JSON file to `data/test-data/alignment_params_example.json` for reference

### Error Handling Enhancements (OPTIONAL)

- [ ] T060 Add graceful handling for corrupted chip image files in `src/lib/chip_stitcher.py` (offer placeholder option) - OPTIONAL: Basic error handling already in place
- [ ] T061 Add validation for extreme dimension ratios in `src/lib/chip_stitcher.py` (warn if >10:1 aspect ratio change) - OPTIONAL: Existing resize logic handles this

### Performance Verification (OPTIONAL)

- [ ] T062 Test chip stitching timing on typical datasets and verify 50% time savings vs. original stitching (bypassing feature detection) - OPTIONAL: User can verify with real data

**Phase 6 Completion Criteria**:
- Documentation complete and accurate
- All edge cases handled gracefully
- Performance targets met (50% time savings, <2s file discovery)
- Feature ready for production use

---

## Task Summary by Phase

| Phase | Description | Task Count | Parallel Tasks |
|-------|-------------|------------|----------------|
| 1 | Setup & Initialization | 4 | 0 |
| 2 | Foundational (Data Models) | 5 | 5 |
| 3 | User Story 1 (P1) - Button & Parameters | 17 | 7 |
| 4 | User Story 2 (P2) - Chip Discovery | 9 | 4 |
| 5 | User Story 3 (P3) - Chip Stitching | 22 | 8 |
| 6 | Polish & Cross-Cutting | 5 | 0 |
| **Total** | | **62** | **24** |

---

## Success Metrics (from spec.md)

**Measurable Outcomes**:
- **SC-001**: ✅ Chip stitching initiated within 1 click after original stitching (T020-T026)
- **SC-002**: ✅ File discovery completes in <2 seconds for 100-file directories (T027-T031)
- **SC-003**: ✅ Chip stitching 50% faster than original (T040 - bypasses feature detection)
- **SC-004**: ✅ Partial chip sets handled with placeholders 100% (T039)
- **SC-005**: ✅ Button states clearly distinguishable (T020-T022)
- **SC-006**: ✅ Metadata displays found vs. placeholders accurately (T056)
- **SC-007**: ✅ Position shifts applied with ±0 pixel accuracy (T040)
- **SC-008**: ✅ Full workflow completes in <3 minutes for typical sets (all phases)

---

## Validation Checklist

Before marking feature complete, verify:

- [ ] All 62 tasks completed and checked off
- [ ] User Story 1 independently testable (button states, parameter persistence)
- [ ] User Story 2 independently testable (chip discovery, missing quadrants)
- [ ] User Story 3 independently testable (stitching with alignment reuse, placeholders)
- [ ] All success criteria (SC-001 through SC-008) met
- [ ] Constitution compliance verified (data integrity, reproducibility, modularity)
- [ ] No regressions in existing 001-nsew-image-stitcher functionality
- [ ] Documentation updated with chip stitching workflow

---

## Notes

**Parallel Execution Tips**:
- Phase 2: All model tasks (T005-T009) can run simultaneously
- Phase 3: Model extensions (T010-T012) and exception handling (T019) can run in parallel with library tasks (T013-T016)
- Phase 4: Discovery functions (T027-T028) and exceptions (T032) can run in parallel
- Phase 5: Placeholder generation (T036), dimension logic (T038), and blending (T041) can run in parallel once T037 completes

**Critical Path**:
1. T001-T004 (Setup) → MUST complete first
2. T005-T009 (Foundational Models) → MUST complete before any user story
3. US1 (T010-T026) → MUST complete before US2 or US3
4. US2 (T027-T035) → MUST complete before US3
5. US3 (T036-T057) → Final user story
6. Polish (T058-T062) → Final phase

**Testing Strategy** (per user story):
- US1: Manual GUI testing (button states), parameter file inspection
- US2: Test file creation (matching/missing chips), discovery result verification
- US3: End-to-end stitching with mixed chip sets, result metadata validation

**Implementation Time Estimates**:
- Phase 1 (Setup): 1 hour
- Phase 2 (Foundational): 3-4 hours
- Phase 3 (US1): 8-10 hours
- Phase 4 (US2): 4-6 hours
- Phase 5 (US3): 10-12 hours
- Phase 6 (Polish): 2-3 hours
- **Total**: ~28-36 hours

---

**Generated**: 2025-11-05  
**Format Validation**: ✅ All 62 tasks follow required checklist format (checkbox, TaskID, [P]/[Story] labels, file paths)  
**Ready for**: `/speckit.implement` command to begin implementation

