from pathlib import Path
import numpy as np

from src.lib.corner_fit import fit_square
from src.lib.corner_autofit import auto_fit_square


def test_corner_workflow_basic():
    # Manual fit path
    pts = [(0, 0), (20, 0), (20, 20), (0, 20)]
    fit = fit_square(pts)
    assert fit.side_length > 0

    # Auto-fit path on synthetic
    img = np.zeros((50, 50), dtype=np.uint8)
    proposal, conf = auto_fit_square(img, downscale=0.5)
    assert proposal is not None
    assert 0.0 <= conf <= 1.0


