# Tasks: NSEW Image Stitcher

**Input**: Design documents from `/specs/001-nsew-image-stitcher/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in the specification, so test tasks are marked optional and placed at the end of each user story phase for developers who choose to follow TDD.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single desktop application**: `src/`, `tests/` at repository root
- Paths shown below are absolute or relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure (src/models/, src/lib/, src/gui/, tests/unit/, tests/integration/, tests/fixtures/)
- [X] T002 Create requirements.txt with dependencies: PyQt6>=6.6.0, numpy>=1.24.0, opencv-python>=4.8.0, czifile>=2019.7.2, tifffile>=2023.7.10, Pillow>=10.0.0, pytest>=7.4.0, pytest-qt>=4.2.0
- [X] T003 [P] Create setup.py for package installation
- [X] T004 [P] Create main.py application entry point
- [X] T005 [P] Create .gitignore to exclude .pyc, __pycache__, data/test-data/, .pytest_cache/, *.egg-info
- [X] T006 [P] Create README.md with project description, installation instructions, and quick start guide
- [X] T007 [P] Create data/test-data/README.md with instructions for obtaining test microscopy images

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Create Quadrant enum in src/models/__init__.py with values NE, NW, SE, SW and position_indices() method
- [X] T009 [P] Create ImageMetadata dataclass in src/models/__init__.py with fields: pixel_size_um, magnification, acquisition_date, objective, channel_names
- [X] T010 Create QuadrantImage dataclass in src/models/quadrant_image.py with fields: file_path, quadrant, filename, dimensions, dtype, num_channels, file_size_bytes, image_data, metadata, md5_checksum
- [X] T011 Create StitchingConfig dataclass in src/models/stitching_config.py with fields: alignment_method, blend_mode, overlap_threshold_percent, resize_strategy, interpolation_method, confidence_threshold, output_format, compression_level, missing_quadrant_fill
- [X] T012 Create StitchedResult dataclass in src/models/stitched_result.py with fields: stitched_image_data, full_resolution, display_resolution, output_file_path, source_quadrants, stitching_config, quality_metrics, processing_time_seconds, timestamp, software_version, was_downsampled
- [X] T013 Create QualityMetrics dataclass in src/models/stitched_result.py with fields: overall_confidence, alignment_confidence_* (4 borders), overlap_percent_* (4 borders), feature_matches_total, inlier_ratio, warnings
- [X] T014 Create custom exception hierarchy in src/lib/__init__.py: ImageProcessingError (base), FileError, StitchingError, ValidationError, EmptyListError, with specific subclasses (CorruptedFileError, InsufficientOverlapError, etc.)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Load and Visualize MEA Quadrant Images (Priority: P1) 🎯 MVP

**Goal**: Enable researchers to load 1-4 microscopy images, auto-detect spatial positions from filenames, and display them in a synchronized 2x2 quadrant layout

**Independent Test**: Load 1-4 files with NSEW keywords → images appear in correct quadrant positions with synchronized zoom/pan

### Implementation for User Story 1

- [X] T015 [P] [US1] Implement detect_quadrant() function in src/lib/keyword_detector.py to extract spatial keywords from filenames using regex with priority order (exact 2-letter > full words > cardinals)
- [X] T016 [P] [US1] Implement load_image() function in src/lib/io.py to load .czi files using czifile library, returning (np.ndarray, ImageMetadata)
- [X] T017 [P] [US1] Extend load_image() in src/lib/io.py to support .lsm/.tif/.tiff files using tifffile library
- [X] T018 [P] [US1] Add format detection logic to load_image() in src/lib/io.py based on file extension, raising UnsupportedFormatError for unknown formats
- [X] T019 [P] [US1] Add error handling to load_image() in src/lib/io.py for corrupted files, raising CorruptedFileError with descriptive message
- [X] T020 [P] [US1] Implement metadata extraction in load_image() in src/lib/io.py to populate ImageMetadata (pixel_size_um, magnification, acquisition_date)
- [X] T021 [US1] Create QuadrantViewer widget in src/gui/quadrant_viewer.py as QWidget subclass with QGraphicsView for image display, label for quadrant position, footer for dimensions/file size
- [X] T022 [US1] Implement set_image() method in src/gui/quadrant_viewer.py to convert NumPy array to QPixmap and display in QGraphicsView
- [X] T023 [US1] Implement zoom functionality in src/gui/quadrant_viewer.py with mouse wheel control (range 10%-400%), emitting zoom_changed signal
- [X] T024 [US1] Implement pan functionality in src/gui/quadrant_viewer.py with click-and-drag, emitting pan_changed signal
- [X] T025 [US1] Implement sync_zoom() and sync_pan() slots in src/gui/quadrant_viewer.py to receive external zoom/pan updates
- [X] T026 [US1] Create AssignmentDialog in src/gui/assignment_dialog.py as QDialog subclass with thumbnail preview, radio buttons for NE/NW/SE/SW, and Assign/Cancel buttons
- [X] T027 [US1] Create MainWindow in src/gui/main_window.py as QMainWindow subclass with menu bar, toolbar (Open Files, Stitch, Save Config buttons), and 2x2 grid layout for 4 QuadrantViewer widgets
- [X] T028 [US1] Implement on_open_files_clicked() slot in src/gui/main_window.py to show QFileDialog for file selection, accepting .czi, .lsm, .tif, .tiff formats
- [X] T029 [US1] Implement load_files() method in src/gui/main_window.py to iterate through selected files, call lib.io.load_image() and lib.keyword_detector.detect_quadrant() for each file
- [X] T030 [US1] Add ambiguity handling to load_files() in src/gui/main_window.py: if detect_quadrant() returns None, show AssignmentDialog and use user's selection
- [X] T031 [US1] Add error handling to load_files() in src/gui/main_window.py: catch CorruptedFileError, show QMessageBox warning with filename and error, continue with remaining files
- [X] T032 [US1] Implement quadrant image storage in src/gui/main_window.py using dict[Quadrant, QuadrantImage] to track loaded images
- [X] T033 [US1] Implement display logic in src/gui/main_window.py to populate QuadrantViewer widgets at correct grid positions based on Quadrant.position_indices()
- [X] T034 [US1] Implement zoom/pan synchronization in src/gui/main_window.py by connecting all QuadrantViewer zoom_changed/pan_changed signals to sync_zoom_to_all()/sync_pan_to_all() methods
- [X] T035 [US1] Add visual indicators in src/gui/main_window.py: empty quadrants show "Empty" placeholder text, green border for loaded quadrants
- [X] T036 [US1] Update main.py to initialize QApplication, create MainWindow, and start event loop
- [X] T037 [US1] Update status bar in src/gui/main_window.py to display "Loaded X of Y files" message after file loading completes

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently (load images, display in quadrants, zoom/pan synchronization)

**Optional Tests for User Story 1** (for developers following TDD):
- [ ] T038 [P] [US1] [OPTIONAL] Create test_keyword_detector.py in tests/unit/ with tests for exact matches (NE, SW), case insensitivity, ambiguous keywords, missing keywords
- [ ] T039 [P] [US1] [OPTIONAL] Create test_io.py in tests/unit/ with tests for loading .czi/.tif files, corrupted files, unsupported formats, metadata extraction
- [ ] T040 [P] [US1] [OPTIONAL] Create test_gui_workflow.py in tests/integration/ with pytest-qt test for loading 4 files and verifying display in correct positions
- [ ] T041 [P] [US1] [OPTIONAL] Create synthetic test images (100x100 NumPy arrays) in tests/fixtures/sample_images/ for use in unit tests

---

## Phase 4: User Story 2 - Stitch Four-Quadrant Images into Single Panorama (Priority: P2)

**Goal**: Enable automated stitching of loaded quadrant images into seamless composite with quality metrics and reproducibility

**Independent Test**: Load 4 overlapping quadrants → click Stitch button → seamless result appears in new window with quality metrics

### Implementation for User Story 2

- [X] T042 [P] [US2] Implement normalize_dimensions() function in src/lib/dimension_handler.py to resize list of QuadrantImage objects to common resolution (largest or smallest strategy) using bicubic interpolation
- [X] T043 [P] [US2] Implement downsample_for_display() function in src/lib/dimension_handler.py to scale down images exceeding max_dimension (default 4000px) using INTER_AREA interpolation
- [X] T044 [P] [US2] Implement compute_overlap_percentage() function in src/lib/stitching.py to calculate overlap between two images given homography matrix
- [X] T045 [US2] Implement stitch_quadrants() function in src/lib/stitching.py: validate inputs (non-empty, unique quadrants, compatible dtypes), normalize dimensions if needed, fill missing quadrants
- [X] T046 [US2] Add OpenCV stitcher integration to stitch_quadrants() in src/lib/stitching.py: create cv2.Stitcher, provide initial camera estimates based on quadrant positions, perform feature detection and matching
- [X] T047 [US2] Add quality metrics computation to stitch_quadrants() in src/lib/stitching.py: extract feature match counts, RANSAC inlier ratios, compute alignment confidence scores and overlap percentages for each border
- [X] T048 [US2] Add error detection to stitch_quadrants() in src/lib/stitching.py: check if overlap < config.overlap_threshold_percent, raise InsufficientOverlapError with specific guidance
- [X] T049 [US2] Implement missing quadrant interpolation in stitch_quadrants() in src/lib/stitching.py: create placeholder images for missing positions based on config.missing_quadrant_fill strategy (black, interpolate, or extend)
- [X] T050 [US2] Complete stitch_quadrants() return in src/lib/stitching.py: create StitchedResult object with stitched image, quality metrics, processing time, and references to source quadrants and config
- [X] T051 [P] [US2] Implement save_image() function in src/lib/io.py to save NumPy array to disk as TIFF/PNG/JPEG with optional compression and metadata embedding
- [X] T052 [P] [US2] Implement save_config() function in src/lib/config_manager.py to serialize StitchedResult to JSON file (excluding image_data, including all parameters and metrics)
- [X] T053 [P] [US2] Implement load_config() function in src/lib/config_manager.py to deserialize JSON to StitchingConfig object with validation
- [X] T054 [US2] Create StitchingThread in src/gui/main_window.py as QThread subclass with progress_updated(int, str), finished(StitchedResult), and error(str) signals
- [X] T055 [US2] Implement StitchingThread.run() in src/gui/main_window.py to call lib.stitching.stitch_quadrants() with progress updates at 0% (loading), 20% (normalizing), 40% (detecting features), 60% (computing alignment), 80% (blending), 100% (complete)
- [X] T056 [US2] Create StitchDialog in src/gui/stitch_dialog.py as QDialog subclass with controls for blend_mode (dropdown), overlap_threshold (slider 5-50%), alignment_method (dropdown), output_format (dropdown), compression_level (slider 0-9), allowing users to adjust parameters before stitching
- [X] T057 [US2] Add tooltips to all controls in src/gui/stitch_dialog.py explaining scientific meaning of parameters (e.g., "Multiband blending provides seamless transitions...")
- [X] T058 [US2] Implement parameter validation in StitchDialog in src/gui/stitch_dialog.py: ensure overlap 5-50%, compression 0-9, show error for invalid values
- [X] T059 [US2] Create ResultWindow in src/gui/result_window.py as QWidget subclass with QGraphicsView for stitched image display, QLabel sections for quality metrics, display/saved resolution info, and Save As/Close buttons
- [X] T060 [US2] Implement quality metrics display in src/gui/result_window.py: show overall confidence with color-coded icon (green >0.8, yellow 0.6-0.8, red <0.6), alignment confidence per border, overlap percentages, processing time
- [X] T061 [US2] Implement downsampling detection in src/gui/result_window.py: if result.was_downsampled, show info icon with message "Full resolution saved to disk", display both display and saved resolutions
- [X] T062 [US2] Implement Save As functionality in src/gui/result_window.py to show QFileDialog and call lib.io.save_image() with user-selected path and format
- [X] T063 [US2] Add "Stitch Images" button logic to src/gui/main_window.py: validate at least 1 image loaded, show StitchDialog to get/confirm parameters, create StitchingThread with loaded quadrants and config
- [X] T064 [US2] Add progress dialog handling to src/gui/main_window.py: create QProgressDialog when stitching starts, connect StitchingThread.progress_updated to update dialog, handle cancel button
- [X] T065 [US2] Add stitching completion handling to src/gui/main_window.py: on StitchingThread.finished signal, check if output exceeds 4GB, call lib.dimension_handler.downsample_for_display() if needed, create and show ResultWindow
- [X] T066 [US2] Add stitching error handling to src/gui/main_window.py: on StitchingThread.error signal, show QMessageBox.critical with error message and actionable guidance
- [X] T067 [US2] Add dimension mismatch notification to src/gui/main_window.py: before stitching, if quadrants have different dimensions, show QMessageBox.information displaying original dimensions and target common dimension
- [ ] T068 [US2] Add Save Config button logic to src/gui/main_window.py: if last_result exists, show QFileDialog to choose location, call lib.config_manager.save_config()
- [X] T069 [US2] Implement state management in src/gui/main_window.py: store last_result (StitchedResult), enable/disable Stitch button based on loaded image count, enable/disable Save Config button based on result existence

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently (full stitching workflow with quality metrics and reproducibility)

**Optional Tests for User Story 2** (for developers following TDD):
- [ ] T070 [P] [US2] [OPTIONAL] Create test_dimension_handler.py in tests/unit/ with tests for normalize_dimensions() with different strategies, downsample_for_display() with various sizes
- [ ] T071 [P] [US2] [OPTIONAL] Create test_stitching.py in tests/unit/ with tests using small synthetic 100x100 images for 4-quadrant stitch, missing quadrants, dimension mismatches
- [ ] T072 [P] [US2] [OPTIONAL] Create test_config_manager.py in tests/unit/ with tests for save/load config round-trip, JSON schema validation
- [ ] T073 [P] [US2] [OPTIONAL] Extend test_gui_workflow.py in tests/integration/ with end-to-end test: load 4 images → click Stitch → verify ResultWindow opens with quality metrics

---

## Phase 5: User Story 3 - Support Multiple Microscopy File Formats (Priority: P3)

**Goal**: Ensure all three file formats (.czi, .lsm, .tif/.tiff) work correctly with metadata extraction and multi-channel support

**Independent Test**: Load mix of .czi, .lsm, .tif files → all display and stitch correctly → metadata shown

### Implementation for User Story 3

- [ ] T074 [P] [US3] Add comprehensive format detection tests to load_image() in src/lib/io.py: verify .czi uses czifile, .lsm/.tif/.tiff use tifffile, unknown extensions raise UnsupportedFormatError
- [ ] T075 [P] [US3] Implement multi-channel support in load_image() in src/lib/io.py: accept channel_index parameter (default 0), extract specified channel from multi-channel files, raise ChannelIndexError if index out of range
- [ ] T076 [P] [US3] Enhance metadata extraction in load_image() in src/lib/io.py for .lsm files: extract LSM-specific tags (objective, magnification, pixel size) from TIFF metadata
- [ ] T077 [P] [US3] Enhance metadata extraction in load_image() in src/lib/io.py for .tiff files: read ImageJ metadata tags if present, standard TIFF tags for dimensions and pixel info
- [ ] T078 [P] [US3] Add metadata display to QuadrantViewer in src/gui/quadrant_viewer.py: show tooltip or expandable section with pixel size, magnification, acquisition date when available
- [ ] T079 [US3] Add channel selector to src/gui/quadrant_viewer.py: if QuadrantImage.num_channels > 1, show QComboBox to select channel, reload image data when selection changes
- [ ] T080 [US3] Add format validation to on_open_files_clicked() in src/gui/main_window.py: show error QMessageBox if unsupported format selected, list supported formats (.czi, .lsm, .tif, .tiff)
- [ ] T081 [US3] Add mixed format handling test: load one .czi, one .lsm, two .tif files in src/gui/main_window.py, verify all display correctly and stitch successfully

**Checkpoint**: All user stories should now be independently functional (comprehensive format support across entire workflow)

**Optional Tests for User Story 3** (for developers following TDD):
- [ ] T082 [P] [US3] [OPTIONAL] Extend test_io.py in tests/unit/ with tests for all three formats (.czi, .lsm, .tif), multi-channel extraction, metadata extraction per format
- [ ] T083 [P] [US3] [OPTIONAL] Create format validation tests in tests/integration/: load mixed formats, verify stitching works regardless of format combination

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T084 [P] Create docs/architecture.md with system architecture diagram showing data flow: file loading → keyword detection → display → stitching → result
- [ ] T085 [P] Create docs/parameters.md with scientific explanation of all stitching parameters (blend modes, overlap thresholds, interpolation methods) and recommended ranges
- [ ] T086 [P] Add keyboard shortcuts to src/gui/main_window.py: Ctrl+O for Open Files, Ctrl+S for Save Config, Ctrl+Return for Stitch
- [ ] T087 [P] Add logging configuration to main.py: set up Python logging module with DEBUG level for development, INFO for production, log to both console and file (app.log)
- [ ] T088 [P] Add comprehensive docstrings to all functions in src/lib/ modules following Google Python Style Guide format with Args, Returns, Raises sections
- [ ] T089 [P] Add type hints to all function signatures in src/lib/ and src/gui/ modules for static type checking with mypy
- [ ] T090 [P] Create .cursor/rules/specify-rules.mdc if not exists, or update with project-specific coding standards and common patterns
- [ ] T091 Code cleanup: run black/autopep8 formatter on all Python files in src/ and tests/
- [ ] T092 Code quality: run flake8/pylint on all Python files, fix any warnings or errors
- [ ] T093 Performance profiling: use cProfile on stitch_quadrants() with real MEA data (4x2000x2000 images), ensure completion <60 seconds
- [ ] T094 Memory profiling: use memory_profiler on full load → stitch workflow, ensure peak usage <4GB
- [ ] T095 Run quickstart.md validation: follow step-by-step instructions in quickstart.md, verify all commands work and produce expected results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion - No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion - Builds on US1 (uses loaded images from US1) but should be independently testable with synthetic data
- **User Story 3 (Phase 5)**: Depends on Foundational phase completion - Enhances US1 and US2 with additional format support
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories ✅ INDEPENDENT
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses QuadrantImage objects from US1 but can create synthetic ones for testing ✅ MOSTLY INDEPENDENT
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Enhances file loading from US1 ✅ MOSTLY INDEPENDENT

### Within Each User Story

- **US1**: lib functions (T015-T020) can be developed in parallel → GUI components (T021-T026) → MainWindow integration (T027-T037)
- **US2**: lib functions (T042-T053) can be developed in parallel → Thread (T054-T055) → Dialogs (T056-T062) → MainWindow integration (T063-T069)
- **US3**: Mostly parallel enhancements to existing functions (T074-T081)

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003-T007)
- All Foundational entity creation tasks can run in parallel after T008 (T009-T013)
- Within US1: T015-T020 can all run in parallel (different lib modules)
- Within US1: T021-T026 can run in parallel (different GUI components)
- Within US2: T042-T043, T044, T051-T053 can all run in parallel (different lib modules)
- Within US2: T056-T059 can run in parallel (different dialog components)
- Within US3: All tasks T074-T081 can run in parallel (enhancements to different modules)
- All Polish tasks T084-T092 can run in parallel

---

## Parallel Example: User Story 1 Core Functions

```bash
# These lib functions can all be implemented simultaneously:
Task T015: Implement detect_quadrant() in src/lib/keyword_detector.py
Task T016: Implement load_image() for .czi in src/lib/io.py
Task T017: Extend load_image() for .lsm/.tif in src/lib/io.py
Task T018: Add format detection to src/lib/io.py
Task T019: Add error handling to src/lib/io.py
Task T020: Add metadata extraction to src/lib/io.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T014) - CRITICAL: blocks all stories
3. Complete Phase 3: User Story 1 (T015-T037)
4. **STOP and VALIDATE**: Load 4 files with NSEW keywords, verify display in correct positions, test zoom/pan sync
5. Deploy/demo if ready - researchers can already inspect quadrant data!

