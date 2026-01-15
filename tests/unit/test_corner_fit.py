import math
from src.lib.corner_fit import fit_square


def test_fit_square_returns_result_for_four_points():
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    fit = fit_square(pts)
    assert fit.side_length > 0
    assert len(fit.corners) == 4
    assert fit.rms_residual_px >= 0


def test_fit_square_requires_four_points():
    try:
        fit_square([(0, 0), (1, 1), (2, 2)])
        assert False, "Expected ValueError"
    except ValueError:
        assert True


