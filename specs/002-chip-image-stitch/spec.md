# Feature Specification: Chip Image Stitching with Alignment Reuse

**Feature Branch**: `002-chip-image-stitch`  
**Created**: 2025-11-05  
**Status**: Draft  
**Input**: User description: "Add a new button 'Stitch chip image' It will be gray out before stitch images and works after finished the stitch image. It will apply the position shifts of x any y axis of the first stitching to stitch the chip images. Find the chip images automatically, according to file name: for example: 2025.10.22-09.58.50-4141-opnT2_chipNE.czi will be correspond to 2025.10.22-09.58.50-4141-opnT2_NE.czi. if the no corresponding image is found, use black with the same dimension as the other."

## Clarifications

### Session 2025-11-05

- Q: Should alignment parameters be saved to disk for later reuse, or only kept in memory during the current application session? → A: Persistent storage - Parameters saved to disk (e.g., JSON file alongside stitched images), can be reloaded later, enabling chip stitching in future sessions
- Q: What color/pattern should placeholder images use to clearly indicate missing data? → A: Pure black (RGB: 0, 0, 0) for missing chip image placeholders
- Q: How should the system handle chip images with mismatched dimensions? → A: Resize to match original quadrant dimensions - Scale chip images to the dimensions of their corresponding original images before applying position shifts to ensure alignment accuracy
- Q: When should the system notify users about chip image dimension mismatches? → A: Both - Show preview notification with dimension details and option to proceed or cancel before starting, and include dimension transformation details in final result metadata
- Q: What validation checks should be performed on loaded alignment parameter files? → A: Comprehensive validation - Check file format (valid JSON/parseable), verify all required parameter fields are present (quadrant positions, dimensions), and confirm referenced original image files still exist at expected paths

## User Scenarios & Testing

### User Story 1 - Enable Chip Image Stitching After Initial Stitching (Priority: P1)

After completing the initial quadrant stitching, the researcher needs the ability to stitch a second set of related "chip" images using the exact same spatial alignment parameters, eliminating the need to re-compute feature matching and alignment.

**Why this priority**: This is the core enabling functionality. The button must become available at the right time (after initial stitching completes) and remain disabled until then. This is the foundation that all other chip stitching functionality depends on.

**Independent Test**: Can be fully tested by verifying the "Stitch Chip Images" button is disabled on application start, loading and stitching quadrant images, then verifying the button becomes enabled. Delivers immediate value by providing clear UI state management.

**Acceptance Scenarios**:

1. **Given** the application has just launched and no images have been loaded, **When** the user views the main window, **Then** the "Stitch Chip Images" button is visible but grayed out (disabled)

2. **Given** quadrant images have been loaded but not yet stitched, **When** the user views the main window, **Then** the "Stitch Chip Images" button remains grayed out (disabled)

3. **Given** quadrant images have been successfully stitched, **When** the stitching operation completes, **Then** the "Stitch Chip Images" button becomes enabled (no longer grayed out)

4. **Given** the "Stitch Chip Images" button is enabled after a successful stitch, **When** the user loads a new set of quadrant images (starting a new session), **Then** the button becomes disabled again until the new images are stitched

5. **Given** a stitching operation fails with an error, **When** the error is displayed, **Then** the "Stitch Chip Images" button remains disabled

6. **Given** the application is launched and a directory containing saved alignment parameters from a previous session is accessed, **When** the system detects the parameter file, **Then** the "Stitch Chip Images" button becomes enabled if the parameters are valid and corresponding original images can be located

7. **Given** a saved alignment parameter file exists but is corrupted (invalid JSON format), **When** the system attempts to load it, **Then** a warning displays indicating "Parameter file is corrupted or unreadable" and the "Stitch Chip Images" button remains disabled

8. **Given** a saved alignment parameter file exists but is missing required fields (e.g., missing quadrant dimensions), **When** the system validates the file, **Then** a warning displays indicating "Parameter file is incomplete - missing required fields" and the "Stitch Chip Images" button remains disabled

9. **Given** a saved alignment parameter file references original images that no longer exist at their expected paths, **When** the system validates the file, **Then** a warning displays indicating "Referenced original images not found" with the list of missing files, and the "Stitch Chip Images" button remains disabled

---

### User Story 2 - Automatically Locate and Load Chip Images (Priority: P2)

