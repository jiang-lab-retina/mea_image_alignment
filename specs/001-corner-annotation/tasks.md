# Tasks: Corner Annotation and Square Fit

Branch: 001-corner-annotation  
Spec: specs/001-corner-annotation/spec.md  
Plan: specs/001-corner-annotation/plan.md

## Dependencies (Story Order)

US1 → US2 → US3 → US4 → US5 → US6

- US1 (Tabs) must precede the Corner tab functionality.
- US2 (Load image) precedes annotation and fits.
- US3 (Annotate) precedes manual Fit (US4).
- US5 (Save/Load) can start after US3; completes after US4.
- US6 (Auto-fit) depends on US2 and overlay infra from US4.

## Phase 1: Setup

- [ ] T001 Create feature folder scaffolding if missing (tests/unit|integration, src/gui, src/lib, src/models)

## Phase 2: Foundational

- [ ] T002 [P] Create Corner data models in src/models/corner_annotations.py
- [ ] T003 [P] Create square fitting lib skeleton in src/lib/corner_fit.py
- [ ] T004 [P] Create auto-fit lib skeleton in src/lib/corner_autofit.py
- [ ] T005 [P] Add helper for latest chip-stitched discovery in src/lib/io.py
- [ ] T006 Add Corner tab widget skeleton in src/gui/corner_tab.py (viewport + toolbar placeholders)
- [ ] T007 Prepare tests scaffolding tests/unit/test_corner_fit.py
- [ ] T008 Prepare tests scaffolding tests/unit/test_corner_autofit.py
- [ ] T009 Prepare tests scaffolding tests/integration/test_corner_workflow.py

## Phase 3: US1 - Restructure GUI into tabs (Priority: P1)

Goal: Move existing controls under "Stitch" tab; add "Corner" tab container.

- [ ] T010 [US1] Refactor src/gui/main_window.py to use QTabWidget with "Stitch" (default) and "Corner"
- [ ] T011 [US1] Embed existing stitching UI into a StitchTab container (non-functional move) in src/gui/main_window.py
- [ ] T012 [US1] Insert CornerTab (empty shell) into tabs in src/gui/main_window.py
- [ ] T013 [P] [US1] Ensure actions/shortcuts still route to Stitch tab handlers in src/gui/main_window.py

Independent test: App launches, Stitch tab is default, Corner tab selectable.

## Phase 4: US2 - Load stitched chip image (Priority: P1)

Goal: Load/display stitched chip image with auto-load latest or prompt fallback.

- [ ] T014 [US2] Implement file open and auto-load latest logic in src/gui/corner_tab.py
- [ ] T015 [P] [US2] Add image viewport (QGraphicsView/Scene) with fit-to-window in src/gui/corner_tab.py
- [ ] T016 [P] [US2] Handle grayscale/RGB channel conversions for display in src/gui/corner_tab.py
- [ ] T017 [US2] Add non-blocking progress and error messaging in src/gui/corner_tab.py
- [ ] T018 [P] [US2] Consume latest chip-stitched discovery helper from src/lib/io.py in src/gui/corner_tab.py

Independent test: Latest image auto-loads or prompt appears; pan/zoom responsive.

## Phase 5: US3 - Annotate corners (Priority: P1)

Goal: Click to record corner coordinates; Undo/Clear; min annotation ≥2; Fit requires 4.

- [ ] T019 [US3] Implement mouse click → image pixel coordinate mapping in src/gui/corner_tab.py
- [ ] T020 [P] [US3] Render numbered markers and maintain CornerPoint list in src/gui/corner_tab.py
- [ ] T021 [US3] Implement Undo and Clear with correct re-numbering in src/gui/corner_tab.py
- [ ] T022 [US3] Enforce minimal completeness (≥2 points) with UI indicator in src/gui/corner_tab.py
- [ ] T023 [US3] Gate "Fit Square" enablement at exactly 4 points in src/gui/corner_tab.py

