# Phase 0: Research & Technical Decisions

**Feature**: Chip Image Stitching with Alignment Reuse  
**Date**: 2025-11-05  
**Status**: Complete

## Overview

This document captures the technical research and decision-making process for implementing chip image stitching with alignment parameter reuse. The feature extends the existing NSEW image stitcher (spec 001) to support a second stitching operation that reuses spatial alignment parameters from the first operation.

## Key Technical Decisions

### 1. Alignment Parameter Storage Format

**Decision**: JSON file format with structured schema

**Rationale**:
- Human-readable for debugging and manual inspection
- Easy to serialize/deserialize with Python's built-in `json` module
- Lightweight (typically <10KB per parameter file)
- Supports nested structures for per-quadrant parameters
- Cross-platform compatible
- Can be version-controlled if needed

**Alternatives Considered**:
- **Binary format (pickle/msgpack)**: Faster but not human-readable; potential security issues with pickle; not cross-version compatible
- **YAML**: More human-friendly but requires additional dependency; slower parsing
- **Database (SQLite)**: Overkill for simple parameter storage; adds complexity

**Implementation Notes**:
- Store parameters in same directory as stitched output image
- Filename pattern: `{stitched_image_basename}_alignment.json`
- Schema includes: quadrant positions, dimensions, translation vectors, timestamp, original image paths
- Use `indent=2` for JSON formatting for readability

---

### 2. Chip Image Filename Pattern Matching

**Decision**: Simple string insertion pattern: `prefix_chipQUADRANT.ext`

**Rationale**:
- Matches user's example: `opnT2_NE.czi` → `opnT2_chipNE.czi`
- No separator between "chip" and quadrant maintains backwards compatibility with existing naming conventions
- Easy to implement with string manipulation
- Predictable for users to understand

**Alternatives Considered**:
- **Regex-based flexible matching**: More flexible but harder to predict; users wouldn't know what to name files
- **Configuration file for patterns**: Unnecessary complexity for straightforward use case
- **Underscore separator (`_chip_NE`)**: Doesn't match user's provided example

**Implementation Notes**:
- Extract quadrant from original filename using existing `keyword_detector.py`
- Insert "chip" immediately before quadrant identifier
- Preserve file extension from original image
- Handle edge cases: multiple underscore-separated components, no underscore before quadrant

---

### 3. Dimension Normalization Strategy

**Decision**: Resize chip images to match corresponding original quadrant dimensions before applying position shifts

**Rationale**:
- Position shifts are in pixel coordinates relative to specific image dimensions
- Resizing ensures alignment parameters remain valid
- Prevents geometric distortion from mismatched dimensions
- Simpler than recalculating position shifts for different dimensions

**Alternatives Considered**:
- **Scale position shifts proportionally**: Complex math; introduces rounding errors; may not preserve alignment accuracy
- **Use original chip dimensions**: Position shifts would be incorrect if dimensions differ
- **Reject mismatched dimensions**: Too restrictive; users often have chips at different resolutions

**Implementation Notes**:
- Use existing `dimension_handler.normalize_dimensions()` function
- Resize using high-quality interpolation (LANCZOS or BICUBIC)
- Store original and final dimensions in result metadata
- Show preview notification before resizing with proceed/cancel option

---

### 4. Alignment Parameter Validation Strategy

**Decision**: Three-layer validation (file format, parameter completeness, image file existence)

**Rationale**:
- **Layer 1 (Format)**: Prevents crashes from corrupted/malformed JSON
- **Layer 2 (Completeness)**: Ensures all required fields present before processing
- **Layer 3 (Existence)**: Verifies referenced original images still available for context
- Progressive validation provides specific error messages for each failure type
- Aligns with constitution's data integrity and validation principles

**Alternatives Considered**:
- **Minimal validation (format only)**: Too risky; missing fields cause runtime errors
- **Strict validation with checksum**: Overkill; file modification is acceptable if dimensions match
- **No image existence check**: Users could use parameters on wrong image sets

**Implementation Notes**:
- Validation order: format → completeness → existence (fail fast)
- Required fields: `version`, `timestamp`, `quadrants` (array), per-quadrant: `name`, `dimensions`, `position_shift`
- Image existence: check file paths, warn if missing but don't block if dimensions recorded
- Return validation result object with specific error details

---

### 5. Placeholder Image Generation

**Decision**: Pure black (RGB: 0,0,0) images sized to match corresponding original quadrant dimensions

**Rationale**:
- Pure black chosen by user in clarifications (Q2)
- Matches original quadrant dimensions ensures alignment consistency
- Simple to generate (no complex patterns or gradients)
- Low memory footprint
- Clear visual distinction in stitched result

**Alternatives Considered**:
- **Mid-gray or white**: User explicitly chose black
- **Patterned (checkerboard)**: Visually distracting for analysis
- **Match available chip dimensions**: Inconsistent with alignment parameters

**Implementation Notes**:
- Create placeholder as NumPy array: `np.zeros((height, width, 3), dtype=np.uint8)`
- Use dimensions from `AlignmentParameters` for corresponding quadrant
- Label placeholders in metadata: `"chipNE": {"type": "placeholder", "reason": "file_not_found"}`

---

### 6. GUI State Management for Chip Stitch Button

**Decision**: Enable button when valid alignment parameters are available (either from current session or loaded from disk)

**Rationale**:
- Button disabled by default prevents invalid operations
- Automatically enables after successful stitching provides immediate workflow continuity
- Loading saved parameters from disk enables cross-session workflow
- Disabling on new image load prevents parameter/image mismatch

