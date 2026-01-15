# Research: Corner Annotation and Square Fit

## Decisions

- Pixel coordinate system only (no micron conversion)
  - Rationale: Avoids metadata dependencies; preserves source-of-truth positions.
  - Alternatives: Optional micron display; forced micron entry (rejected as unnecessary).

- JSON sidecar naming from CZI prefix (no quadrant), e.g., `<prefix>.json`
  - Rationale: Groups artifacts by logical acquisition prefix; simple discovery.
  - Alternatives: Timestamped names; embed quadrant; store in central dir.

- Square orientation: arbitrary rotation
  - Rationale: Matches real-world placements; avoids bias to axes.
  - Alternatives: Axis-aligned; discrete angles.

- Auto-fit thresholds: RMS ≤ 2 px AND confidence ≥ 0.7
  - Rationale: Combines geometric residual with normalized confidence to gate acceptance.
  - Alternatives: Either metric alone; no threshold (too permissive).

- Auto-fit resolution strategy: multi-scale (downscale detect, full-res refine)
  - Rationale: Balances speed and accuracy on large stitched images.
  - Alternatives: Full-res only (slow); downscale only (less accurate).

- Minimum annotation: ≥2 corners labeled; fit requires exactly 4
  - Rationale: Allows partial progress and save; geometric fit needs 4 constraints.

## Notes

- Confidence definition: normalized [0, 1] score combining edge consistency, symmetry, and contour fit.
- Performance target: auto-fit under 200 ms on typical 4K images using downscale 0.25–0.5×.


