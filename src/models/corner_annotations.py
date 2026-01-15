from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class CornerPoint:
    index: int  # 1..4
    x: int
    y: int


@dataclass
class SquareFit:
    center_x: float
    center_y: float
    side_length: float
    rotation_degrees: float
    corners: List[CornerPoint]
    residuals_px: List[float]
    rms_residual_px: float
    confidence: float = 0.0  # 0..1, used for auto-fit


@dataclass
class CornerAnnotation:
    image_path: str
    points: List[CornerPoint] = field(default_factory=list)  # 0..4; minimal at ≥2; fit requires 4
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CornerAnnotationFile:
    version: str
    image_path: str
    points: List[CornerPoint]
    fit: Optional[SquareFit]
    created_at: datetime
    provenance: Dict[str, Any] = field(default_factory=dict)


def corner_annotation_file_to_dict(caf: CornerAnnotationFile) -> Dict[str, Any]:
    def point_to_dict(p: CornerPoint) -> Dict[str, Any]:
        return {"index": p.index, "x": p.x, "y": p.y}

    def fit_to_dict(f: SquareFit) -> Dict[str, Any]:
        return {
            "center_x": f.center_x,
            "center_y": f.center_y,
            "side_length": f.side_length,
            "rotation_degrees": f.rotation_degrees,
            "corners": [point_to_dict(cp) for cp in f.corners],
            "residuals_px": list(f.residuals_px),
            "rms_residual_px": f.rms_residual_px,
            "confidence": f.confidence,
        }

    return {
        "version": caf.version,
        "image_path": caf.image_path,
        "points": [point_to_dict(p) for p in caf.points],
        "fit": None if caf.fit is None else fit_to_dict(caf.fit),
        "created_at": caf.created_at.isoformat(),
        "provenance": caf.provenance or {},
    }


def corner_annotation_file_from_dict(payload: Dict[str, Any]) -> CornerAnnotationFile:
    def point_from_dict(d: Dict[str, Any]) -> CornerPoint:
        return CornerPoint(index=int(d["index"]), x=int(d["x"]), y=int(d["y"]))

    def fit_from_dict(d: Dict[str, Any]) -> SquareFit:
        return SquareFit(
            center_x=float(d["center_x"]),
            center_y=float(d["center_y"]),
            side_length=float(d["side_length"]),
            rotation_degrees=float(d["rotation_degrees"]),
            corners=[point_from_dict(cp) for cp in d.get("corners", [])],
            residuals_px=[float(v) for v in d.get("residuals_px", [])],
            rms_residual_px=float(d["rms_residual_px"]),
            confidence=float(d.get("confidence", 0.0)),
        )

    fit_dict = payload.get("fit")
    created_at_str = payload.get("created_at")
    return CornerAnnotationFile(
        version=str(payload.get("version", "1.0")),
        image_path=str(payload.get("image_path", "")),
        points=[point_from_dict(p) for p in payload.get("points", [])],
        fit=None if fit_dict is None else fit_from_dict(fit_dict),
        created_at=datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(),
        provenance=payload.get("provenance", {}),
    )


