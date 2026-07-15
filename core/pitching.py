"""Analítica de pitching pura — pandas/numpy. Sin Streamlit ni matplotlib."""
import numpy as np
import pandas as pd
from core.metrics import (safe_pct, in_zone_mask, SWING_CALLS, CONTACT_CALLS,
                          ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP)

def pitch_summary(df):
    """Por tipo: Count, Usage %, Avg/Max mph, Spin, IVB, HB. FB primero, luego por Count."""
    total = len(df); rows = []
    for pt, grp in df.groupby("TaggedPitchType"):
        r = {"Pitch": pt, "Count": len(grp), "Usage %": safe_pct(len(grp), total)}
        if "RelSpeed" in grp.columns:
            r["Avg mph"] = round(grp["RelSpeed"].mean(), 1)
            r["Max mph"] = round(grp["RelSpeed"].max(), 1)
        for col, alias in [("SpinRate", "Spin"), ("InducedVertBreak", "IVB"), ("HorzBreak", "HB")]:
            r[alias] = round(grp[col].mean(), 1) if col in grp.columns else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_fb"] = out["Pitch"].str.lower().str.contains("fastball|4-seam|2-seam").astype(int)
    return out.sort_values(["_fb", "Count"], ascending=[False, False]).drop(columns="_fb").reset_index(drop=True)

def pitch_discipline(df):
    """Por tipo: Zone %, Swing %, Contact %, Chase %, Whiff %. Ubicación real si existe."""
    if "PitchCall" not in df.columns:
        return pd.DataFrame()
    ZONE_CALLS = {"StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallFieldable",
                  "FoulBallNotFieldable", "InPlay"}
    rows = []
    for pt, grp in df.groupby("TaggedPitchType"):
        pc = grp["PitchCall"].astype(str)
        n = len(grp)
        sw_m = pc.isin(SWING_CALLS); ct_m = pc.isin(CONTACT_CALLS); wh_m = pc.eq("StrikeSwinging")
        sw, ct, wh = int(sw_m.sum()), int(ct_m.sum()), int(wh_m.sum())
        zone_m, has_loc = in_zone_mask(grp)
        if has_loc:
            located = grp["PlateLocSide"].notna() & grp["PlateLocHeight"].notna()
            n_loc = int(located.sum()); in_z = int(zone_m.sum())
            oz = located & ~zone_m
            zone_pct = safe_pct(in_z, n_loc)
            chase_pct = safe_pct(int((sw_m & oz).sum()), max(int(oz.sum()), 1))
        else:
            in_z = int(pc.isin(ZONE_CALLS).sum())
            zone_pct = safe_pct(in_z, n)
            chase_pct = safe_pct(max(0, sw - ct), max(n - in_z, 1))
        rows.append({"Pitch": pt, "Count": n, "Zone %": zone_pct, "Swing %": safe_pct(sw, n),
                     "Contact %": safe_pct(ct, max(sw, 1)), "Chase %": chase_pct,
                     "Whiff %": safe_pct(wh, max(sw, 1))})
    return pd.DataFrame(rows).sort_values("Count", ascending=False).reset_index(drop=True)

def build_usage_by_count(df):
    """Usage % por conteo balls-strikes (rows=tipo, cols=conteo)."""
    if "Count" not in df.columns or df["Count"].isna().all():
        return pd.DataFrame()
    sub = df[df["Count"].notna() & ~df["Count"].astype(str).str.contains("<NA>", na=True)]
    if sub.empty:
        return pd.DataFrame()
    order = [f"{b}-{s}" for b in range(4) for s in range(3)]
    tab = pd.crosstab(sub["TaggedPitchType"], sub["Count"], normalize="columns") * 100
    cols = [c for c in order if c in tab.columns]
    return tab[cols].round(1) if cols else pd.DataFrame()

def _csw_pct(pc):
    """CSW% = (StrikeCalled + StrikeSwinging) / pitcheos, de una Serie PitchCall."""
    return safe_pct(int(pc.isin({"StrikeCalled", "StrikeSwinging"}).sum()), len(pc))

def arsenal_stuff(df):
    """Una fila por tipo: usage, velo, spin, movimiento, disciplina + CSW%."""
    summ = pitch_summary(df)
    if summ.empty:
        return summ
    disc = pitch_discipline(df)
    disc_by = {r["Pitch"]: r for r in disc.to_dict("records")} if not disc.empty else {}
    has_pc = "PitchCall" in df.columns
    rows = []
    for r in summ.to_dict("records"):
        pt = r["Pitch"]; d = disc_by.get(pt, {})
        pc = (df[df["TaggedPitchType"] == pt]["PitchCall"].astype(str)
              if has_pc else pd.Series(dtype=str))
        rows.append({
            "Pitch": pt, "Usage %": r.get("Usage %", 0.0), "Count": r.get("Count", 0),
            "Avg mph": r.get("Avg mph", np.nan), "Max mph": r.get("Max mph", np.nan),
            "Spin": r.get("Spin", np.nan), "IVB": r.get("IVB", np.nan), "HB": r.get("HB", np.nan),
            "Zone %": d.get("Zone %", np.nan), "Swing %": d.get("Swing %", np.nan),
            "Chase %": d.get("Chase %", np.nan), "Whiff %": d.get("Whiff %", np.nan),
            "CSW %": _csw_pct(pc) if has_pc and len(pc) else np.nan,
        })
    return pd.DataFrame(rows)

