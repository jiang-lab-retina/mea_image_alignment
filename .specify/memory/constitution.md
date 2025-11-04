# Image MEA Dulce Constitution

<!--
SYNC IMPACT REPORT
==================
Version Change: INITIAL → 1.0.0
Modified Principles: N/A (Initial creation)
Added Sections:
  - Core Principles (5 principles)
  - Performance Standards
  - Development Workflow
  - Governance
Removed Sections: N/A
Templates Status:
  ✅ plan-template.md - Reviewed, compatible with constitution
  ✅ spec-template.md - Reviewed, compatible with constitution
  ✅ tasks-template.md - Reviewed, compatible with constitution
Follow-up TODOs: None
-->

## Core Principles

### I. Data Integrity First

**NON-NEGOTIABLE**: Preservation of scientific data integrity throughout all processing stages.

- Original raw data (.czi files) MUST never be modified; all processing operates on copies
- All transformations MUST be reversible or documented with full parameter tracking
- Processing pipelines MUST validate input data format and integrity before processing
- Output data MUST include metadata documenting all processing steps applied
- Any data loss or quality degradation MUST be explicitly detected and reported to the user

**Rationale**: Scientific research depends on trustworthy data. Any compromise in data integrity
invalidates experimental results and conclusions. This principle ensures reproducibility and
scientific rigor.

### II. User-Friendly GUI Design

All user-facing functionality MUST be accessible through an intuitive graphical interface.

- Parameter input MUST use appropriate UI controls (sliders, dropdowns, text fields) with
  clear labels and tooltips
- Real-time preview MUST be provided where computationally feasible to help users understand
  parameter effects
- Parameter validation MUST happen immediately with clear error messages
- The GUI MUST save and load parameter configurations for reproducibility
- Common workflows MUST be accessible within 3 clicks or less

**Rationale**: Scientists are domain experts, not necessarily programmers. An intuitive GUI
lowers barriers to adoption and reduces errors from manual parameter entry.

### III. Reproducible Processing

**NON-NEGOTIABLE**: Every processing operation MUST be fully reproducible.

- All processing functions MUST accept explicit parameters (no hidden global state)
- Random operations MUST use settable seeds
- Processing configurations MUST be serializable to human-readable formats (JSON/YAML)
- Each processing output MUST be accompanied by a parameter manifest documenting:
  - Software version
  - All processing parameters
  - Input file paths
  - Timestamp
- Batch processing MUST apply identical parameters to all items unless explicitly varied

**Rationale**: Scientific reproducibility is fundamental. Researchers must be able to recreate
results exactly, and document methods for publication and peer review.

### IV. Validation & Quality Control

Processing results MUST include automated quality assessment and validation.

- Alignment algorithms MUST report confidence metrics or quality scores
- The system MUST detect and flag potential alignment failures
- Users MUST be able to visually inspect results with before/after comparisons
- Statistical summaries of processed data MUST be automatically generated
- Edge cases and boundary conditions MUST be tested during development

**Rationale**: Automated processing can introduce subtle errors. Built-in validation catches
problems early and builds user confidence in results.

### V. Modular Architecture

Processing logic MUST be decoupled from user interface implementation.

- Core image processing algorithms MUST be implemented as standalone library functions
- GUI components MUST call library functions without embedding processing logic
- Each processing module (alignment, transformation, analysis) MUST be independently testable
- Library functions MUST work via programmatic API (enabling scripting/automation)
- CLI tools SHOULD be provided alongside GUI for advanced users and batch processing

**Rationale**: Separation of concerns enables testing, reuse, and maintenance. Scientists may
want to script workflows or integrate processing into pipelines without the GUI.

## Performance Standards

Given the large size of microscopy image data (.czi files):

- **Memory Efficiency**: Processing MUST handle images larger than available RAM using
  chunking/streaming where applicable
- **Progress Feedback**: Operations taking >2 seconds MUST show progress indicators
- **Responsive UI**: GUI MUST remain responsive during processing (use background threads/processes)
- **Batch Processing**: System MUST support processing multiple files without manual intervention
- **File Format Support**: Native support for .czi format is required; additional formats
  (TIFF, PNG, etc.) are desired for flexibility

## Development Workflow

### Code Quality

- All processing functions MUST have docstrings documenting parameters, returns, and purpose
- Type hints MUST be used for all function signatures in Python 3.7+ style
- Code MUST pass linting (flake8/pylint) and formatting (black/autopep8) checks
- Complex algorithms MUST include inline comments explaining the approach

### Testing Requirements

- **Unit Tests**: Core processing functions MUST have unit tests with known-good reference data
- **Integration Tests**: GUI workflows MUST be tested (manual or automated UI testing)
- **Validation Testing**: Test with real experimental data to ensure scientific validity
- Test data SHOULD include edge cases (empty images, corrupted files, extreme parameters)

### Version Control

- Use semantic versioning (MAJOR.MINOR.PATCH)
- Commit messages MUST follow conventional commits format
- Breaking changes to processing algorithms MUST bump MAJOR version
- New features (GUI additions, new algorithms) MUST bump MINOR version
- Bug fixes and performance improvements MUST bump PATCH version

### Documentation

- README MUST include installation instructions, quick start guide, and basic usage
- Parameter documentation MUST explain scientific meaning and recommended ranges
- Architecture documentation MUST maintain diagrams of processing pipeline
- Release notes MUST document changes in each version

## Governance

This constitution defines the architectural and quality standards for the Image MEA Dulce project.

### Amendment Process

- Constitution amendments MUST be documented in git history with rationale
- Breaking changes to core principles MUST be discussed before implementation
- Version number MUST be updated following semantic versioning:
  - MAJOR: Incompatible principle changes, removed principles
  - MINOR: New principles added, significant expansions
  - PATCH: Clarifications, wording improvements, typo fixes

### Compliance

- All feature implementations MUST verify compliance with constitution principles
- Code reviews MUST check adherence to principles (data integrity, reproducibility, modularity)
- Any deviation from principles MUST be explicitly justified in documentation
- Constitution supersedes ad-hoc decisions in case of conflict

### Constitution Maintenance

- Constitution MUST be reviewed during major feature additions
- Outdated principles MUST be updated or removed
- New challenges SHOULD prompt principle additions if recurring issues emerge

**Version**: 1.0.0 | **Ratified**: 2025-11-04 | **Last Amended**: 2025-11-04
