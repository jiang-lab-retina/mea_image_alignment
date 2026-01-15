# Implementation Plan: Corner Annotation and Square Fit

**Branch**: `001-corner-annotation` | **Date**: 2025-11-11 | **Spec**: specs/001-corner-annotation/spec.md  
**Input**: Feature specification from `/specs/001-corner-annotation/spec.md`

## Summary

Add a new "Corner" tab (keeping all current UI under "Stitch") to: (1) load a stitched chip image, (2) annotate at least two corners (fit requires 4), (3) fit a best‑fit square with arbitrary rotation and metrics, (4) auto‑fit a square from intensities with thresholds (RMS ≤ 2 px and confidence ≥ 0.7) via a multi‑scale approach, and (5) save/reload annotations to a sidecar JSON named with the source CZI prefix (no quadrant).

## Technical Context

**Language/Version**: Python 3.x  
**Primary Dependencies**: PyQt6 (GUI), NumPy, OpenCV (image ops), tifffile (I/O), pathlib, json  
**Storage**: Files only (stitched images and sidecar JSON)  
**Testing**: pytest for library units; manual GUI validation; synthetic image fixtures for auto‑fit metrics  
**Target Platform**: Desktop (macOS; cross‑platform where possible)  
**Project Type**: Single project (desktop GUI + processing libs)  
**Performance Goals**: UI responsive during interactions; auto‑fit < 200 ms on 4K using multi‑scale; zoom/pan ~60 fps  
**Constraints**: Memory‑safe handling of large TIFF; background threads for long ops; dark‑mode‑safe overlay colors  
**Scale/Scope**: Single‑user desktop usage with very large stitched images

## Constitution Check

- [x] **Data Integrity**: Sidecar JSON; no source image modification; parameters and metrics recorded
- [x] **GUI Design**: Clear controls, tooltips, disabled/enabled states, two‑tab layout
- [x] **Reproducibility**: Pixel coordinates only; JSON naming rule; deterministic fit; config serializable
- [x] **Validation**: Metrics shown (per‑point residuals, RMS, confidence); visual overlay
- [x] **Modularity**: Processing in lib modules callable without GUI; GUI triggers library functions
- [x] **Performance**: Multi‑scale auto‑fit; background ops; responsive viewport
- [x] **Testing**: Unit tests for fit/auto‑fit; synthetic tests; manual GUI checks
- [x] **Documentation**: Quickstart will document workflows and parameters

## Project Structure

### Documentation (this feature)

```text
specs/001-corner-annotation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── spec.md
```

### Source Code (repository root)

```text
src/
├── gui/
│   ├── main_window.py          # add QTabWidget: 'Stitch' (existing), 'Corner' (new)
│   ├── corner_tab.py           # new: viewport, toolbar (Open, Undo, Clear, Fit, Auto-Fit, Save/Load)
│   └── result_window.py
├── lib/
│   ├── corner_fit.py           # new: best‑fit square (LSQ), metrics, overlay geometry
│   ├── corner_autofit.py       # new: multi‑scale intensity‑based proposal + confidence
│   └── io.py
├── models/
│   └── corner_annotations.py   # new: dataclasses for CornerPoint, SquareFit, file schema

tests/
├── unit/
│   ├── test_corner_fit.py
│   └── test_corner_autofit.py
└── integration/
    └── test_corner_workflow.py
```

**Structure Decision**: Extend existing single‑project layout with new GUI tab and library modules; keep processing code out of GUI for modularity and testing.

## Phase 0: Outline & Research (research.md)

Decisions captured: pixel‑only coordinates; JSON naming from CZI prefix; arbitrary rotation; auto‑fit thresholds (RMS/confidence); multi‑scale detection/refinement; minimum annotation (≥2; fitting needs 4). Include brief rationale and alternatives.

## Phase 1: Design & Contracts

- Data model: CornerPoint, CornerAnnotation, SquareFit, CornerAnnotationFile (+ AutoFitResult)
- Contracts (module‑level): function signatures for fit, auto‑fit, persistence; GUI ↔ lib interactions (signals/slots, DTOs)
- Quickstart: steps to load, annotate, fit, auto‑fit, save/load

## Complexity Tracking

N/A (no constitution violations).