def _fnum(v):
    return float(v) if v is not None and pd.notna(v) else None

def movement_points(df):
    """Puntos individuales (hb,ivb) + centroide por tipo enriquecido con arsenal_stuff."""
    out = {"pitches": [], "centroids": []}
    if not {"HorzBreak", "InducedVertBreak"}.issubset(df.columns):
        return out
    sub = df.dropna(subset=["HorzBreak", "InducedVertBreak"])
    if sub.empty:
        return out
    stuff = {r["Pitch"]: r for r in arsenal_stuff(df).to_dict("records")}
    for pt, g in sub.groupby("TaggedPitchType"):
        for hb, ivb in zip(g["HorzBreak"], g["InducedVertBreak"]):
            out["pitches"].append({"pitch_type": pt, "hb": float(hb), "ivb": float(ivb)})
        s = stuff.get(pt, {})
        out["centroids"].append({
            "pitch_type": pt, "hb": float(g["HorzBreak"].mean()),
            "ivb": float(g["InducedVertBreak"].mean()), "n": int(len(g)),
            "usage": float(s.get("Usage %", 0.0)), "avg_velo": _fnum(s.get("Avg mph")),
            "max_velo": _fnum(s.get("Max mph")), "avg_spin": _fnum(s.get("Spin")),
            "whiff": _fnum(s.get("Whiff %")), "csw": _fnum(s.get("CSW %")),
        })
    return out

def whiff_csw_zone_grid(df, min_swings=4, min_pitches=5):
    """Grid 5×5 de tasas Whiff%/CSW% por celda (vista catcher).

    El 3×3 interno se alinea a la zona de strike; la banda externa (una celda por
    lado) captura el área de chase — los pitcheos fuera del extent se asignan por
    clamp a la celda de borde. Puro; NO requiere TaggedPitchType (el filtrado por
    tipo se hace antes de llamar).
    """
    cell_x = (2 * ZONE_HALF_WIDTH) / 3.0
    cell_z = (ZONE_TOP - ZONE_BOTTOM) / 3.0
    x_edges = [-ZONE_HALF_WIDTH - cell_x, -ZONE_HALF_WIDTH, -ZONE_HALF_WIDTH + cell_x,
               ZONE_HALF_WIDTH - cell_x, ZONE_HALF_WIDTH, ZONE_HALF_WIDTH + cell_x]
    z_edges = [ZONE_BOTTOM - cell_z, ZONE_BOTTOM, ZONE_BOTTOM + cell_z,
               ZONE_TOP - cell_z, ZONE_TOP, ZONE_TOP + cell_z]
    empty = {"x_edges": x_edges, "z_edges": z_edges, "cells": [], "total_pitches": 0}
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns) or "PitchCall" not in df.columns:
        return empty
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        return empty
    pc = loc["PitchCall"].astype(str)
    # 5 celdas por eje: digitize contra los 4 bordes internos, clamp a 0..4
    xi = np.clip(np.digitize(loc["PlateLocSide"].to_numpy(), x_edges[1:5]), 0, 4)
    zi = np.clip(np.digitize(loc["PlateLocHeight"].to_numpy(), z_edges[1:5]), 0, 4)
    swing = pc.isin(SWING_CALLS).to_numpy()
    whiff = (pc == "StrikeSwinging").to_numpy()
    called = (pc == "StrikeCalled").to_numpy()
    cells = []
    for iz in range(5):
        for ix in range(5):
            m = (xi == ix) & (zi == iz)
            n = int(m.sum())
            ns = int(swing[m].sum())
            nw = int(whiff[m].sum())
            nc = int(called[m].sum())
            cells.append({
                "ix": ix, "iz": iz, "n_pitches": n, "n_swings": ns,
                "whiffs": nw, "called": nc,
                "whiff_pct": safe_pct(nw, ns), "csw_pct": safe_pct(nc + nw, n),
                "whiff_reliable": ns >= min_swings, "csw_reliable": n >= min_pitches,
            })
    return {"x_edges": x_edges, "z_edges": z_edges, "cells": cells, "total_pitches": int(len(loc))}
