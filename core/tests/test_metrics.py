import numpy as np
import pandas as pd
from core.metrics import (pitch_color, safe_pct, count_pa, in_zone_mask,
                          batted_ball_mask, barrel_mask, count_k_bb)

def test_safe_pct_zero_denom():
    assert safe_pct(5, 0) == 0.0
    assert safe_pct(1, 4) == 25.0

def test_pitch_color_known_and_fallback():
    assert pitch_color("Slider") == "#C3BD0E"
    assert pitch_color("MysteryPitch", 0) == "#1f77b4"

def test_count_pa_from_playresult():
    df = pd.DataFrame({"PlayResult": ["1B", "Out", "Undefined", "HR", "K"]})
    assert count_pa(df) == 4  # 1B, Out, HR, K (Undefined no cuenta)

def test_in_zone_mask_true_location():
    df = pd.DataFrame({"PlateLocSide": [0.0, 1.5], "PlateLocHeight": [2.5, 2.5]})
    mask, has_loc = in_zone_mask(df)
    assert has_loc is True
    assert mask.tolist() == [True, False]

def test_batted_ball_mask_inplay():
    df = pd.DataFrame({"PitchCall": ["InPlay", "BallCalled", "InPlay"]})
    assert batted_ball_mask(df).tolist() == [True, False, True]

def test_barrel_mask_basic():
    df = pd.DataFrame({"ExitSpeed": [100.0, 80.0], "Angle": [28.0, 28.0]})
    assert barrel_mask(df).tolist() == [True, False]

def test_count_k_bb():
    df = pd.DataFrame({"PlayResult": ["K", "BB", "K", "1B"]})
    assert count_k_bb(df) == (2, 1)
