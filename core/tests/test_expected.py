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


def _bb_df():
    # 3 batazos (2 buenos, 1 débil) + 1 K + 1 BB → PA=5
    return pd.DataFrame({
        "PitchCall": ["InPlay", "InPlay", "InPlay", "StrikeSwinging", "BallCalled"],
        "PlayResult": ["2B", "Out", "Out", "K", "BB"],
        "ExitSpeed": [100.0, 95.0, 70.0, np.nan, np.nan],
        "Angle":     [28.0, 15.0, -5.0, np.nan, np.nan],
    })


def test_expected_batted_balls_shape():
    xbb = ex.expected_batted_balls(_bb_df())
    assert list(xbb.columns) == ["xwoba", "xba", "xslg"]
    assert len(xbb) == 3
    assert (xbb["xba"].between(0, 1)).all()


def test_xwoba_pa_uses_expected_plus_actual_bb():
    df = _bb_df()
    xw = ex.xwoba_pa(df)
    # denom = PA(5) - SacBunt(0) = 5 ; num = Σxwoba(3 batazos) + WOBA_W['BB']
    xbb = ex.expected_batted_balls(df)
    expected = round((xbb["xwoba"].sum() + ex.WOBA_W["BB"]) / 5, 3)
    assert xw == expected


def test_xwoba_pa_nan_without_pa():
    assert pd.isna(ex.xwoba_pa(pd.DataFrame({"ExitSpeed": [], "Angle": []})))


def test_expected_summary_keys():
    s = ex.expected_summary(_bb_df())
    assert set(s) >= {"xwoba", "xba", "xslg", "woba", "woba_minus_xwoba", "n_bip"}
    assert s["n_bip"] == 3
