import numpy as np
import pandas as pd
import pytest
from core import expected as ex


@pytest.mark.parametrize("ev,la,lo,hi", [
    (100, 28, 0.85, 3.0),    # barrel: piso alto
    (95, 15, 0.57, 0.73),    # línea dura
    (89, 12, 0.29, 0.45),    # contacto promedio
    (70, -5, 0.0, 0.20),     # roletazo débil
    (80, 50, 0.0, 0.10),     # popup
])
def test_anchors(ev, la, lo, hi):
    assert lo <= ex.xwoba_contact(ev, la) <= hi


def test_probs_valid_over_grid():
    for ev in range(40, 121, 5):
        for la in range(-40, 61, 5):
            p = ex.base_outcome_probs(ev, la)
            assert p.shape == (5,)
            assert (p >= -1e-9).all()
            assert abs(p.sum() - 1.0) < 1e-6


def test_monotonic_ev_in_line_band():
    xs = [ex.xwoba_contact(ev, 18) for ev in (80, 90, 100, 108)]
    assert xs == sorted(xs)


def test_popup_worse_than_line_same_ev():
    assert ex.xwoba_contact(95, 50) < ex.xwoba_contact(95, 15)
