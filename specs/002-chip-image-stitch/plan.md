# Implementation Plan: Chip Image Stitching with Alignment Reuse

**Branch**: `002-chip-image-stitch` | **Date**: 2025-11-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-chip-image-stitch/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature adds automated chip image stitching functionality that reuses alignment parameters from the initial quadrant stitching operation. After users complete the original NSEW quadrant stitching, they can click a "Stitch Chip Images" button to automatically discover corresponding chip images (identified by "chip" prefix in filename) and stitch them using the stored X/Y position shifts, bypassing computationally expensive feature detection. The system persists alignment parameters to disk as JSON files, validates them on load, handles missing chip images with black placeholders, and automatically resizes chip images to match original quadrant dimensions for alignment accuracy.

**Technical Approach**: Extend the existing `StitchedResult` model to include serializable alignment parameters; add JSON persistence layer for parameter storage/loading; implement filename pattern matching for chip image discovery; create dimension normalization and placeholder generation logic; add new GUI button with state management tied to parameter availability; reuse existing stitching pipeline with parameter injection instead of feature detection.

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: PyQt6 (GUI framework), NumPy (array operations), OpenCV (image stitching algorithms), czifile (CZI format I/O), tifffile (TIFF format I/O), Pillow (image utilities)  
**Storage**: JSON files (alignment parameters stored alongside stitched images in same directory)  
**Testing**: pytest (unit tests), pytest-qt (GUI component testing)  
**Target Platform**: Desktop application (macOS, Linux, Windows)  
**Project Type**: Single desktop application  
**Performance Goals**: Chip stitching completes in 50% less time than original stitching (bypassing feature detection); file discovery completes in <2 seconds for directories with up to 100 files; alignment parameter validation completes in <500ms  
**Constraints**: Parameters must apply with pixel-perfect accuracy (±0 pixels); GUI must remain responsive during all operations; must handle chip images up to different dimensions than originals  
**Scale/Scope**: Supports 1-4 quadrant images per stitch; handles microscopy files up to several GB each; JSON parameter files typically <10KB

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify alignment with Image MEA Dulce Constitution v1.0.0:

- [x] **Data Integrity**: Yes - Original chip image files are never modified; alignment parameters are read-only after initial stitching generates them; black placeholders are explicitly labeled in metadata; all processing operates on in-memory copies
- [x] **GUI Design**: Yes - "Stitch Chip Images" button provides clear visual state (enabled/disabled); preview notifications show dimension mismatches with proceed/cancel options; progress dialog provides operation status; result window displays comprehensive metadata
- [x] **Reproducibility**: Yes - Alignment parameters are stored as JSON with all required fields (quadrant positions, dimensions, translation vectors); parameters include timestamp and reference to original stitching session; chip stitching can be reproduced by re-running with same parameter file and chip images
- [x] **Validation**: Yes - Comprehensive 3-layer validation (file format, parameter completeness, image file existence); specific error messages for each validation failure; result metadata indicates which chip images were found vs. placeholders; dimension transformation details displayed
- [x] **Modularity**: Yes - Chip image file discovery logic is separate from GUI (callable from CLI); alignment application logic works without feature detection libraries; position shift parameters are serializable and independently loadable; parameter persistence module is standalone
- [x] **Performance**: Yes - Progress dialog displays during chip stitching; background threading prevents GUI blocking; file discovery optimized for directories with many files; alignment reuse bypasses expensive feature detection
- [x] **Testing**: Yes - Unit tests for parameter serialization/deserialization, filename pattern matching, placeholder generation, dimension normalization; integration tests for full chip stitching workflow; validation with real .czi test data
- [x] **Documentation**: Yes - Alignment parameters documented with scientific meaning (X/Y position shifts in pixels); parameter file format documented in data model; quickstart guide explains chip stitching workflow; result metadata explains transformations

**Complexity Justification Required If**: None - all gates pass without violations

## Project Structure

### Documentation (this feature)

```text
specs/002-chip-image-stitch/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── alignment-params-schema.md  # JSON schema for parameter files
│   └── chip-stitching-api.md       # Library API contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single desktop application structure (extends existing 001-nsew-image-stitcher)

src/
├── models/
│   ├── __init__.py                  # [EXISTING] Quadrant, ImageMetadata
│   ├── quadrant_image.py            # [EXISTING] QuadrantImage
│   ├── stitching_config.py          # [EXISTING] StitchingConfig
│   ├── stitched_result.py           # [EXTEND] StitchedResult - add alignment parameters
│   └── alignment_parameters.py      # [NEW] AlignmentParameters dataclass
│
├── lib/
│   ├── __init__.py                  # [EXISTING] Exception hierarchy
│   ├── io.py                        # [EXISTING] load_image(), save_image()
│   ├── keyword_detector.py          # [EXISTING] detect_quadrant()
│   ├── dimension_handler.py         # [EXISTING] normalize_dimensions(), downsample_for_display()
│   ├── stitching.py                 # [EXTEND] stitch_quadrants() - capture alignment parameters
│   ├── config_manager.py            # [EXTEND] save_config(), load_config() - add alignment parameters
│   ├── chip_image_finder.py         # [NEW] find_chip_images(), generate_chip_filename()
│   ├── alignment_manager.py         # [NEW] save_alignment_params(), load_alignment_params(), validate_alignment_params()
│   └── chip_stitcher.py             # [NEW] stitch_chip_images() - apply stored parameters
│
├── gui/
│   ├── __init__.py                  # [EXISTING]
│   ├── main_window.py               # [EXTEND] Add "Stitch Chip Images" button, state management
│   ├── quadrant_viewer.py           # [EXISTING] Display quadrant images
│   ├── assignment_dialog.py         # [EXISTING] Manual quadrant assignment
│   ├── stitch_dialog.py             # [EXISTING] Stitching parameters
│   ├── result_window.py             # [EXTEND] Display chip stitching metadata
│   └── dimension_preview_dialog.py  # [NEW] Preview dimension mismatches with proceed/cancel
│
└── cli/                             # [OPTIONAL - Future enhancement]
    └── chip_stitch.py               # [NEW] CLI for chip stitching

tests/
├── unit/
│   ├── test_alignment_parameters.py        # [NEW] Parameter serialization tests
│   ├── test_alignment_manager.py           # [NEW] Save/load/validation tests
│   ├── test_chip_image_finder.py           # [NEW] Filename pattern matching tests
│   ├── test_chip_stitcher.py               # [NEW] Alignment application tests
│   └── test_dimension_normalization.py     # [NEW] Resize and placeholder tests
│
├── integration/
│   └── test_chip_stitching_workflow.py     # [NEW] End-to-end chip stitching test
│
└── test-data/                               # [EXISTING] Test microscopy images
    ├── sample_NE.czi
    ├── sample_chipNE.czi                    # [NEW] Chip image test data
    └── alignment_params.json                # [NEW] Test parameter file
```

**Structure Decision**: Single desktop application structure. This feature extends the existing 001-nsew-image-stitcher implementation by adding new modules for chip image discovery and alignment parameter persistence, while reusing existing I/O, dimension handling, and GUI infrastructure. The modular design allows the chip stitching functionality to work both through the GUI and programmatically via the library API.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

_No violations - all constitution gates pass. This section intentionally left blank._