### Incremental Delivery

1. **Foundation** (Phases 1-2): T001-T014 → Basic project structure ready
2. **MVP** (Phase 3): T015-T037 → Load and visualize quadrants ✅ SHIPPABLE
3. **Core Value** (Phase 4): T042-T069 → Add stitching capability ✅ SHIPPABLE  
4. **Enhanced** (Phase 5): T074-T081 → Multi-format support ✅ SHIPPABLE
5. **Production** (Phase 6): T084-T095 → Polish and documentation

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (Phases 1-2)
2. **Once Foundational is done** (after T014):
   - Developer A: User Story 1 (T015-T037) - Load & visualize
   - Developer B: User Story 2 (T042-T069) - Stitching (can use synthetic images initially)
   - Developer C: User Story 3 (T074-T081) - Format support
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Optional test tasks (marked [OPTIONAL]) are for developers who choose TDD approach - tests are NOT required by the specification
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Task Summary

- **Total Tasks**: 95 (excluding optional tests)
  - Phase 1 (Setup): 7 tasks
  - Phase 2 (Foundational): 7 tasks
  - Phase 3 (User Story 1): 23 tasks (+ 4 optional test tasks)
  - Phase 4 (User Story 2): 28 tasks (+ 4 optional test tasks)
  - Phase 5 (User Story 3): 8 tasks (+ 2 optional test tasks)
  - Phase 6 (Polish): 12 tasks
- **Parallel Opportunities**: ~40 tasks can run in parallel within their phase
- **Independent Test Criteria**:
  - **US1**: Load images → display in correct quadrants → zoom/pan synchronization works
  - **US2**: Load images → click Stitch → result window shows stitched image with quality metrics
  - **US3**: Load mixed formats (.czi, .lsm, .tif) → all display and stitch correctly
- **Suggested MVP Scope**: Phase 1-3 (T001-T037) = Load and visualize quadrants
- **Format Validation**: ✅ All tasks follow checklist format (checkbox, ID, labels, file paths)