When the researcher clicks "Stitch Chip Images", the system must automatically discover corresponding chip image files by analyzing the original quadrant filenames and searching for files with the "_chip" naming pattern in the same directory.

**Why this priority**: This is the second critical step after enabling the button. Automatic file discovery eliminates manual file selection and ensures the correct correspondence between original and chip images. This enables the core workflow but depends on P1 being complete.

**Independent Test**: Can be tested by creating matching pairs of files (e.g., `sample_NE.czi` and `sample_chipNE.czi`), stitching the original quadrant images, clicking "Stitch Chip Images", and verifying the system automatically finds and processes the chip images. Delivers value by automating file discovery.

**Acceptance Scenarios**:

1. **Given** original quadrant images named `2025.10.22-09.58.50-4141-opnT2_NE.czi`, `2025.10.22-09.58.50-4141-opnT2_NW.czi`, `2025.10.22-09.58.50-4141-opnT2_SE.czi`, `2025.10.22-09.58.50-4141-opnT2_SW.czi` have been stitched, **When** the user clicks "Stitch Chip Images", **Then** the system searches for and finds `2025.10.22-09.58.50-4141-opnT2_chipNE.czi`, `2025.10.22-09.58.50-4141-opnT2_chipNW.czi`, `2025.10.22-09.58.50-4141-opnT2_chipSE.czi`, `2025.10.22-09.58.50-4141-opnT2_chipSW.czi` in the same directory

2. **Given** the original filename pattern `[prefix]_[quadrant].[ext]`, **When** searching for chip images, **Then** the system looks for files matching `[prefix]_chip[quadrant].[ext]` (inserting "chip" before the quadrant identifier without an underscore)

3. **Given** only some chip images exist (e.g., chipNE and chipNW files present but chipSE and chipSW missing), **When** the system searches for chip images, **Then** the system successfully loads the available chip images and proceeds with stitching

4. **Given** chip image files exist but are in a different directory than the original images, **When** the user clicks "Stitch Chip Images", **Then** the system displays a notification that chip images were not found and shows the expected filename patterns

5. **Given** no chip images are found matching any of the quadrants, **When** the user clicks "Stitch Chip Images", **Then** the system displays an error message listing the expected chip image filenames and their locations

6. **Given** chip image files have different file extensions than the originals (e.g., originals are .czi but chip files are .tif), **When** searching for chip images, **Then** the system searches for chip images with the same extension as each corresponding original image

---

### User Story 3 - Apply Original Alignment to Chip Images (Priority: P3)

The system must reuse the exact X and Y position shifts (translation parameters) from the original quadrant stitching to align chip images, bypassing feature detection and matching. For missing chip images, the system generates black placeholder images with matching dimensions.

**Why this priority**: This is the actual stitching operation that delivers the final result. It depends on both P1 (button enablement) and P2 (file discovery) being complete. The alignment reuse is the key value proposition that saves computation time and ensures consistency.

**Independent Test**: Can be tested by stitching original quadrant images, noting their alignment parameters, stitching chip images, and verifying the chip images use identical position shifts. Delivers complete end-to-end chip stitching with alignment reuse.

**Acceptance Scenarios**:

1. **Given** original quadrant images have been stitched with specific X and Y position shifts (e.g., NE shifted +50px X, +30px Y relative to NW), **When** chip images are stitched, **Then** the system applies the exact same X and Y position shifts to the corresponding chip images

2. **Given** the original stitching used translation parameters [dx_NE, dy_NE, dx_NW, dy_NW, dx_SE, dy_SE, dx_SW, dy_SW], **When** chip images are stitched, **Then** the system applies these exact parameters without recalculating feature matches or running alignment algorithms

3. **Given** one or more chip images are missing (e.g., chipSE.czi does not exist), **When** the chip stitching operation runs, **Then** the system creates a pure black placeholder image matching the dimensions of the corresponding original quadrant image and places it in the corresponding quadrant position

4. **Given** all chip images are present and stitching is initiated, **When** the operation progresses, **Then** a progress dialog displays current status (e.g., "Loading chip images...", "Applying alignment...", "Generating composite...")

5. **Given** chip images have different dimensions than the original quadrant images, **When** the user initiates chip stitching, **Then** the system displays a preview notification showing which chip images will be resized (with original and target dimensions) and provides options to proceed or cancel; if the user proceeds, resizing occurs and dimension details are included in the final result metadata