**Alternatives Considered**:
- **Always enabled with runtime error**: Bad UX; users click disabled button and see error
- **Session-only enablement**: Doesn't support saved parameter reuse (conflicts with clarification Q1)
- **Manual enable by user**: Extra step; not intuitive

**Implementation Notes**:
- Button state managed by `MainWindow` based on `self.alignment_parameters` attribute
- Enable conditions: (1) successful stitch just completed, (2) valid parameter file loaded
- Disable conditions: (1) app start, (2) new images loaded, (3) parameter validation failed
- Visual state: clearly distinguishable disabled (grayed out) vs. enabled

---

### 7. Dimension Mismatch Notification Strategy

**Decision**: Show preview notification before stitching with proceed/cancel option, plus include details in result metadata

**Rationale**:
- Preview allows user to verify resize operation before processing
- Cancel option prevents wasted processing time if wrong files selected
- Result metadata provides permanent record of transformations
- Aligns with constitution's GUI design principle (clear feedback)

**Alternatives Considered**:
- **Pre-notification only**: No permanent record of transformations
- **Post-notification only**: Can't cancel after processing already done
- **Always auto-resize silently**: User has no control or awareness

**Implementation Notes**:
- Detect dimension mismatches during chip image loading
- Show `DimensionPreviewDialog` with table of transformations
- Dialog includes: image name, original dimensions, target dimensions, action (resize/placeholder)
- Proceed button continues to stitching; Cancel returns to main window
- Result window displays transformation details in metadata panel

---

### 8. Alignment Reuse Implementation Approach

**Decision**: Inject stored position shifts directly into stitching pipeline, bypassing feature detection

**Rationale**:
- Dramatically faster (50% time savings per success criterion)
- Ensures exact consistency with original stitching
- Simpler code path (no feature detection overhead)
- Works even if chip images have different content/exposure

**Alternatives Considered**:
- **Re-run feature detection with hints**: Still slow; unnecessary computation
- **Hybrid approach (detect + validate)**: Adds complexity; no benefit over pure reuse

**Implementation Notes**:
- Extend `lib/stitching.py` to accept optional `alignment_parameters` argument
- When parameters provided, skip OpenCV's feature detection and matching
- Apply position shifts using affine transformation matrices
- Use same blending/compositing logic as original stitching
- Return result with parameter reuse noted in metadata

---

## Dependencies & Best Practices

### JSON Schema Validation

**Practice**: Define explicit JSON schema for alignment parameter files

**Rationale**: Provides clear contract for parameter format; enables validation; documents structure

**Implementation**: Use dataclass with type hints, serialize via `dataclasses.asdict()`, deserialize with validation

---

### File Discovery Performance

**Practice**: Use `pathlib.Path.glob()` for file discovery instead of `os.walk()`

**Rationale**: More Pythonic; faster for single-directory search; better type support

**Implementation**: `parent_dir.glob(f"{prefix}_chip*.{ext}")`

---

### Progress Feedback

**Practice**: Emit progress signals at key milestones during chip stitching

**Rationale**: Keeps user informed; maintains GUI responsiveness; aligns with performance standards

**Implementation**:
- 0%: "Loading chip images..."
- 25%: "Validating dimensions..."
- 50%: "Applying alignment..."
- 75%: "Blending images..."
- 100%: "Generating result..."

---

### Error Handling

**Practice**: Use specific exception types for different failure modes

**Rationale**: Enables targeted error recovery; provides clear error messages; improves debugging

**Implementation**: Define exception hierarchy:
- `AlignmentParameterError` (base)
  - `ParameterFileCorruptedError`
  - `ParameterFileIncompleteError`
  - `ParameterImageMismatchError`
- `ChipImageError` (base)
  - `ChipImageNotFoundError`
  - `ChipImageDimensionError`

---

## Integration Points

### With Existing 001-nsew-image-stitcher

**Integration**: Extends `StitchedResult` to include `alignment_parameters` field

**Rationale**: Alignment parameters naturally belong with stitching result; enables seamless workflow

**Changes Required**:
- Add `alignment_parameters: Optional[AlignmentParameters]` to `StitchedResult`
- Modify `stitch_quadrants()` to capture and return position shifts
- Update `ResultWindow` to display parameter file save location

---

### With Config Management System

**Integration**: Add alignment parameter I/O to existing `lib/config_manager.py`

**Rationale**: Reuses existing configuration persistence patterns; maintains consistency

**Changes Required**:
- Add `save_alignment_params(params, path)` function
- Add `load_alignment_params(path)` function
- Add `validate_alignment_params(params)` function

---

## Open Questions Resolved

All technical questions were resolved through the clarification session and research:

1. ✅ Parameter persistence (Q1 clarification): Persistent storage to disk
2. ✅ Placeholder color (Q2 clarification): Pure black
3. ✅ Dimension handling (Q3 clarification): Resize to match originals
4. ✅ Notification timing (Q4 clarification): Preview + result metadata
5. ✅ Parameter validation (Q5 clarification): Comprehensive 3-layer validation

No remaining unknowns - ready for Phase 1 design.

---

## References

- OpenCV Stitcher documentation: https://docs.opencv.org/4.x/d2/d8d/classcv_1_1Stitcher.html
- NumPy image operations: https://numpy.org/doc/stable/reference/routines.array-manipulation.html
- PyQt6 dialog patterns: https://doc.qt.io/qt-6/qdialog.html
- JSON schema best practices: https://json-schema.org/understanding-json-schema/
- Pathlib documentation: https://docs.python.org/3/library/pathlib.html

