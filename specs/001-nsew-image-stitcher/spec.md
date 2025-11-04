# Feature Specification: NSEW Image Stitcher

**Feature Branch**: `001-nsew-image-stitcher`  
**Created**: 2025-11-04  
**Status**: Draft  
**Input**: User description: "create GUI to visualize czi files according to the keyword NSEW as north, south, east, west for location. View four files at a time. Provide a button and function to stitch the data to one image using stitching package. Make it compatible to LSM files and TIFF or TIF files. Display the stithed image in a new window at the end."

## Clarifications

### Session 2025-11-04

- Q: How should the system behave when users load fewer than four quadrant images? → A: Allow loading any number of images and enable stitching with whatever is available (system interpolates missing quadrants)
- Q: How should the system resolve files with ambiguous or multiple spatial keywords? → A: Prompt user to manually assign quadrant position when ambiguous keywords detected
- Q: How should the system handle quadrant images with different pixel dimensions or resolutions? → A: Automatically resize all images to match the smallest common dimension or largest dimension, notify user of the transformation
- Q: How should the system handle displaying stitched images that are too large to fit in memory? → A: Automatically downsample large results for display while saving full resolution to disk
- Q: How should the system respond when encountering corrupted or unreadable image files? → A: Display clear error message and skip file

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load and Visualize MEA Quadrant Images (Priority: P1)

A researcher has captured MEA microscopy data across spatial quadrants (North, South, East, West) and needs to view available images in their correct spatial positions to assess data quality and spatial relationships before stitching. The system supports loading anywhere from one to four quadrant images.

**Why this priority**: This is the foundational capability that enables all subsequent functionality. Researchers must first load and visualize images before any processing can occur.

**Independent Test**: Can be fully tested by loading one to four properly-named image files (containing N/S/E/W keywords) and verifying they appear in the correct quadrant positions. Delivers immediate value by allowing visual inspection of available quadrant data.

**Acceptance Scenarios**:

1. **Given** a directory containing four .czi files with filenames containing "NE", "NW", "SE", "SW" keywords, **When** the user selects these files through the GUI, **Then** each image displays in its corresponding quadrant position (NE=top-right, NW=top-left, SE=bottom-right, SW=bottom-left)

2. **Given** files with mixed case keywords (e.g., "north", "NORTH", "North"), **When** the user loads the files, **Then** the system correctly identifies the spatial location regardless of case

3. **Given** loaded quadrant images, **When** the user zooms or pans in one quadrant, **Then** the zoom/pan level synchronizes across all four quadrants to maintain spatial reference

4. **Given** large microscopy image files (>100MB each), **When** the user loads four images, **Then** loading completes within 10 seconds and memory usage remains under 2GB total

5. **Given** a file with ambiguous keywords (e.g., "Northeast_section" or multiple keywords like "North_South_border"), **When** the user loads the file, **Then** the system displays a dialog prompting the user to manually select the quadrant position (NE, NW, SE, or SW)

6. **Given** a file with no detectable spatial keywords, **When** the user loads the file, **Then** the system prompts the user to manually assign the quadrant position

7. **Given** a corrupted or unreadable image file, **When** the user attempts to load it, **Then** the system displays a clear error message identifying the specific file and the issue (e.g., "Cannot read file: data_NE.czi - file may be corrupted"), and allows the user to continue loading other valid files

---

### User Story 2 - Stitch Four-Quadrant Images into Single Panorama (Priority: P2)

After verifying the four-quadrant images are correctly positioned, the researcher needs to automatically stitch them into a single seamless image for analysis and publication.

**Why this priority**: This is the primary processing operation. Once images are loaded (P1), stitching is the next critical step to create analyzable composite data.

**Independent Test**: Can be tested by loading four overlapping quadrant images, clicking the stitch button, and verifying a seamless composite image appears in a new window. Delivers complete end-to-end stitching workflow.

**Acceptance Scenarios**:

1. **Given** four quadrant images loaded in correct positions, **When** the user clicks the "Stitch Images" button, **Then** the system applies automated stitching and displays the result in a new window within 30 seconds

2. **Given** the stitching operation is in progress, **When** the system processes the images, **Then** a progress bar displays current status (e.g., "Aligning quadrants...", "Blending borders...", "Finalizing...")

3. **Given** a successfully stitched image, **When** displayed in the new window, **Then** the stitched image shows seamless transitions between quadrants with no visible seams or misalignments

4. **Given** images with minimal overlap between quadrants, **When** stitching is attempted, **Then** the system detects insufficient overlap and displays an error message with specific guidance

5. **Given** a completed stitch operation, **When** the user views the result, **Then** the system displays stitching quality metrics (e.g., alignment confidence score, overlap percentage)

