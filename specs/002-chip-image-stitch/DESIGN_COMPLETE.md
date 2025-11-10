# Design Phase Complete: Chip Image Stitching

**Feature**: 002-chip-image-stitch  
**Date**: 2025-11-05  
**Status**: ✅ Design Complete - Ready for Task Generation

---

## Summary

Implementation planning for chip image stitching with alignment reuse is complete. All Phase 0 (Research) and Phase 1 (Design) artifacts have been generated and validated against the constitution.

---

## Generated Artifacts

### Phase 0: Research ✓

- ✅ `research.md` - 8 technical decisions documented with rationale and alternatives
  - Alignment parameter storage format (JSON)
  - Chip image filename pattern matching
  - Dimension normalization strategy
  - Alignment parameter validation (3-layer)
  - Placeholder image generation (pure black)
  - GUI state management
  - Dimension mismatch notification
  - Alignment reuse implementation

### Phase 1: Design ✓

- ✅ `data-model.md` - 5 entities defined with complete schemas
  - `AlignmentParameters` (main entity)
  - `QuadrantAlignment` (nested)
  - `ChipImageSet` (discovery results)
  - `DimensionMismatch` (nested)
  - `StitchedResult` (extended from 001)
  - `ChipStitchMetadata` (nested)
  - JSON schema v1.0 specification

- ✅ `contracts/chip-stitching-api.md` - 9 functions with full API contracts
  - `alignment_manager.save_alignment_params()`
  - `alignment_manager.load_alignment_params()`
  - `alignment_manager.validate_alignment_params()`
  - `chip_image_finder.find_chip_images()`
  - `chip_image_finder.generate_chip_filename()`
  - `chip_stitcher.stitch_chip_images()`
  - `chip_stitcher.generate_placeholder_image()`
  - `stitching.stitch_quadrants()` (modified)
  - Exception hierarchy defined

- ✅ `quickstart.md` - Developer reference guide
  - Architecture overview with diagrams
  - Data flow documentation
  - Implementation phases
  - Key code snippets
  - Testing strategy
  - Performance targets
  - Common pitfalls
  - Debug tips

- ✅ `.cursor/rules/specify-rules.mdc` - Agent context updated
  - Python 3.10+ confirmed
  - All dependencies documented
  - JSON for configuration persistence

---

## Post-Design Constitution Check ✅

All 8 constitution gates still pass after detailed design:

| Gate | Status | Evidence |
|------|--------|----------|
| **Data Integrity** | ✅ PASS | Alignment parameters are read-only; chip images never modified; placeholders labeled in metadata; all processing on in-memory copies |
| **GUI Design** | ✅ PASS | Button state management detailed; DimensionPreviewDialog specified; progress callbacks defined; result metadata display planned |
| **Reproducibility** | ✅ PASS | JSON schema v1.0 defined; all required fields specified; timestamp and version tracking; serialization helpers documented |
| **Validation** | ✅ PASS | 3-layer validation specified (format, completeness, existence); specific error types defined; validation result object designed |
| **Modularity** | ✅ PASS | 4 new library modules defined; GUI separated from logic; API contracts fully specified; CLI-callable functions |
| **Performance** | ✅ PASS | Progress callback points defined (0%, 25%, 50%, 75%, 100%); background threading in GUI; alignment reuse bypasses feature detection |
| **Testing** | ✅ PASS | Unit test strategy for each module; integration tests for workflows; pytest-qt for GUI; real data validation |
| **Documentation** | ✅ PASS | All parameters documented; JSON schema provided; quickstart guide created; API contracts complete |

**Complexity Violations**: None

**Risk Assessment**: Low - extends proven architecture from 001-nsew-image-stitcher

---

## Key Design Decisions

1. **JSON for Parameter Storage**: Human-readable, lightweight, cross-platform, no additional dependencies
2. **Filename Pattern `prefix_chipQUADRANT.ext`**: Simple, predictable, matches user example
3. **Resize Chips to Original Dimensions**: Ensures pixel-perfect alignment, simpler than recalculating shifts
4. **3-Layer Validation**: Progressive validation with specific error messages for each failure mode
5. **Pure Black Placeholders**: User-chosen in clarifications, simple to generate, visually clear
6. **Persistent Parameter Storage**: Enables cross-session workflows, aligns with scientific reproducibility
7. **Alignment Reuse**: Bypasses feature detection for 50% time savings, ensures exact consistency

---

## Implementation Roadmap

### Phase 1: Core Data Models
- Create `AlignmentParameters` dataclass with JSON serialization
- Extend `StitchedResult` with chip metadata fields
- Create `ChipImageSet` dataclass
- **Validation**: Unit tests for serialization round-trips

