# Feature Specification: Corner Annotation and Square Fit

**Feature Branch**: `[001-corner-annotation]`  
**Created**: 2025-11-11  
**Status**: Draft  
**Input**: User description: "put all current gui in one tab named \"Stitch\", make a new tab named \"Corner\". In the new table, load the stitched chip images and allow the user to use mouse to click to label the coordinate of the corner of the the chip. Then, provide a button to generate a square shape that has corners fit the annotated coordinates of the corners as close as possible. Display the square for visual validation"

## Clarifications

### Session 2025-11-11
- Q: Default image source behavior in the Corner tab? → A: Auto-load latest chip-stitched result if available; otherwise prompt to open a file.
- Q: Square orientation constraint? → A: Allow arbitrary rotation (any angle).
- Q: Coordinate reference for annotations/fit? → A: Pixel coordinates only.
- Q: Auto-fit confidence threshold? → A: RMS ≤ 2 px AND confidence ≥ 0.7.
- Q: Sidecar JSON filename convention? → A: Use CZI filename prefix without quadrant; filename "<prefix>.json".
- Q: Auto-fit resolution strategy? → A: Multi-scale: downscale detect, full-res refine.
- Q: “Latest chip-stitched image” selection rule? → A: Newest by modification time; tie-breaker by lexicographic filename.
- Q: Multi-scale downscale defaults? → A: Default 0.5; allowed range 0.25–0.5.
- Q: Auto-fit performance target? → A: 200 ms at 4K on a typical laptop.
- Q: Coordinate rounding rule? → A: Click coordinates round to nearest integer pixel.
- Q: Confidence definition? → A: Normalized [0,1] from edge consistency, square symmetry, contour fit agreement.
- Q: Missing/invalid sidecar behavior? → A: Show non-intrusive message; continue without annotations.
- Q: Mixed channels and downscale impact? → A: Viewport supports grayscale/RGB without altering data; downscale applies to auto-fit internals only.
- Q: Concurrent changes with auto-fit? → A: Undo affects only points; accept/discard doesn’t modify points unless user clears.
- Q: Provenance fields in JSON? → A: Include source_czi_prefix, stitched_image_path, thresholds, resolution_strategy.
- Q: Dark mode overlay contrast? → A: ≥4.5:1; defaults overlay #44FF88, markers #FFD166; line width ≥2 px.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Restructure GUI into tabs (Priority: P1)

Move all existing functionality into a tab named "Stitch" and add a new tab named "Corner".

**Why this priority**: Enables clear separation of workflows and prepares the UI for corner annotation without disrupting current stitching tasks.

**Independent Test**: Launch application; confirm "Stitch" is default tab with all current controls; switch to "Corner" tab successfully.

**Acceptance Scenarios**:

1. Given the app starts, When it loads the main window, Then the "Stitch" tab is selected and all current controls are present with unchanged behavior.
2. Given the main window, When the user selects the "Corner" tab, Then the tab switches without errors and shows Corner tooling.

---

### User Story 2 - Load stitched chip image in Corner tab (Priority: P1)

As a user in the "Corner" tab, I can load a stitched chip image to annotate.

**Why this priority**: Corner annotation requires a visual reference image; loading must be simple and reliable.

**Independent Test**: From Corner tab, load a TIFF/PNG/JPEG stitched chip image and see it rendered fully with zoom/pan.

**Acceptance Scenarios**:

1. Given no image loaded, When the user clicks "Open Image…" and chooses a valid stitched image, Then the image appears in the viewport at fit-to-window zoom.
2. Given a prior chip-stitched image exists, When opening the Corner tab, Then the latest chip-stitched image auto-loads (newest by modification time; tie-break by lexicographic filename); otherwise a file picker prompts the user to open one.
3. Given a very large image, When loaded, Then interaction remains responsive (zoom/pan within 50 ms/frame).

---

### User Story 3 - Click to annotate chip corners (Priority: P1)

As a user, I can click on the image to record the four chip corner coordinates in pixel space.

**Why this priority**: Accurate corner coordinates are essential for downstream geometry and validation.

**Independent Test**: Add 4 corner points via clicks; see numbered markers and a list of coordinates update; undo/clear works.

**Acceptance Scenarios**:

1. Given an image is loaded, When the user left-clicks, Then a numbered marker (1..4) appears and a coordinate (x, y) is recorded in a list.
2. Given 1–3 points placed, When the user continues clicking, Then points are added up to exactly 4; the "Fit Square" button remains disabled until 4 points exist.
3. Given a mistake, When the user clicks "Undo" or "Clear", Then the latest point is removed or all points are cleared respectively and numbering updates.
4. Given the image is zoomed/panned, When the user clicks, Then recorded coordinates reflect image-space pixels (not screen coordinates).
5. A minimally complete annotation requires at least two corners labeled; UI indicates minimal completion at ≥2 points. Fitting still requires exactly 4 points.