6. **Given** only 2 or 3 quadrant images loaded (incomplete set), **When** the user clicks "Stitch Images", **Then** the system stitches available quadrants and interpolates/fills missing quadrant regions with a placeholder pattern or extends adjacent image data

7. **Given** loaded quadrant images with different pixel dimensions (e.g., 2000x2000 and 3000x3000), **When** the user initiates stitching, **Then** the system displays a notification showing original dimensions and the target dimension for resizing, and proceeds with automatic resizing to a common resolution

8. **Given** a stitching operation that produces a very large output (>4GB), **When** the stitched image is ready for display, **Then** the system automatically downsamples the image for in-window display, shows a notification indicating the display is downsampled, and saves the full-resolution version to disk

9. **Given** a downsampled display of a large stitched image, **When** the user views the result window, **Then** the system displays both the current display resolution and the full resolution saved to disk (e.g., "Displaying: 4000x4000, Full resolution saved: 16000x16000")

---

### User Story 3 - Support Multiple Microscopy File Formats (Priority: P3)

Researchers work with various microscopy systems that produce different file formats (.czi, .lsm, .tif/.tiff). The system must handle all common formats without requiring format conversion.

**Why this priority**: Broader format support increases utility across different microscopy platforms. However, core functionality (P1, P2) works with any supported format, so this expands compatibility rather than enabling new workflows.

**Independent Test**: Can be tested by loading four files in different formats (.czi, .lsm, .tif) and verifying they all display and stitch correctly. Delivers value by eliminating manual format conversion steps.

**Acceptance Scenarios**:

1. **Given** a mix of file formats (.czi, .lsm, .tif, .tiff) with NSEW keywords, **When** the user loads files, **Then** all formats display correctly regardless of the format mix

2. **Given** a .lsm file with multiple channels (e.g., fluorescence channels), **When** loaded, **Then** the user can select which channel to display

3. **Given** a .tiff file with embedded metadata, **When** loaded, **Then** the system extracts and displays relevant metadata (pixel size, magnification, acquisition date)

4. **Given** files in unsupported formats, **When** the user attempts to load them, **Then** the system displays a clear error message listing supported formats

---

### Edge Cases

- **Incomplete quadrant sets**: System allows loading 1-3 images and enables stitching; missing quadrants are interpolated or filled with placeholder patterns
- **Ambiguous keywords**: User prompted via dialog to manually assign quadrant position when keywords are ambiguous or multiple keywords detected
- **Missing keywords**: User prompted to manually assign quadrant position when no spatial keywords detected in filename
- **Mismatched dimensions**: System automatically resizes all images to common resolution (smallest or largest dimension) and notifies user of transformation with details
- **Large stitched images (>4GB)**: System automatically downsamples for display while saving full resolution to disk; user notified of display resolution vs. saved resolution
- **Corrupted or unreadable files**: System displays clear error message identifying the specific file and issue, then skips that file and allows loading of other valid files to continue

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect spatial location keywords (N, S, E, W, NE, NW, SE, SW, North, South, East, West) in filenames case-insensitively
- **FR-018**: System MUST prompt user with a quadrant assignment dialog when filenames contain ambiguous keywords, multiple spatial keywords, or no detectable spatial keywords
- **FR-019**: Quadrant assignment dialog MUST show a thumbnail preview of the image and allow user to select from four options: NE, NW, SE, SW
- **FR-002**: System MUST display loaded images in a 2x2 quadrant layout corresponding to their spatial positions, with empty positions for missing quadrants
- **FR-003**: System MUST support loading .czi (Carl Zeiss Image), .lsm (Zeiss Laser Scanning Microscope), .tif, and .tiff file formats
- **FR-028**: System MUST detect corrupted or unreadable image files during loading
- **FR-029**: System MUST display specific error messages identifying which file failed and the reason (file corruption, unsupported format, read permission denied, etc.)
- **FR-030**: System MUST allow loading workflow to continue after encountering a corrupted file, processing remaining valid files
- **FR-004**: Users MUST be able to select and load one to four image files through a file picker dialog
- **FR-005**: System MUST provide synchronized zoom and pan controls across all loaded quadrant views
- **FR-006**: System MUST provide a "Stitch Images" button that becomes enabled when at least one valid quadrant image is loaded
- **FR-016**: System MUST interpolate or fill missing quadrant regions when stitching incomplete sets (1-3 quadrants)
- **FR-017**: System MUST visually indicate which quadrant positions are empty before stitching
- **FR-020**: System MUST automatically detect dimension mismatches between loaded quadrant images
- **FR-021**: System MUST resize all images to a common resolution (largest dimension among loaded images) when dimensions differ
- **FR-022**: System MUST display a notification to the user before stitching showing original dimensions of each image and the target common dimension
- **FR-023**: Resizing operation MUST preserve aspect ratio and use high-quality interpolation (bicubic or better)
- **FR-007**: System MUST use the stitching package to perform automated image alignment and blending
- **FR-008**: System MUST display the stitched result in a new, separate window
- **FR-024**: System MUST detect when stitched output exceeds memory threshold (4GB) and automatically downsample for display
- **FR-025**: System MUST always save the full-resolution stitched image to disk regardless of display downsampling
- **FR-026**: System MUST display a notification when showing downsampled version indicating both display resolution and saved full resolution
- **FR-027**: Downsampling for display MUST preserve aspect ratio and use high-quality interpolation
- **FR-009**: Users MUST be able to save the stitched image to disk in common formats (TIFF, PNG, JPEG)
- **FR-010**: System MUST display a progress indicator during stitching operations
- **FR-011**: System MUST validate that original image files are never modified (read-only operations)
- **FR-012**: System MUST detect and report stitching failures (e.g., insufficient overlap, alignment errors)
- **FR-013**: System MUST display stitching quality metrics after completion (alignment confidence, processing time)
- **FR-014**: Users MUST be able to adjust stitching parameters (blend mode, overlap threshold) through the GUI
- **FR-015**: System MUST save stitching parameters to a configuration file for reproducibility