### Phase 2: Parameter Persistence
- Implement `alignment_manager` module (save/load/validate)
- Extend `stitch_quadrants()` to capture position shifts
- **Validation**: Integration test for full save/load cycle

### Phase 3: Chip Discovery
- Implement `chip_image_finder` module
- Filename pattern matching logic
- Dimension checking
- **Validation**: Unit tests with test files, edge cases

### Phase 4: Chip Stitching
- Implement `chip_stitcher` module
- Placeholder generation
- Dimension normalization
- Position shift application
- **Validation**: Integration test with mixed present/missing chips

### Phase 5: GUI Integration
- Add "Stitch Chip Images" button to main window
- Implement state management
- Create `DimensionPreviewDialog`
- Extend `ResultWindow` for chip metadata
- **Validation**: GUI tests with pytest-qt, manual workflow testing

---

## Technical Highlights

**Zero New Dependencies**: All functionality implemented with existing Python 3.10+, PyQt6, NumPy, OpenCV, czifile, tifffile, Pillow stack.

**Alignment Reuse Efficiency**: Bypassing OpenCV's feature detection and matching provides:
- 50%+ time savings for chip stitching
- Pixel-perfect consistency with original stitching
- Robustness to exposure/content differences between original and chip images

**Cross-Session Support**: Persistent JSON parameter files enable:
- Chip stitching in different sessions
- Archival of alignment parameters for reproducibility
- Parameter sharing across systems

**Graceful Degradation**: System handles:
- Missing chip images → black placeholders
- Dimension mismatches → automatic resize with user preview
- Corrupted parameter files → specific error messages with recovery guidance
- Missing original images → warnings but proceed if dimensions available

---

## Testing Coverage

| Component | Unit Tests | Integration Tests | GUI Tests |
|-----------|------------|-------------------|-----------|
| Alignment Parameters | ✅ Serialization, deserialization, validation | ✅ Save/load cycle | N/A |
| Chip Image Finder | ✅ Filename generation, dimension checking | ✅ Discovery with mixed presence | N/A |
| Chip Stitcher | ✅ Placeholder generation, resizing | ✅ Full workflow with alignment reuse | N/A |
| GUI Components | N/A | N/A | ✅ Button states, dialogs, result display |

**Test Data Requirements**:
- Sample original quadrant images (.czi)
- Sample chip quadrant images (.czi) with matching prefixes
- Sample alignment parameter JSON file
- Test cases for dimension mismatches
- Test cases for missing chips

---

## Performance Targets (from spec.md)

| Metric | Target | Strategy |
|--------|--------|----------|
| Chip stitching time | 50% faster than original | Bypass feature detection |
| File discovery time | <2 seconds for 100 files | Use pathlib.glob(), single directory search |
| Parameter validation | <500ms | Progressive validation, fail fast |
| Alignment accuracy | ±0 pixels | Direct position shift application |
| GUI responsiveness | Non-blocking | Background threading for stitching |

---

## Ready for Next Phase

**Next Command**: `/speckit.tasks`

This will generate the detailed implementation task list (`tasks.md`) based on the completed design artifacts.

**Implementation Order**:
1. Data models → Parameter persistence → Chip discovery → Chip stitching → GUI integration
2. Each phase includes corresponding unit/integration tests
3. Final phase includes end-to-end validation with real .czi data

---

## Questions Resolved

All 5 clarification questions from the spec were addressed in design:

1. ✅ Parameter persistence: Persistent JSON storage alongside stitched images
2. ✅ Placeholder color: Pure black (RGB: 0,0,0)
3. ✅ Dimension handling: Resize chips to match original dimensions
4. ✅ Notification timing: Preview dialog before stitching + result metadata
5. ✅ Parameter validation: Comprehensive 3-layer validation (format, completeness, existence)

**No open technical questions remain.**

---

## Design Review Checklist

- [x] All unknowns from Technical Context resolved
- [x] Research decisions documented with rationale
- [x] Data entities fully specified with validation rules
- [x] API contracts defined with function signatures
- [x] Error handling strategy specified
- [x] GUI components and workflows designed
- [x] Testing strategy defined
- [x] Performance targets established
- [x] Constitution compliance verified
- [x] Agent context updated
- [x] Quick reference guide created

**Status**: ✅ COMPLETE - Ready for task generation

---

**Generated by**: `/speckit.plan` command  
**Review Date**: 2025-11-05  
**Next Step**: Run `/speckit.tasks` to generate implementation task list

