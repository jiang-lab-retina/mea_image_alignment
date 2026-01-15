# Contracts: Corner Annotation and Square Fit

## Library Interfaces

### fit_square(points: list[tuple[int,int]]) -> SquareFit
- Input: exactly 4 image-space points [(x,y) ...]
- Output: SquareFit (center, side_length, rotation_degrees, corners, residuals_px, rms_residual_px)
- Errors: ValueError if len(points) != 4

### auto_fit_square(image: np.ndarray, downscale: float=0.5) -> tuple[SquareFit, float]
- Input: grayscale or RGB image; downscale in (0,1]
- Output: (proposal: SquareFit, confidence: float in [0,1])
- Notes: Multi-scale detection (downscaled) with full-res refinement

### save_annotations(json_path: Path, data: CornerAnnotationFile) -> None
- Behavior: Atomic write; create parent dirs if missing

### load_annotations(json_path: Path) -> CornerAnnotationFile
- Behavior: Validates schema and version; returns parsed structure

## GUI ↔ Library Contracts

- CornerTab emits signals:
  - pointsChanged(points: list[CornerPoint])
  - fitRequested()
  - autoFitRequested(downscale: float)
  - saveRequested(json_path: str)
  - loadRequested(json_path: str)

- Library returns DTOs conforming to data-model.md; GUI renders overlays accordingly.

## Threshold Policy (Auto-Fit)
- Accept as “confident” only if:
  - rms_residual_px ≤ 2.0
  - confidence ≥ 0.7
- Otherwise, label proposal “low confidence”; do not block manual tools.


