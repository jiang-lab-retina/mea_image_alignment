# Requirements Quality Checklist: Corner Annotation and Square Fit

Purpose: Validate requirement clarity, completeness, consistency, measurability, and coverage (unit tests for English).  
Created: 2025-11-11  
Feature: specs/001-corner-annotation/spec.md

## Requirement Completeness

- [x] CHK001 Are tab structure requirements fully specified (two tabs, default, unchanged Stitch behavior)? [Completeness, Spec §User Story 1, §FR-001]
- [x] CHK002 Are all image load pathways defined (auto-load latest vs prompt, supported formats)? [Completeness, Spec §User Story 2, §FR-002]
- [x] CHK003 Is the minimum annotation definition documented (≥2 points) and its purpose stated? [Completeness, Spec §User Story 3, §FR-015]
- [x] CHK004 Are all actions enumerated (Open, Undo, Clear, Fit, Auto-fit, Save, Load, Overlay toggle)? [Completeness, Spec §User Stories 2–6, §FR-003–FR-014]
- [x] CHK005 Are persistence details complete (file name rule, location, schema contents)? [Completeness, Spec §User Story 5, §FR-009, §Key Entities]
- [x] CHK006 Are performance expectations stated for viewport and auto-fit? [Completeness, Spec §Success Criteria SC-003, §User Story 2]
- [x] CHK007 Are error/empty/low-confidence flows defined for auto-fit and loading? [Completeness, Spec §User Story 6, §Edge Cases, §FR-014]

## Requirement Clarity

- [x] CHK008 Is “auto-load latest chip-stitched image” unambiguous (how “latest” is determined)? [Clarity, Spec §User Story 2]
- [x] CHK009 Is the definition of “minimally complete annotation” precisely stated (UI indication, behavior)? [Clarity, Spec §User Story 3, §FR-015]
- [x] CHK010 Are “fit requires 4 points” constraints explicitly tied to button enablement states? [Clarity, Spec §User Story 3, §FR-005]
- [x] CHK011 Is the JSON sidecar naming rule precise for all prefixes and extensions? [Clarity, Spec §Clarifications, §FR-009]
- [x] CHK012 Is the coordinate system precisely defined (origin, axes directions, integer rounding)? [Clarity, Spec §FR-010]
- [x] CHK013 Is “confidence score” definition clear (range [0,1], components, interpretation)? [Clarity, Spec §FR-014]
- [x] CHK014 Is the multi-scale downscale factor range and default clear? [Clarity, Spec §FR-016]

## Requirement Consistency

- [x] CHK015 Do acceptance scenarios and FRs consistently require 4 points for fitting? [Consistency, Spec §User Story 3–4, §FR-005/FR-006]
- [x] CHK016 Do success criteria align with performance targets in user stories (e.g., 100 ms fit)? [Consistency, Spec §SC-003, §User Story 4/6]
- [x] CHK017 Is pixel-only policy consistently reflected across requirements and entities? [Consistency, Spec §FR-010, §Key Entities, §User Story 5]
- [x] CHK018 Do auto-fit thresholds in acceptance scenarios match FR-014 (RMS ≤ 2 px and confidence ≥ 0.7)? [Consistency, Spec §User Story 6, §FR-014]

## Acceptance Criteria Quality (Measurability)

- [x] CHK019 Are enablement conditions for actions measurable (e.g., Fit enabled at exactly 4 points)? [Measurability, Spec §FR-005]
- [x] CHK020 Are overlay metrics quantitatively defined (side length, rotation, residuals, RMS)? [Measurability, Spec §FR-008]
- [x] CHK021 Are performance targets measurable for responsiveness/latency? [Measurability, Spec §SC-003]
- [x] CHK022 Is the confidence threshold policy objectively verifiable? [Measurability, Spec §FR-014]
- [x] CHK023 Is JSON schema content sufficiently specified for validation (fields, types)? [Measurability, Spec §Key Entities, §FR-009]

## Scenario Coverage

- [x] CHK024 Are zero/partial annotation states covered (0–3 points) with UI behaviors? [Coverage, Spec §User Story 3, §FR-004/FR-005/FR-015]
- [x] CHK025 Are low-contrast/ambiguous images and low-confidence auto-fit flows covered? [Coverage, Spec §User Story 6, §FR-014]
- [x] CHK026 Are large image handling, zoom/pan responsiveness, and memory considerations covered? [Coverage, Spec §User Story 2, §SC-003]
- [x] CHK027 Are Save/Load with missing/invalid sidecar files addressed? [Coverage, Spec §User Story 5, §FR-009]
- [x] CHK028 Is overlay toggle behavior specified across states (no points, manual fit, auto-fit)? [Coverage, Spec §User Story 4, §FR-007]

## Edge Case Coverage

- [x] CHK029 Are clicks outside image bounds covered with expected messaging? [Edge Case, Spec §Edge Cases]
- [x] CHK030 Are near-duplicate points (within 2 px) warnings and outcomes defined? [Edge Case, Spec §Edge Cases]
- [x] CHK031 Are mixed channel images (RGB vs grayscale) and downscale impacts addressed? [Edge Case, Spec §FR-016]
- [x] CHK032 Are concurrent changes (undo after auto-fit, accept/discard while overlay visible) defined? [Edge Case, Spec §User Story 6]

## Non-Functional Requirements

- [x] CHK033 Is background processing and UI responsiveness documented (threading/progress indicators as requirements)? [NFR, Spec §SC-003, Constitution §Performance]
- [x] CHK034 Are dark-mode visuals for overlays and markers specified? [NFR, Spec §FR-012]
- [x] CHK035 Is reproducibility of results across sessions captured (bit-for-bit metrics/overlay)? [NFR, Spec §SC-005, §FR-009]

## Dependencies & Assumptions

- [x] CHK036 Are assumptions about stitched image availability for auto-load explicit? [Assumption, Spec §User Story 2]
- [x] CHK037 Is the source path/provenance for JSON persisted as a requirement? [Assumption/Traceability, Spec §Key Entities]

## Ambiguities & Conflicts

- [x] CHK038 Is “latest” chip-stitched image selection rule free from ambiguity? [Ambiguity, Spec §User Story 2]
- [x] CHK039 Are overlay styles (color, thickness, z-order) unambiguous in dark mode? [Ambiguity, Spec §FR-012]
- [x] CHK040 Do any acceptance scenarios conflict with FR gating (e.g., enabling Fit with <4 points)? [Conflict, Spec §User Story 3–4, §FR-005]


