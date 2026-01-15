# Data Model: Corner Annotation and Square Fit

## Entities

### CornerPoint
- index: int (1..4)
- x: int
- y: int

### SquareFit
- center_x: float
- center_y: float
- side_length: float
- rotation_degrees: float
- corners: CornerPoint[4]
- residuals_px: float[4]
- rms_residual_px: float
- confidence: float (0..1, for auto-fit)

### CornerAnnotation
- image_path: string
- points: CornerPoint[] (0..4; minimally complete at ≥2; fit requires 4)
- created_at: datetime

### CornerAnnotationFile (JSON)
- version: string
- image_path: string
- points: CornerPoint[<=4]
- fit: SquareFit | null
- created_at: datetime
- provenance:
  - source_czi_prefix: string (no quadrant)
  - stitched_image_path: string
  - thresholds: { rms_px: float, confidence_min: float }
  - resolution_strategy: { mode: "multiscale", downscale: float }

## Validation Rules
- CornerPoint indices unique and within 1..4.
- points length in {0,1,2,3,4}; minimal at ≥2; fit only if length==4.
- rotation_degrees in [-180, 180].
- confidence in [0, 1].
- thresholds.rms_px ≤ 2 and confidence_min ≥ 0.7 to mark fit “confident”.


