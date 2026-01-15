import numpy as np
from src.lib.corner_autofit import auto_fit_square


def test_auto_fit_square_on_blank_image():
    img = np.zeros((100, 100), dtype=np.uint8)
    proposal, conf = auto_fit_square(img, downscale=0.5)
    assert proposal is not None
    assert 0.0 <= conf <= 1.0