5a. **Given** the system displays a dimension mismatch preview notification, **When** the user chooses to cancel, **Then** the stitching operation does not proceed and the user is returned to the main window

6. **Given** the chip stitching operation completes successfully, **When** the result is ready, **Then** the stitched chip image displays in a new window, similar to the original stitch result window

7. **Given** the chip stitching operation completes successfully, **When** the result window opens, **Then** the system displays metadata including: number of chip images found, number of placeholders generated, processing time, and reference to the original stitching session

8. **Given** chip images were resized during the stitching operation, **When** the result window opens, **Then** the system displays dimension transformation details showing which images were resized and their original vs. final dimensions

9. **Given** chip images have significantly different content or exposure than original images, **When** stitching is applied, **Then** the alignment still works correctly because position shifts are reused (feature matching is not performed)

---

### Edge Cases

- **All chip images missing**: System displays error with expected filenames; stitching does not proceed unless user has explicitly requested placeholder-only stitching
- **Chip images with different pixel dimensions**: System automatically resizes chip images to match their corresponding original quadrant dimensions before applying position shifts, ensuring alignment accuracy; user is notified of dimension transformations
- **Mixed presence of chip images**: System uses black placeholders for missing quadrants, sizing each placeholder to match its corresponding original quadrant dimensions
- **Original stitching had only 2-3 quadrants**: System searches for chip images only for the quadrants that were present in the original stitching
- **User loads new images after chip stitching**: System disables "Stitch Chip Images" button until new quadrant images are stitched, ensuring alignment parameters are always from the current session
- **Chip images are corrupted or unreadable**: System displays error identifying the specific chip file and offers to proceed with a black placeholder for that quadrant
- **Different file formats for chip vs. original**: System supports chip images in different formats (.czi, .lsm, .tif) than the original quadrants
- **Saved alignment parameters exist from previous session**: System automatically detects and loads saved parameters; button becomes enabled if parameters are valid and corresponding original image files can be located
- **Stale or corrupted alignment parameter file**: System performs comprehensive validation (file format, parameter completeness, image file existence); displays specific warning indicating which validation failed; "Stitch Chip Images" button remains disabled until valid parameters are available; user can proceed with fresh stitching
- **Multiple parameter files in directory**: System uses the most recently modified parameter file that matches the current working set of images

## Requirements

### Functional Requirements

- **FR-001**: System MUST display a "Stitch Chip Images" button in the main window toolbar or menu bar
- **FR-002**: System MUST disable the "Stitch Chip Images" button by default when the application starts
- **FR-003**: System MUST disable the "Stitch Chip Images" button when new quadrant images are loaded (before stitching)
- **FR-004**: System MUST enable the "Stitch Chip Images" button immediately after a successful quadrant stitching operation completes
- **FR-005**: System MUST keep the "Stitch Chip Images" button disabled if quadrant stitching fails or is cancelled
- **FR-006**: System MUST store the X and Y position shift parameters (translation vectors) from the original quadrant stitching operation to disk in a structured format (e.g., JSON file)
- **FR-006a**: System MUST save alignment parameters in the same directory as the stitched image output, using a related filename (e.g., `stitched_result.tiff` → `stitched_result_alignment.json`)
- **FR-006b**: System MUST include original quadrant image dimensions (width and height for each quadrant) in the saved alignment parameters
- **FR-006c**: System MUST enable the "Stitch Chip Images" button when valid saved alignment parameters are detected, even if parameters were generated in a previous application session
- **FR-006d**: System MUST load and validate saved alignment parameters automatically when the application starts or when the user navigates to a directory containing parameter files
- **FR-006e**: System MUST perform comprehensive validation on alignment parameter files including: (1) file format validation (parseable JSON), (2) parameter completeness validation (all required fields present: quadrant positions, dimensions, translation vectors), (3) referenced image file existence validation (original image files still exist at expected paths)
- **FR-006f**: System MUST display a warning message if alignment parameter file validation fails, indicating the specific validation error (corrupted file, missing fields, or missing original image files)
- **FR-006g**: System MUST keep the "Stitch Chip Images" button disabled if alignment parameter validation fails, preventing use of invalid parameters
- **FR-007**: System MUST automatically determine chip image filenames by inserting "chip" immediately before the quadrant identifier in the original filename (e.g., `prefix_NE.ext` → `prefix_chipNE.ext`)
- **FR-008**: System MUST search for chip images in the same directory as the original quadrant images
- **FR-009**: System MUST search for chip images with the same file extension as each corresponding original image
- **FR-010**: System MUST support chip images in all formats supported by the original quadrant stitching (.czi, .lsm, .tif, .tiff)
- **FR-011**: System MUST load all available chip images that match the expected naming pattern
- **FR-012**: System MUST notify the user if no chip images are found and display the expected filenames
- **FR-013**: System MUST proceed with chip stitching even if only a subset of chip images are found
- **FR-014**: System MUST generate pure black (RGB: 0, 0, 0) placeholder images for missing chip images
- **FR-015**: System MUST resize chip images to match the dimensions of their corresponding original quadrant images before applying alignment parameters
- **FR-015a**: System MUST size placeholder images to match the dimensions of their corresponding original quadrant images
- **FR-015b**: System MUST display a preview notification before starting chip stitching if any chip images require resizing, showing original dimensions, target dimensions, and providing options to proceed or cancel
- **FR-015c**: System MUST include dimension transformation details (which images were resized, from what dimensions to what dimensions) in the chip stitching result metadata
- **FR-016**: System MUST apply the stored position shifts from the original stitching to align chip images without performing feature detection or matching
- **FR-017**: System MUST display a progress dialog during chip image stitching showing current operation status
- **FR-018**: System MUST display the stitched chip image in a new result window upon successful completion
- **FR-019**: System MUST display chip stitching metadata including: chip images found, placeholders generated, dimension transformations performed, processing time, and reference to original stitching session
- **FR-020**: System MUST allow the user to save the stitched chip image to disk in common formats (.tiff, .png)
- **FR-021**: System MUST handle errors gracefully (corrupted chip files, permission issues) by displaying clear error messages and offering to continue with placeholders

