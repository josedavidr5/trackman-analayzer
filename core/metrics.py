"""Primitivos sabermétricos puros — sin Streamlit ni matplotlib. Solo pandas/numpy."""
import numpy as np
import pandas as pd

# ── Colores Statcast por tipo de pitcheo (hex literal; espejo del theme del app) ──
STATCAST_PITCH_COLORS = {
    "4-Seam": "#D22D49", "Fastball": "#D22D49", "2-Seam": "#DE6A04", "Sinker": "#FE9D00",
    "Cutter": "#933F2C", "Slider": "#C3BD0E", "Sweeper": "#DDB33A", "Curve": "#00D1ED",
    "Knuckle Curve": "#6236CD", "Change": "#1DBE3A", "Split": "#3BACAC",
    "Knuckleball": "#3C44CD", "Screwball": "#60DB33",
}
PITCH_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b",
                 "#e377c2", "#7f7f7f", "#2ca02c", "#ff9896", "#98df8a", "#c5b0d5"]

def pitch_color(pt, idx=0):
    return STATCAST_PITCH_COLORS.get(str(pt), PITCH_PALETTE[idx % len(PITCH_PALETTE)])

def safe_pct(num, denom):
    return round(100 * num / denom, 1) if denom > 0 else 0.0

TERMINAL_RESULTS = {"1B", "2B", "3B", "HR", "Out", "K", "BB", "HBP", "FC", "Error", "SacFly", "SacBunt"}
SWING_CALLS = {"StrikeSwinging", "FoulBall", "FoulBallFieldable", "FoulBallNotFieldable", "InPlay"}
CONTACT_CALLS = {"FoulBall", "FoulBallFieldable", "FoulBallNotFieldable", "InPlay"}
ZONE_HALF_WIDTH = 0.83
ZONE_BOTTOM, ZONE_TOP = 1.5, 3.5
WOBA_W = {"BB": 0.69, "HBP": 0.72, "1B": 0.89, "2B": 1.27, "3B": 1.62, "HR": 2.10}

def count_pa(df):
    """Plate appearances = pitches whose PlayResult is a terminal outcome."""
    if "PlayResult" in df.columns:
        pa = int(df["PlayResult"].astype(str).isin(TERMINAL_RESULTS).sum())
        if pa > 0:
            return pa
    if "PitchCall" in df.columns:
        return int(df["PitchCall"].astype(str).isin({"InPlay", "HitByPitch"}).sum())
    return 0

def in_zone_mask(df):
    """(mask, has_location) — true strike-zone membership from PlateLoc columns."""
    if {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns) and df["PlateLocSide"].notna().any():
        m = ((df["PlateLocSide"].abs() <= ZONE_HALF_WIDTH)
             & (df["PlateLocHeight"].between(ZONE_BOTTOM, ZONE_TOP)))
        return m.fillna(False), True
    return pd.Series(False, index=df.index), False

def batted_ball_mask(df):
    """Balls put in play — denominator for HH% / Barrel%."""
    if "PitchCall" in df.columns:
        m = df["PitchCall"].astype(str).eq("InPlay")
        if m.any():
            return m
    if "ExitSpeed" in df.columns:
        return df["ExitSpeed"].notna()
    return pd.Series(False, index=df.index)

def barrel_mask(df, barrel_ev_base=98):
    """Savant-style barrel window, rescaled by barrel_ev_base for amateur levels."""
    if not {"ExitSpeed", "Angle"}.issubset(df.columns):
        return pd.Series(False, index=df.index)
    ev = df["ExitSpeed"] + (98 - barrel_ev_base)
    la = df["Angle"]
    lo = (26 - (ev - 98)).clip(lower=8)
    hi = (30 + (ev - 98) * (20 / 18)).clip(upper=50)
    return ((ev >= 98) & (la >= lo) & (la <= hi)).fillna(False)

def count_k_bb(df):
    """(K, BB) counted once per PA from PlayResult, PitchCall fallback for K."""
    kk = bb = 0
    if "PlayResult" in df.columns:
        pr = df["PlayResult"].astype(str)
        kk = int(pr.eq("K").sum()); bb = int(pr.eq("BB").sum())
    if kk == 0 and "PitchCall" in df.columns:
        kk = int(df["PitchCall"].astype(str).isin({"StrikeoutSwinging", "StrikeoutCalled"}).sum())
    return kk, bb

def compute_woba(df):
    """wOBA from tagged PlayResults. Returns np.nan without PA data."""
    pa = count_pa(df)
    if pa == 0 or "PlayResult" not in df.columns:
        return np.nan
    pr = df["PlayResult"].astype(str)
    num = sum(w * int(pr.eq(res).sum()) for res, w in WOBA_W.items())
    denom = pa - int(pr.eq("SacBunt").sum())
    return round(num / denom, 3) if denom > 0 else np.nan
