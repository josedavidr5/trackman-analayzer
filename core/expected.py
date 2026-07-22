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


def expected_batted_balls(df, grid=None):
    """xwoba/xba/xslg por batazo (filas InPlay con EV+ángulo)."""
    cols = ["xwoba", "xba", "xslg"]
    if not {"ExitSpeed", "Angle"}.issubset(df.columns):
        return pd.DataFrame(columns=cols)
    bip = batted_ball_mask(df)
    sub = df.loc[bip, ["ExitSpeed", "Angle"]].dropna()
    rows = []
    for ev, la in zip(sub["ExitSpeed"], sub["Angle"]):
        p = hybrid_outcome_probs(ev, la, grid) if grid else base_outcome_probs(ev, la)
        rows.append((float(p @ _OUT_W), float(p[1:].sum()), float(p @ _SLG_W)))
    return pd.DataFrame(rows, columns=cols, index=sub.index)


def xwoba_pa(df, grid=None):
    """xwOBA por PA: batazos esperados + K/BB/HBP reales; espeja compute_woba."""
    pa = count_pa(df)
    if pa == 0:
        return np.nan
    xbb = expected_batted_balls(df, grid)
    num = float(xbb["xwoba"].sum()) if not xbb.empty else 0.0
    if "PlayResult" in df.columns:
        pr = df["PlayResult"].astype(str)
        for res in ("BB", "HBP"):
            num += WOBA_W[res] * int(pr.eq(res).sum())
        denom = pa - int(pr.eq("SacBunt").sum())
    else:
        denom = pa
    return round(num / denom, 3) if denom > 0 else np.nan


def expected_summary(df, grid=None):
    xbb = expected_batted_balls(df, grid)
    woba = compute_woba(df)
    xw = xwoba_pa(df, grid)
    n_bip = int(len(xbb))
    return {
        "xwoba": float(xw) if pd.notna(xw) else None,
        "xba": float(xbb["xba"].mean()) if n_bip else None,
        "xslg": float(xbb["xslg"].mean()) if n_bip else None,
        "woba": float(woba) if pd.notna(woba) else None,
        "woba_minus_xwoba": (float(woba) - float(xw)) if pd.notna(woba) and pd.notna(xw) else None,
        "n_bip": n_bip,
    }


_BIP_CLASS = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}   # otros BIP → 0 (out)


def _bin_idx(ev, la):
    ei = int(np.clip((float(ev) - EV_LO) // EV_BIN, 0, (EV_HI - EV_LO) / EV_BIN - 1))
    li = int(np.clip((float(la) - LA_LO) // LA_BIN, 0, (LA_HI - LA_LO) / LA_BIN - 1))
    return ei, li


def empirical_grid(df):
    """{(ei,li): (counts[5], n)} desde los batazos del dataset + total y flag."""
    cells = {}
    total = 0
    if not {"ExitSpeed", "Angle", "PlayResult"}.issubset(df.columns):
        return {"cells": cells, "n": 0, "recalibrated": False}
    bip = batted_ball_mask(df)
    sub = df.loc[bip, ["ExitSpeed", "Angle", "PlayResult"]].dropna(subset=["ExitSpeed", "Angle"])
    for ev, la, res in zip(sub["ExitSpeed"], sub["Angle"], sub["PlayResult"].astype(str)):
        key = _bin_idx(ev, la)
        c, n = cells.get(key, (np.zeros(5), 0))
        c = c.copy(); c[_BIP_CLASS.get(res, 0)] += 1
        cells[key] = (c, n + 1)
        total += 1
    return {"cells": cells, "n": total, "recalibrated": total >= RECAL_MIN_BB}


def hybrid_outcome_probs(ev, la, grid):
    base = base_outcome_probs(ev, la)
    if not grid or not grid.get("cells"):
        return base
    c, n = grid["cells"].get(_bin_idx(ev, la), (np.zeros(5), 0))
    if n == 0:
        return base
    p_emp = c / n
    return (n * p_emp + SHRINK_K * base) / (n + SHRINK_K)