---

### User Story 4 - Fit a square and visualize overlay (Priority: P1)

As a user, after placing 4 corners, I can press "Fit Square" to compute and overlay the best-fit square and see basic fit metrics.

**Why this priority**: Visual validation of geometric fit ensures scientific integrity of corner measurements.

**Independent Test**: With 4 points, press "Fit Square"; a square overlay appears, with side length, rotation, and residuals shown; overlay togglable.

**Acceptance Scenarios**:

1. Given exactly 4 corner points, When "Fit Square" is pressed, Then a square is computed (parameters: center, side_length, rotation_degrees) that minimizes squared residuals to the annotated corners and is overlayed on the image.
2. Given the overlay is shown, When the user toggles overlay visibility, Then the square appears/disappears without affecting annotations.
3. Given the fit completes, When metrics are displayed, Then the UI shows side length (px), rotation (deg), per-point residuals (px), and RMS error (px).
4. Square orientation: arbitrary rotation (no axis-alignment constraint).

---

### User Story 5 - Save/Reload annotations and fit (Priority: P2)

As a user, I can save the 4 corner points and the fitted square parameters to a sidecar file and reload them later.

**Why this priority**: Supports reproducibility and cross-session work.

**Independent Test**: Save annotations; reopen the image; load annotations; markers and overlay reappear identically.

**Acceptance Scenarios**:

1. Given 4 points and a fit, When "Save" is pressed, Then a sidecar JSON is written alongside the image containing points, square parameters, and metrics.
2. Given a saved JSON, When the image is reopened, Then annotations and overlay load automatically or upon "Load Annotations".
3. Coordinate reference: Pixel coordinates only (no micron conversion).
4. Saved JSON filename uses the CZI prefix without quadrant, with ".json" extension (e.g., "sample.json").
5. If the sidecar is missing or invalid, Then show a non-intrusive message and proceed without annotations (no blocking).

---

### User Story 6 - Automatic square fit by image intensity (Priority: P2)

As a user, I can press an "Auto-fit Square" button to automatically propose a square that best matches the chip boundaries inferred from image intensities, then review it visually.

**Why this priority**: Reduces manual effort and provides a reproducible, objective initial fit that the user can accept or refine.

**Independent Test**: Load a stitched chip image; click "Auto-fit Square"; a proposed square overlay appears with confidence metrics and can be accepted or adjusted.

**Acceptance Scenarios**:

1. Given a stitched chip image with clearly delineated chip edges, When "Auto-fit Square" is pressed, Then a square overlay is computed and displayed along with a confidence score and residual metrics.
2. Given the auto-fit overlay is shown, When the user clicks "Accept", Then the proposed square becomes the active fit and metrics are recorded; When the user clicks "Discard", Then the proposal is removed without altering existing annotations.
3. Given low-contrast or ambiguous edges, When "Auto-fit Square" is pressed, Then if RMS residual > 2 px or confidence < 0.7, the system reports low confidence and suggests manual annotation, without blocking the user.
4. Given an existing manual fit, When "Auto-fit Square" is accepted, Then it replaces the previous fit but the prior annotations remain available unless explicitly cleared.
5. Auto-fit completes within 200 ms on 4K images on a typical laptop.
6. Undo affects only annotation points; accepting or discarding an auto-fit proposal does not modify points unless the user explicitly clears them.

---

### Edge Cases

