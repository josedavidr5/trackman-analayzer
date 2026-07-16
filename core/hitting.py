"""Analítica de bateo pura — pandas/numpy. Sin Streamlit ni matplotlib."""
import numpy as np
import pandas as pd
from core.metrics import (safe_pct, count_pa, count_k_bb, in_zone_mask, batted_ball_mask,
                          barrel_mask, compute_woba, SWING_CALLS, CONTACT_CALLS)


# ── movidas verbatim del monolito ──
def build_play_result_table(df):
    if "PlayResult" not in df.columns:
        return pd.DataFrame()
    counts = df["PlayResult"].value_counts().reset_index()
    counts.columns = ["Result", "Count"]
    counts = counts[counts["Result"] != "—"]
    pa = max(count_pa(df), 1)
    counts["% of PAs"] = counts["Count"].apply(lambda x: safe_pct(x, pa))
    return counts.reset_index(drop=True)


def compute_plate_discipline_batter(df):
    """Disciplina del bateador: Zone/Chase reales, K%/BB% por PA."""
    if "PitchCall" not in df.columns:
        return {}
    pc = df["PitchCall"].astype(str)
    ZONE_CALLS = {"StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallFieldable",
                  "FoulBallNotFieldable", "InPlay"}
    n = len(df)
    sw_m = pc.isin(SWING_CALLS); ct_m = pc.isin(CONTACT_CALLS)
    sw, cont, whiff = int(sw_m.sum()), int(ct_m.sum()), int(pc.eq("StrikeSwinging").sum())
    zone_m, has_loc = in_zone_mask(df)
    if has_loc:
        located = df["PlateLocSide"].notna() & df["PlateLocHeight"].notna()
        in_z = int(zone_m.sum()); n_loc = int(located.sum())
        oz = located & ~zone_m
        zone_pct = safe_pct(in_z, n_loc)
        chase_pct = safe_pct(int((sw_m & oz).sum()), max(int(oz.sum()), 1))
    else:
        in_z = int(pc.isin(ZONE_CALLS).sum())
        zone_pct = safe_pct(in_z, n)
        chase_pct = safe_pct(max(0, sw - cont), max(n - in_z, 1))
    pa = count_pa(df); kk, bb = count_k_bb(df)
    return {"Zone %": zone_pct, "Swing %": safe_pct(sw, n),
            "Contact %": safe_pct(cont, max(sw, 1)), "Chase %": chase_pct,
            "Whiff %": safe_pct(whiff, max(sw, 1)),
            "K %": safe_pct(kk, max(pa, 1)), "BB %": safe_pct(bb, max(pa, 1))}


def build_split_table(df, split_col="PitcherThrows", ev_hard=95):
    if split_col not in df.columns:
        return pd.DataFrame()
    rows = []
    for hand, grp in df.groupby(split_col):
        n = len(grp); r = {"vs": hand, "Pitches": n, "PA": count_pa(grp)}
        if "ExitSpeed" in grp.columns:
            ev = grp["ExitSpeed"].dropna()
            r["Avg EV"] = round(ev.mean(), 1) if not ev.empty else np.nan
            r["HH %"] = safe_pct((ev >= ev_hard).sum(), len(ev))
        if "Angle" in grp.columns:
            la = grp["Angle"].dropna()
            r["Avg LA"] = round(la.mean(), 1) if not la.empty else np.nan
        r.update({k: v for k, v in compute_plate_discipline_batter(grp).items()})
        r["wOBA"] = compute_woba(grp)
        rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)


