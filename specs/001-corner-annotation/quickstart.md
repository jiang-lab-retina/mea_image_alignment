# Quickstart: Corner Annotation and Square Fit

1) Open the app (dark mode). Confirm “Stitch” tab loads as before.
2) Switch to “Corner” tab.
3) Image loading:
   - The latest chip-stitched image auto-loads if available; otherwise click “Open Image…”.
4) Annotate corners:
   - Click to add points (1..4). Minimal: ≥2 points. Fit requires 4 points.
   - Use “Undo” or “Clear” to edit points.
5) Fit Square:
   - Enabled at exactly 4 points. Shows overlay + metrics (side length, rotation, residuals, RMS).
6) Auto-fit Square:
   - Click “Auto-fit Square” to propose a square from intensities.
   - Acceptance thresholds: RMS ≤ 2 px and confidence ≥ 0.7 (multi-scale detect/refine).
   - Accept to apply as current fit or Discard to ignore.
7) Save/Load Annotations:
   - Saves JSON sidecar named from the CZI prefix (no quadrant): `<prefix>.json`.
   - Load to restore points and fit overlay.