- Clicks outside image bounds: ignore and warn non-intrusively.
- Duplicate/near-identical points: allow but warn if any two points are within 2 px; fit still proceeds.
- Fewer than 4 points: disable "Fit Square".
- More than 4 clicks: restrict to exactly 4 by requiring clear/undo before adding.
- Very large images: ensure zoom/pan and overlay remain responsive; memory usage bounded.
- Image resizing in viewport: display coordinates in full-resolution image space; show also the viewport scale for clarity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Tabs)**: The main window MUST present two tabs: "Stitch" (default) containing all existing controls unchanged; "Corner" for corner annotation.
- **FR-002 (Image loading)**: In "Corner", users MUST be able to load a stitched chip image via file picker supporting TIFF/PNG/JPEG. The app MUST auto-load the most recent chip-stitched output if available; otherwise, prompt with a file picker.
- **FR-003 (Viewport)**: The image MUST support fit-to-window, zoom, pan, and high-DPI rendering without altering the underlying data.
- Viewport MUST correctly display both grayscale and RGB images without converting or mutating saved image data.
- **FR-004 (Annotation capture)**: Left-click MUST add a numbered corner marker (1..4) and record integer pixel coordinates (x, y). Provide "Undo" and "Clear".
- **FR-005 (Validation states)**: "Fit Square" MUST be disabled until exactly 4 points exist; enable immediately when 4 are present.
- **FR-006 (Square fitting)**: System MUST compute a best-fit square parameterized by center (cx, cy), side_length (px), and rotation_degrees, minimizing sum of squared distances from annotated corners to the nearest square corners; do not mutate annotation points. Orientation: arbitrary rotation (no axis alignment).
- **FR-007 (Overlay)**: System MUST overlay the fitted square with clearly visible styling and provide a toggle to show/hide it.
- **FR-008 (Metrics)**: System MUST display side_length, rotation_degrees, per-point residuals (px), and RMS residual (px).
- **FR-009 (Persistence)**: System MUST save and load annotations and fit to/from a sidecar JSON: image_path, timestamp, points, fit parameters, residuals, version metadata. The JSON filename MUST use the source CZI filename prefix with the quadrant suffix removed and a ".json" extension (e.g., "<prefix>.json"), saved alongside the stitched image unless an explicit output directory is chosen.
- **FR-010 (Coordinate system)**: Coordinates MUST be in image pixel space with origin at top-left and x increasing right, y increasing down; click coordinates are rounded to the nearest integer pixel; no micron conversion required.
- **FR-011 (Non-destructive)**: Loading, annotating, and fitting MUST NOT alter image data on disk.
- **FR-012 (Accessibility/UX)**: Provide tooltips and dark-mode-aware colors; marker sizes and text remain legible at common zoom levels.
- In dark mode, overlays/markers MUST maintain a contrast ratio ≥ 4.5:1 against the background; default colors: overlay #44FF88, markers #FFD166; line width ≥ 2 px.
- **FR-013 (Auto-fit Square)**: Provide an "Auto-fit Square" control that proposes a square derived from image intensity patterns consistent with chip boundaries; display the proposal as an overlay with confidence and residual metrics; allow users to Accept (apply as current fit) or Discard.
- **FR-014 (Auto-fit confidence handling)**: Apply thresholds RMS residual ≤ 2 px AND confidence score ≥ 0.7 for a "confident" auto-fit. If either threshold is not met, label as low confidence, inform the user, and keep manual tools available; do not block manual annotation or fitting. Confidence score is normalized to [0, 1].
- Confidence is derived from edge consistency, square symmetry, and contour fit agreement, normalized to [0,1].
- **FR-015 (Minimum annotated corners)**: A minimally complete annotation MUST include at least two corners labeled; square fitting operations remain restricted to exactly four annotated corners.
- **FR-016 (Auto-fit resolution strategy)**: Auto-fit MUST use a multi-scale pipeline: perform coarse detection on a downscaled copy (0.25–0.5×) and refine parameters at full resolution; downscale factor SHOULD be configurable.
- Default downscale factor: 0.5; allowed configuration range: 0.25–0.5.
- Downscale applies only to internal auto-fit processing; original image data is not modified.

### Constitution-Aligned Requirements

- **Data Integrity**: Never modify source images; store annotations/fits in separate sidecar files with timestamps and source references.
- **GUI Usability**: Controls must be discoverable and self-explanatory; prevent invalid states (e.g., fitting with <4 points).
- **Reproducibility**: Saving exact pixel coordinates and derived fit parameters enables exact reload and verification.
- **Validation**: Visual overlay and numeric residuals provide immediate quality checks.
- **Modularity**: Core fit logic should be callable independently from the GUI to support automated validation or CLI in future.

### Key Entities *(include if feature involves data)*

- **CornerPoint**: { index: 1..4, x: int, y: int }
- **CornerAnnotation**: { image_path: string, points: CornerPoint[4], created_at: datetime }
- **SquareFit**: { center_x: float, center_y: float, side_length: float, rotation_degrees: float, corners: CornerPoint[4], residuals_px: float[4], rms_residual_px: float }
- **CornerAnnotationFile (JSON)**: { version: string, image_path: string, points: CornerPoint[4], fit: SquareFit, created_at: datetime, provenance: { source_czi_prefix: string, stitched_image_path: string, thresholds: { rms_px: float, confidence_min: float }, resolution_strategy: { mode: "multiscale", downscale: float } } }

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (No regressions)**: All existing Stitch tab workflows function as before (manual QA pass across 5 representative images).
- **SC-002 (Usability)**: 90% of users complete corner annotation and fit in under 60 seconds on first attempt.
- **SC-003 (Performance)**: Fit computation and overlay appear within 100 ms after pressing "Fit Square" on 4K images on a typical laptop.
- **SC-004 (Accuracy)**: On synthetic square tests with 1-pixel perturbations, median RMS residual ≤ 1.5 px.
- **SC-005 (Reproducibility)**: Saved annotations reloaded produce identical overlay and identical metrics (bit-for-bit equality).
- **SC-006 (Stability)**: Zero crashes across 20 open/annotate/fit/save/reload cycles during soak test.