### Constitution-Aligned Requirements

- **Data Integrity**: Original chip image files must never be modified; all stitching operations work on in-memory copies; if chip images cannot be read, the operation halts with clear error reporting; black placeholders are explicitly labeled in logs and metadata
- **GUI Usability**: The "Stitch Chip Images" button provides clear visual feedback (disabled state is clearly distinguishable from enabled state); users receive notifications about chip image discovery results before processing begins; progress dialogs keep users informed during potentially long operations
- **Reproducibility**: The system stores the complete set of position shift parameters from the original stitching; chip stitching results include metadata linking back to the original stitching session; users can reproduce chip stitching by running the same operation on the same original + chip image sets
- **Validation**: The system reports which chip images were found vs. which used placeholders; the result window displays alignment parameters used; processing logs capture all file discovery and alignment operations for quality assurance
- **Modularity**: The chip image file discovery logic must be independent of the GUI (callable from CLI or scripts); the alignment application logic must work without requiring feature detection libraries; position shift parameters must be serializable and loadable independently

### Key Entities

- **ChipImageSet**: Represents the collection of chip images corresponding to a stitched quadrant set, including discovered files, missing quadrants, and placeholder indicators
- **AlignmentParameters**: The stored X and Y position shifts (translation vectors) from the original quadrant stitching, including per-quadrant offsets, reference frame, original quadrant image dimensions for each quadrant, and file paths to the original images for validation purposes
- **ChipStitchResult**: The output of chip stitching, including the composite image, metadata about source files, placeholder usage, and reference to the original stitching session
- **PlaceholderImage**: A generated pure black (RGB: 0, 0, 0) image used when a corresponding chip image is not found, with dimensions matching the corresponding original quadrant image

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can initiate chip image stitching within 1 click after completing the original quadrant stitching
- **SC-002**: The system automatically discovers chip images in under 2 seconds for directories containing up to 100 files
- **SC-003**: Chip image stitching completes in 50% less time than original quadrant stitching (measured on the same hardware and image sizes) due to bypassing feature detection
- **SC-004**: The system successfully handles partial chip image sets (1-3 chip images found) and generates appropriate placeholders 100% of the time
- **SC-005**: Users can clearly distinguish between enabled and disabled states of the "Stitch Chip Images" button without reading documentation
- **SC-006**: The chip stitching result window displays clear metadata indicating which images were found vs. placeholders, with 100% accuracy
- **SC-007**: The system applies position shifts with pixel-perfect accuracy (±0 pixels) compared to the original stitching alignment
- **SC-008**: Users can complete the full workflow (original stitching → chip stitching → save result) in under 3 minutes for typical image sets (4 quadrants, ~100MB each)