def build_hitting_monthly(df, lmeta=None):
    ev_hard = (lmeta or {}).get("ev_hard", 95)
    barrel_base = (lmeta or {}).get("barrel_ev", 98)
    df = df.copy(); df["YearMonth"] = df["Date"].dt.to_period("M")
    rows = []
    for period, grp in df.groupby("YearMonth"):
        r = {"Month": str(period), "Pitches": len(grp), "PA": count_pa(grp)}
        for col, (mx, av) in [("ExitSpeed", ("Max EV", "Avg EV")), ("Angle", ("Max LA", "Avg LA")),
                              ("Distance", ("Max Dist", "Avg Dist"))]:
            if col in df.columns:
                vals = grp[col].dropna()
                r[mx] = round(vals.max(), 1) if not vals.empty else np.nan
                r[av] = round(vals.mean(), 1) if not vals.empty else np.nan
        bip = batted_ball_mask(grp); n_bip = int(bip.sum())
        if "ExitSpeed" in df.columns:
            ev = grp.loc[bip, "ExitSpeed"].dropna()
            r["HH %"] = safe_pct(int((ev >= ev_hard).sum()), max(len(ev), 1))
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrels = int(barrel_mask(grp[bip], barrel_base).sum()) if n_bip else 0
            r["Barrel %"] = safe_pct(barrels, max(n_bip, 1))
        kk, bb = count_k_bb(grp); pa = max(count_pa(grp), 1)
        r["K %"] = safe_pct(kk, pa); r["BB %"] = safe_pct(bb, pa)
        r["wOBA"] = compute_woba(grp)
        rows.append(r)
    out = pd.DataFrame(rows)
    return out.sort_values("Month", ascending=False).reset_index(drop=True) if not out.empty else out


# ── helpers nuevos ──
def batted_balls(df):
    """Filas con contacto (batted balls)."""
    m = batted_ball_mask(df)
    return df[m].copy() if bool(m.any()) else df.iloc[0:0].copy()


def spray_points(df):
    """Por batazo con Distance+Bearing: {'points': [{x,y,ev,la,distance,result}]}."""
    if not {"Distance", "Bearing"}.issubset(df.columns):
        return {"points": []}
    sub = df.dropna(subset=["Distance", "Bearing"])
    if sub.empty:
        return {"points": []}
    brad = np.deg2rad(sub["Bearing"].to_numpy(dtype=float))
    dist = sub["Distance"].to_numpy(dtype=float)
    xs = dist * np.sin(brad); ys = dist * np.cos(brad)
    ev = sub["ExitSpeed"].to_numpy() if "ExitSpeed" in sub.columns else np.full(len(sub), np.nan)
    la = sub["Angle"].to_numpy() if "Angle" in sub.columns else np.full(len(sub), np.nan)
    res = sub["PlayResult"].astype(str).to_numpy() if "PlayResult" in sub.columns else np.array([""] * len(sub))
    pts = []
    for i in range(len(sub)):
        pts.append({"x": float(xs[i]), "y": float(ys[i]),
                    "ev": float(ev[i]) if pd.notna(ev[i]) else None,
                    "la": float(la[i]) if pd.notna(la[i]) else None,
                    "distance": float(dist[i]), "result": str(res[i])})
    return {"points": pts}


def hitting_summary(df, lmeta=None):
    """Métricas de cabecera/panel: n, pa, avg/max EV, avg LA, HH%, Barrel%, wOBA."""
    ev_hard = (lmeta or {}).get("ev_hard", 95)
    barrel_base = (lmeta or {}).get("barrel_ev", 98)
    bip = batted_ball_mask(df); n_bip = int(bip.sum())

    def _f(v):
        return float(v) if v is not None and pd.notna(v) else None

    ev = df.loc[bip, "ExitSpeed"].dropna() if "ExitSpeed" in df.columns else pd.Series(dtype=float)
    la = df.loc[bip, "Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    hh = safe_pct(int((ev >= ev_hard).sum()), max(len(ev), 1)) if len(ev) else 0.0
    barrel = (safe_pct(int(barrel_mask(df[bip], barrel_base).sum()), n_bip)
              if n_bip and {"ExitSpeed", "Angle"}.issubset(df.columns) else 0.0)
    return {"n": int(len(df)), "pa": int(count_pa(df)),
            "avg_ev": _f(ev.mean()) if len(ev) else None,
            "max_ev": _f(ev.max()) if len(ev) else None,
            "avg_la": _f(la.mean()) if len(la) else None,
            "hh_pct": hh, "barrel_pct": barrel, "woba": _f(compute_woba(df))}
