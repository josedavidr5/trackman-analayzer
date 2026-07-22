"""Capa evaluativa: modelo híbrido EV×ángulo y stats esperados (xwOBA/xBA/xSLG). Puro."""
import numpy as np
import pandas as pd
from core.metrics import WOBA_W, count_pa, batted_ball_mask, compute_woba

OUTCOMES = ["out", "1B", "2B", "3B", "HR"]
_OUT_W = np.array([0.0, WOBA_W["1B"], WOBA_W["2B"], WOBA_W["3B"], WOBA_W["HR"]])
_SLG_W = np.array([0.0, 1.0, 2.0, 3.0, 4.0])

RECAL_MIN_BB = 500
SHRINK_K = 50.0
EV_BIN, LA_BIN = 5.0, 5.0
EV_LO, EV_HI = 40.0, 120.0
LA_LO, LA_HI = -40.0, 60.0


def _logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def base_outcome_probs(ev, la):
    """Vector [out,1B,2B,3B,HR] de la base MLB paramétrica para un batazo (ev,la)."""
    ev = float(ev); la = float(la)
    p_hr = 0.92 * _logistic((ev - 99.0) / 3.0) * np.exp(-((la - 27.0) / 9.0) ** 2)
    hit = 0.58 * np.exp(-((la - 16.0) / 14.0) ** 2) * _logistic((ev - 82.0) / 8.0)
    hit = float(np.clip(hit, 0.0, 0.95))
    d_share = 0.15 + 0.45 * _logistic((ev - 88.0) / 6.0) * np.exp(-((la - 20.0) / 12.0) ** 2)
    t_share = 0.03
    p_2b = hit * d_share
    p_3b = hit * t_share
    p_1b = hit - p_2b - p_3b
    p = np.clip(np.array([0.0, p_1b, p_2b, p_3b, p_hr], dtype=float), 0.0, None)
    s = p[1:].sum()
    if s > 1.0:
        p[1:] = p[1:] / s
        s = 1.0
    p[0] = 1.0 - s
    return p


def xwoba_contact(ev, la, grid=None):
    if ev is None or la is None or pd.isna(ev) or pd.isna(la):
        return np.nan
    p = hybrid_outcome_probs(ev, la, grid) if grid else base_outcome_probs(ev, la)
    return float(p @ _OUT_W)