Independent test: Points 1..4 captured, marker list updates, gating works.

## Phase 6: US4 - Fit square and overlay (Priority: P1)

Goal: Fit best-fit square; overlay + metrics; toggle visibility.

- [ ] T024 [US4] Implement fit_square(points) per contract in src/lib/corner_fit.py
- [ ] T025 [P] [US4] Compute residuals and RMS; return SquareFit DTO in src/lib/corner_fit.py
- [ ] T026 [US4] Draw overlay from SquareFit (center, side, rotation) in src/gui/corner_tab.py
- [ ] T027 [P] [US4] Display metrics panel (side length, rotation, residuals, RMS) in src/gui/corner_tab.py
- [ ] T028 [US4] Add overlay toggle; persist state during zoom/pan in src/gui/corner_tab.py

Independent test: With 4 points, overlay and metrics appear; toggle works.

## Phase 7: US5 - Save/Load annotations (Priority: P2)

Goal: Save/Load sidecar JSON using CZI prefix without quadrant; atomic writes.

- [ ] T029 [US5] Implement CornerAnnotationFile serialization/deserialization in src/models/corner_annotations.py
- [ ] T030 [P] [US5] Implement save_annotations/load_annotations in src/lib/io.py
- [ ] T031 [US5] Wire Save/Load buttons; enforce JSON naming rule in src/gui/corner_tab.py
- [ ] T032 [P] [US5] Handle missing/invalid sidecar with clear messaging in src/gui/corner_tab.py

Independent test: Save then reload restores markers and overlay.

## Phase 8: US6 - Auto-fit by intensities (Priority: P2)

Goal: Auto-fit proposal with multi-scale detect/refine, thresholds, Accept/Discard.

- [ ] T033 [US6] Implement auto_fit_square(image, downscale) proposal in src/lib/corner_autofit.py
- [ ] T034 [P] [US6] Compute normalized confidence [0,1] and proposal residuals in src/lib/corner_autofit.py
- [ ] T035 [US6] Apply thresholds (RMS ≤ 2 px AND confidence ≥ 0.7) and label in src/gui/corner_tab.py
- [ ] T036 [P] [US6] Add Accept/Discard interaction and overlay rendering in src/gui/corner_tab.py
- [ ] T037 [US6] Expose configurable downscale factor with a sane default in src/gui/corner_tab.py

Independent test: Auto-fit proposes square; thresholds gate confidence; accept/discard works.

## Phase 9: Polish & Cross-Cutting

- [ ] T038 [P] Dark-mode overlay and marker style tuning in src/gui/corner_tab.py
- [ ] T039 [P] Unit tests for fit and auto-fit metrics in tests/unit/*
- [ ] T040 Integration test for open/annotate/fit/save/reload in tests/integration/test_corner_workflow.py
- [ ] T041 Update quickstart with annotated screenshots in specs/001-corner-annotation/quickstart.md
- [ ] T042 Performance pass (ensure <200 ms auto-fit @4K) in src/lib/corner_autofit.py
- [ ] T043 [P] Validate non-destructive policy: assert no source image writes; atomic JSON saves in tests/integration/test_non_destructive.py
- [ ] T044 Stability soak test: 20 open/annotate/fit/save/reload cycles with metrics logging in tests/integration/test_soak_corner.py

## Parallel Opportunities

- Foundational modules (T002–T005) can progress in parallel.
- Display and channel handling (T015–T016) can run in parallel with file discover (T018).
- Overlay metrics and drawing (T026–T027) can be parallelized.
- Save/Load wiring (T031–T032) can proceed in parallel with serializers (T029–T030) once DTOs stubbed.
- Auto-fit confidence and UI wiring (T034–T037) can parallelize after lib proposal stub exists.

## Implementation Strategy (MVP-first)

1) MVP: US1–US4 to enable manual annotation and fit with overlay + metrics.  
2) Add persistence (US5).  
3) Add auto-fit (US6) and polish.