### Constitution-Aligned Requirements

*Ensure feature requirements align with Image MEA Dulce Constitution:*

- **Data Integrity**: Original image files are opened in read-only mode and never modified. All stitching operations work on in-memory copies. Stitched output is saved as a new file with full metadata documenting source files and parameters.

- **GUI Usability**: File selection via standard file picker dialog. Stitching parameters accessible through labeled sliders and dropdowns with tooltips explaining scientific meaning. Real-time preview of parameter effects on a small region. "Stitch" button clearly labeled with enabling/disabling based on loaded image count.

- **Reproducibility**: All stitching parameters (blend mode, overlap threshold, alignment method, resizing details) are saved to a JSON configuration file alongside the stitched output. Configuration includes source file paths, original and target dimensions, timestamps, software version, and parameter values. Users can load saved configurations to reproduce exact results.

- **Validation**: Stitching quality assessed via alignment confidence scores and overlap analysis. Visual comparison mode allows side-by-side viewing of input quadrants and stitched result. Failed stitching attempts display specific error messages (e.g., "Insufficient overlap between North and South quadrants: found 5%, required minimum 10%").

- **Modularity**: Core stitching logic implemented as standalone library functions accepting explicit parameters (image arrays, alignment method, blend mode). GUI calls library functions without embedding processing logic. Stitching module can be invoked programmatically for batch processing scripts. CLI tool planned for future phase to enable scripting workflows.

### Key Entities

- **QuadrantImage**: Represents a single microscopy image with spatial location (N/S/E/W), file path, pixel dimensions, metadata (magnification, pixel size, acquisition date), and loaded image data (numpy array or equivalent)

- **StitchingConfig**: Configuration parameters including blend mode (linear, multiband, feather), overlap threshold percentage, alignment method (feature-based, phase-correlation), output format, quality settings, and resizing details (original dimensions per quadrant, target common dimension, interpolation method)

- **StitchedResult**: Output of stitching operation containing the composite image data, stitching quality metrics (alignment confidence per border, overlap percentages), processing time, references to source quadrant files, full-resolution dimensions, display-resolution dimensions (if downsampled), and output file path

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can load four quadrant images and view them in correct spatial positions within 15 seconds from file selection
- **SC-002**: Stitching operation completes within 60 seconds for typical MEA images (each quadrant approximately 2000x2000 pixels, 16-bit grayscale)
- **SC-003**: Successfully stitched images show no visible seams or misalignments when viewed at 100% zoom
- **SC-004**: System successfully stitches images with at least 10% overlap between adjacent quadrants
- **SC-005**: Researchers can reproduce identical stitched outputs by reloading saved parameter configurations (pixel-perfect reproducibility)
- **SC-006**: System handles images up to 4000x4000 pixels per quadrant without crashes or excessive memory usage (under 4GB RAM for display)
- **SC-007**: 90% of users successfully complete their first stitching operation without consulting documentation
- **SC-008**: Stitching quality metrics correctly identify problematic alignments (false positive rate <5%)
- **SC-009**: System successfully saves and displays stitched images exceeding 4GB by automatically downsampling for display while preserving full resolution on disk

### Assumptions

- Users have basic familiarity with microscopy file formats and spatial terminology (NSEW)
- Input images follow standard naming conventions that include spatial location keywords
- Microscopy images are captured with sufficient overlap (typically 10-30%) between adjacent quadrants
- Users have microscopy data from MEA experiments that naturally divide into four quadrants
- Processing occurs on standard research workstations (16GB+ RAM, modern multi-core processor)
- Stitching package (e.g., OpenCV stitching module, image-stitching library) is available and compatible with Python/selected platform
- Images are primarily grayscale or single-channel fluorescence data
