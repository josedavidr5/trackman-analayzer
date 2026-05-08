"""
=============================================================================
  TRACKMAN BASEBALL ANALYTICS DASHBOARD  v2.0
  Expert-grade Streamlit app for pitching and hitting analysis

  NEW in v2:
  ─────────────────────────────────────────────────────────────────────────
  UX / UI
    • Redesigned hero banner with feature pills
    • Multi-date picker: select any individual dates (Tue, Thu etc.)
    • Tab-based layout inside each dashboard (no more endless scroll)
    • Wider metric cards with delta indicators (max beside avg)
    • Advanced Filters expander: handedness, pitch type, inning range
    • Compact discipline stat-badges row

  ANALYTICS — PITCHING
    • Pitch Usage % column in summary table
    • Strike Zone %, Swing %, Contact %, Chase %, Whiff % per pitch type
    • Movement Profile bubble chart (IVB vs HB, sized by usage)
    • Release Point scatter (RelHeight vs RelSide)
    • Count / game-state context (Balls–Strikes)

  ANALYTICS — HITTING
    • Hard-Hit Rate (EV ≥ 95 mph) + Barrel % (EV ≥ 98, LA 8-32°)
    • Plate Discipline badges: Zone%, Swing%, Contact%, Chase%, K%, BB%
    • Monthly table now includes HH% and Barrel% per month
    • Exit Velo histogram with mean + hard-hit threshold lines
    • Launch Angle histogram with barrel-zone shading
    • Rolling 7-day Avg Exit Speed trend line
  ─────────────────────────────────────────────────────────────────────────
  Built with: Streamlit, Pandas, Matplotlib, Seaborn, NumPy
=============================================================================
"""

import io
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────
BG      = "#0d1117"
CARD    = "#161b22"
CARD2   = "#1c2230"
ACCENT  = "#e8a838"
ACCENT2 = "#f0c060"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"
BORDER  = "#30363d"
GRID_C  = "#21262d"
RED     = "#e85858"
BLUE    = "#4e9af1"
GREEN   = "#58c99a"
PURPLE  = "#c458e8"
TEAL    = "#58a4e8"
ORANGE  = "#e87858"

PITCH_PALETTE = [
    ACCENT, BLUE, RED, GREEN, PURPLE,
    ACCENT2, TEAL, ORANGE,
    "#a8d8a8", "#f8b4b4", "#b4c8f8", "#f8d4a8",
]

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trackman Analytics v2",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
:root {{
    --bg:     {BG};    --card:   {CARD};   --card2:  {CARD2};
    --accent: {ACCENT}; --text:  {TEXT};   --muted:  {MUTED};
    --border: {BORDER}; --grid:  {GRID_C};
}}

/* ── App shell ── */
.stApp {{ background-color: var(--bg); color: var(--text);
          font-family: 'Segoe UI', system-ui, sans-serif; }}
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0f1923 0%, #111820 100%);
    border-right: 1px solid var(--border);
}}

/* ── Sidebar section labels ── */
.sb-label {{
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--accent);
    padding: 14px 0 4px 0; display: block;
}}

/* ── Hero banner ── */
.hero {{
    background: linear-gradient(135deg, #0f1f35 0%, #0d1117 55%, #1a1100 100%);
    border: 1px solid var(--border); border-radius: 14px;
    padding: 26px 32px; margin-bottom: 22px;
    display: flex; align-items: center; gap: 20px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5);
}}
.hero-icon {{ font-size: 3.4rem; line-height: 1; filter: drop-shadow(0 2px 6px #e8a83855); }}
.hero-title {{ font-size: 2.3rem; font-weight: 900; color: var(--text);
               letter-spacing: -0.03em; line-height: 1.05; }}
.hero-title span {{ color: var(--accent); }}
.hero-sub {{ color: var(--muted); font-size: 0.9rem; margin-top: 5px; }}
.hero-pills {{ display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }}
.pill {{
    background: rgba(232,168,56,0.12); border: 1px solid rgba(232,168,56,0.3);
    color: var(--accent); border-radius: 20px; padding: 3px 12px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
}}

/* ── Section headers ── */
.sh {{
    font-size: 0.78rem; font-weight: 800; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.14em;
    border-bottom: 1px solid var(--border); padding-bottom: 7px;
    margin: 24px 0 14px 0; display: flex; align-items: center; gap: 8px;
}}

/* ── Metric cards ── */
div[data-testid="metric-container"] {{
    background: var(--card); border: 1px solid var(--border);
    border-top: 3px solid var(--accent); border-radius: 10px;
    padding: 18px 16px; transition: box-shadow .2s;
}}
div[data-testid="metric-container"]:hover {{ box-shadow: 0 0 16px rgba(232,168,56,0.15); }}
div[data-testid="metric-container"] label {{
    color: var(--muted) !important; font-size: 0.75rem !important; letter-spacing: 0.06em;
}}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
    color: var(--accent) !important; font-size: 1.9rem !important; font-weight: 800 !important;
}}

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}

/* ── Alerts ── */
div[data-testid="stAlert"] {{ border-radius: 8px; }}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px; background: var(--card); border-radius: 10px; padding: 4px;
    border: 1px solid var(--border);
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 7px; color: var(--muted);
    font-weight: 600; font-size: 0.85rem;
}}
.stTabs [aria-selected="true"] {{ background: var(--accent) !important; color: #000 !important; }}

/* ── Download buttons ── */
.stDownloadButton > button {{
    background: rgba(232,168,56,0.08); border: 1px solid var(--accent);
    color: var(--accent); font-weight: 700; border-radius: 7px;
    transition: all .2s; letter-spacing: 0.04em;
}}
.stDownloadButton > button:hover {{ background: var(--accent); color: #000; }}

/* ── Expander ── */
div[data-testid="stExpander"] {{
    border: 1px solid var(--border) !important;
    border-radius: 8px !important; background: var(--card) !important;
}}

/* ── Date chips ── */
.date-chip-wrap {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }}
.date-chip {{
    background: rgba(232,168,56,0.15); border: 1px solid rgba(232,168,56,0.4);
    color: var(--accent); border-radius: 14px; padding: 2px 10px;
    font-size: 0.72rem; font-weight: 600;
}}

/* ── Discipline badges ── */
.stat-badge {{
    display: inline-block; background: var(--card2);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 16px; text-align: center; min-width: 90px;
}}
.stat-badge .val {{ font-size: 1.5rem; font-weight: 800; color: var(--accent); }}
.stat-badge .lbl {{ font-size: 0.65rem; color: var(--muted);
                    letter-spacing: 0.07em; text-transform: uppercase; }}

/* ── Upload drop zone ── */
.upload-zone {{
    background: var(--card); border: 2px dashed var(--border);
    border-radius: 14px; padding: 64px 40px;
    text-align: center; margin-top: 32px;
}}
.upload-zone .big {{ font-size: 3.2rem; margin-bottom: 14px; }}
.upload-zone .ttl {{ font-size: 1.35rem; font-weight: 700; color: var(--text); margin-bottom: 8px; }}
.upload-zone .sub {{ color: var(--muted); font-size: 0.9rem; line-height: 1.6; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def apply_dark_theme(fig, ax_list=None):
    """Apply consistent dark theme to any matplotlib figure."""
    fig.patch.set_facecolor(BG)
    for ax in (ax_list or fig.get_axes()):
        ax.set_facecolor(CARD)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        ax.title.set_color(TEXT)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID_C)
        ax.grid(color=GRID_C, linewidth=0.5, alpha=0.6)


def draw_strike_zone(ax, color=ACCENT, lw=1.8, alpha=0.9):
    """MLB strike zone rectangle with 3×3 inner grid."""
    zone = patches.Rectangle(
        (-0.71, 1.5), 1.42, 2.0,
        lw=lw, edgecolor=color, facecolor="none", alpha=alpha, zorder=5)
    ax.add_patch(zone)
    for i in range(1, 3):
        ax.axvline(-0.71 + i * 1.42/3, color=color, lw=0.45, alpha=0.3, zorder=4)
    for j in range(1, 3):
        ax.axhline(1.5  + j * 2.0/3,  color=color, lw=0.45, alpha=0.3, zorder=4)


def styled_table_pdf(ax, df, title):
    """Render a styled dark table on a matplotlib Axes for PDF embedding."""
    ax.axis("off")
    if title:
        ax.set_title(title, color=TEXT, fontsize=12, fontweight="bold", pad=14)
    cols = list(df.columns)
    data = df.fillna("—").values.tolist()
    tbl = ax.table(cellText=data, colLabels=cols, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.auto_set_column_width(col=list(range(len(cols))))
    for j in range(len(cols)):
        c = tbl[0, j]
        c.set_facecolor(ACCENT)
        c.set_text_props(color="#000", fontweight="bold")
    for i in range(1, len(data) + 1):
        for j in range(len(cols)):
            c = tbl[i, j]
            c.set_facecolor(CARD2 if i % 2 == 0 else CARD)
            c.set_text_props(color=TEXT)
    tbl.scale(1.1, 1.55)


def csv_dl(df, fname, label="⬇️ Download CSV"):
    """Streamlit CSV download button."""
    st.download_button(label, df.to_csv(index=False).encode(), fname, "text/csv")


def safe_pct(num, denom):
    """Safe percentage rounded to 1 decimal."""
    return round(100 * num / denom, 1) if denom > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — DATA LOADING & CLEANING
# ─────────────────────────────────────────────────────────────────────────────
COLUMN_ALIASES = {
    "TaggedPitchType": ["AutoPitchType", "PitchType"],
    "PitchCall":       ["Call", "PitchResult"],
    "Batter":          ["BatterName", "HitterName"],
    "Pitcher":         ["PitcherName", "ThrowerName"],
    "BatterSide":      ["BatterHand", "BatterHandedness", "Side"],
    "PitcherThrows":   ["PitcherHand", "Throws"],
}
# Only these explicit strings are warmups — NaN/blank are VALID pitches
WARMUP_VALUES = {"warmup", "undefined"}


def smart_map_columns(df):
    """Rename alternative Trackman column names to their standard equivalents."""
    for std, alts in COLUMN_ALIASES.items():
        if std not in df.columns:
            for alt in alts:
                matched = [c for c in df.columns if c.lower() == alt.lower()]
                if matched:
                    df.rename(columns={matched[0]: std}, inplace=True)
                    break
    return df


def load_and_clean(files):
    """
    Read, merge, column-map, date-parse, warmup-filter, and cast numerics.
    Returns a clean master DataFrame.
    """
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f, low_memory=False))
        except Exception as e:
            st.warning(f"⚠️ Could not read **{f.name}**: {e}")
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = smart_map_columns(df)

    # Parse date — Latin American day-first format
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    else:
        st.warning("⚠️ No 'Date' column found — date filtering unavailable.")
        df["Date"] = pd.NaT

    # ── Warmup filter: explicit strings only, never NaN/blank ──
    before = len(df)
    mask = pd.Series(False, index=df.index)
    for col in ["PitchCall", "Batter"]:
        if col in df.columns:
            mask |= (df[col].fillna("").astype(str)
                            .str.strip().str.lower()
                            .isin(WARMUP_VALUES))
    df = df[~mask].reset_index(drop=True)
    removed = before - len(df)
    if removed:
        st.sidebar.caption(f"🧹 Removed **{removed:,}** warmup rows.")

    # Fill missing pitch type
    if "TaggedPitchType" in df.columns:
        df["TaggedPitchType"] = (df["TaggedPitchType"].astype(str).str.strip()
                                  .replace({"nan": "Unknown", "": "Unknown"}))
    else:
        df["TaggedPitchType"] = "Unknown"

    # Cast all numeric columns safely
    NUMERIC = [
        "RelSpeed", "SpinRate", "InducedVertBreak", "HorzBreak",
        "PlateLocSide", "PlateLocHeight", "ExitSpeed", "Angle",
        "Distance", "Bearing", "RelHeight", "RelSide", "Extension",
        "SpinAxis", "VertApprAngle", "HorzApprAngle",
        "Balls", "Strikes", "Inning",
    ]
    for col in NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Build Count string (0-0, 1-2, etc.)
    if "Balls" in df.columns and "Strikes" in df.columns:
        df["Count"] = (df["Balls"].astype("Int64").astype(str) + "-"
                       + df["Strikes"].astype("Int64").astype(str))

    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — MULTI-DATE FILTER
# ─────────────────────────────────────────────────────────────────────────────
def sidebar_date_filter(df):
    """
    Two-mode date filter shown in sidebar:
      • Date Range  — continuous start → end window
      • Pick Dates  — multiselect any individual dates (Tue, Thu, etc.)
    """
    st.sidebar.markdown(
        '<span class="sb-label">📅 Date Filter</span>', unsafe_allow_html=True)

    valid = df["Date"].dropna()
    if valid.empty:
        st.sidebar.info("No valid dates — showing all data.")
        return df

    all_dates = sorted(valid.dt.date.unique())
    min_d, max_d = all_dates[0], all_dates[-1]

    mode = st.sidebar.radio(
        "Filter mode",
        ["📆 Date Range", "🗓️ Pick Specific Dates"],
        horizontal=True,
        label_visibility="collapsed",
        key="date_mode",
    )

    if mode == "📆 Date Range":
        # ── Continuous range picker ──
        sel = st.sidebar.date_input(
            "Range", value=(min_d, max_d),
            min_value=min_d, max_value=max_d,
        )
        if isinstance(sel, (list, tuple)) and len(sel) == 2:
            start, end = sel
        else:
            start = end = sel or min_d
        filtered = df[
            (df["Date"].dt.date >= start) &
            (df["Date"].dt.date <= end)
        ]
        st.sidebar.caption(f"📊 **{len(filtered):,}** pitches · {start} → {end}")

    else:
        # ── Individual date multi-picker ──
        # Map each date → readable label (e.g. "Tue Apr 08, 2025")
        date_fmt = {d: d.strftime("%a %b %d, %Y") for d in all_dates}
        fmt_list = [date_fmt[d] for d in all_dates]

        # Sensible default: last 7 distinct dates
        default_labels = fmt_list[-min(7, len(fmt_list)):]

        chosen_labels = st.sidebar.multiselect(
            "Select individual dates",
            options=fmt_list,
            default=default_labels,
            help=(
                "Pick any combination of dates — e.g. every Tuesday and Thursday "
                "across several months. Hold Ctrl / Cmd to multi-select."
            ),
        )

        if not chosen_labels:
            st.sidebar.warning("No dates selected — showing all data.")
            filtered = df.copy()
        else:
            rev_map = {v: k for k, v in date_fmt.items()}
            chosen_set = {rev_map[l] for l in chosen_labels}
            filtered = df[df["Date"].dt.date.isin(chosen_set)]

            # Show compact date chips below the multiselect
            chips = "".join(
                f'<span class="date-chip">{l.split(",")[0]}</span>'
                for l in chosen_labels
            )
            st.sidebar.markdown(
                f'<div class="date-chip-wrap">{chips}</div>',
                unsafe_allow_html=True,
            )
            st.sidebar.caption(
                f"📊 **{len(filtered):,}** pitches across **{len(chosen_labels)}** dates"
            )

    return filtered.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED SIDEBAR FILTERS
# ─────────────────────────────────────────────────────────────────────────────
def advanced_filters(df):
    """Collapsible expander: handedness, pitch type, inning range."""
    with st.sidebar.expander("⚙️ Advanced Filters", expanded=False):

        if "BatterSide" in df.columns:
            opts = sorted(df["BatterSide"].dropna().unique())
            sel  = st.multiselect("Batter Side", opts, default=opts, key="adv_side")
            if sel:
                df = df[df["BatterSide"].isin(sel)]

        if "PitcherThrows" in df.columns:
            opts = sorted(df["PitcherThrows"].dropna().unique())
            sel  = st.multiselect("Pitcher Throws", opts, default=opts, key="adv_throws")
            if sel:
                df = df[df["PitcherThrows"].isin(sel)]

        if "TaggedPitchType" in df.columns:
            opts = sorted(df["TaggedPitchType"].dropna().unique())
            sel  = st.multiselect("Pitch Types", opts, default=opts, key="adv_pt")
            if sel:
                df = df[df["TaggedPitchType"].isin(sel)]

        if "Inning" in df.columns and df["Inning"].notna().any():
            lo = int(df["Inning"].min())
            hi = int(df["Inning"].max())
            if lo < hi:
                rng = st.slider("Inning Range", lo, hi, (lo, hi), key="adv_inn")
                df = df[(df["Inning"] >= rng[0]) & (df["Inning"] <= rng[1])]

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# ══ PITCHING ANALYTICS ═══════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

def build_pitch_summary(df):
    """
    Per-pitch-type table: Count, Usage%, MaxMPH, AvgMPH,
    AvgSpin, AvgIVB, AvgHB.  Fastballs forced to top.
    """
    total = len(df)
    rows  = []
    for pt, grp in df.groupby("TaggedPitchType"):
        r = {"Pitch Type": pt,
             "Count":     len(grp),
             "Usage %":   safe_pct(len(grp), total)}
        if "RelSpeed" in grp.columns:
            r["Max MPH"] = round(grp["RelSpeed"].max(),  1)
            r["Avg MPH"] = round(grp["RelSpeed"].mean(), 1)
        for col, alias in [("SpinRate", "Avg Spin"),
                           ("InducedVertBreak", "Avg IVB"),
                           ("HorzBreak",        "Avg HB")]:
            r[alias] = round(grp[col].mean(), 1) if col in grp.columns else np.nan
        rows.append(r)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_fb"] = out["Pitch Type"].str.lower().str.contains("fastball").astype(int)
    out = (out.sort_values(["_fb", "Count"], ascending=[False, False])
              .drop(columns="_fb").reset_index(drop=True))
    return out


def compute_pitch_discipline(df):
    """
    Zone%, Swing%, Contact%, Chase%, Whiff% per pitch type.
    Uses standard Trackman PitchCall values.
    """
    if "PitchCall" not in df.columns:
        return pd.DataFrame()

    ZONE    = {"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable",
               "FoulBallNotFieldable","InPlay"}
    SWING   = {"StrikeSwinging","FoulBall","FoulBallFieldable",
               "FoulBallNotFieldable","InPlay"}
    CONTACT = {"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    WHIFF   = {"StrikeSwinging"}

    rows = []
    for pt, grp in df.groupby("TaggedPitchType"):
        pc     = grp["PitchCall"].astype(str)
        n      = len(grp)
        in_z   = pc.isin(ZONE).sum()
        swings = pc.isin(SWING).sum()
        cont   = pc.isin(CONTACT).sum()
        whiffs = pc.isin(WHIFF).sum()
        out_z  = max(n - in_z, 1)
        chase  = max(0, swings - cont)
        rows.append({
            "Pitch Type": pt,
            "Count":      n,
            "Zone %":     safe_pct(in_z,  n),
            "Swing %":    safe_pct(swings, n),
            "Contact %":  safe_pct(cont, max(swings, 1)),
            "Chase %":    safe_pct(chase, out_z),
            "Whiff %":    safe_pct(whiffs, max(swings, 1)),
        })
    return (pd.DataFrame(rows)
              .sort_values("Count", ascending=False)
              .reset_index(drop=True))


def plot_pitch_locations(df, pitcher_name):
    """Scatter of pitch locations over strike zone, coloured by pitch type."""
    fig, ax = plt.subplots(figsize=(5, 5.5))
    apply_dark_theme(fig, [ax])

    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        ax.text(0.5, 0.5, "No location data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
    else:
        for idx, (pt, g) in enumerate(loc.groupby("TaggedPitchType")):
            ax.scatter(g["PlateLocSide"], g["PlateLocHeight"],
                       label=pt, color=PITCH_PALETTE[idx % len(PITCH_PALETTE)],
                       alpha=0.72, s=28, edgecolors="none", zorder=6)

    draw_strike_zone(ax)
    ax.set_xlim(-2.5, 2.5); ax.set_ylim(0.5, 5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Plate Height (ft)")
    ax.set_title(f"Pitch Locations\n{pitcher_name}", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, framealpha=0.3, edgecolor=BORDER)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(); return fig


def plot_hot_zone(df, pitcher_name):
    """Seaborn KDE density heatmap over the strike zone."""
    fig, ax = plt.subplots(figsize=(5, 5.5))
    apply_dark_theme(fig, [ax])

    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if len(loc) >= 5:
        try:
            sns.kdeplot(data=loc, x="PlateLocSide", y="PlateLocHeight",
                        fill=True, cmap="YlOrRd", alpha=0.78,
                        levels=12, thresh=0.04, ax=ax)
        except Exception:
            ax.text(0.5, 0.5, "Not enough data for KDE",
                    ha="center", va="center", color=MUTED, transform=ax.transAxes)
    else:
        ax.text(0.5, 0.5, "Not enough data for KDE",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)

    draw_strike_zone(ax)
    ax.set_xlim(-2.5, 2.5); ax.set_ylim(0.5, 5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Plate Height (ft)")
    ax.set_title(f"Hot Zone (KDE)\n{pitcher_name}", fontsize=10, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(); return fig


def plot_velocity_tendency(df, pitcher_name):
    """Line chart: daily avg RelSpeed per pitch type."""
    fig, ax = plt.subplots(figsize=(11, 3.5))
    apply_dark_theme(fig, [ax])

    if "RelSpeed" not in df.columns or df["RelSpeed"].dropna().empty:
        ax.text(0.5, 0.5, "No velocity data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    vel = df.dropna(subset=["RelSpeed", "Date"])
    if vel.empty:
        ax.text(0.5, 0.5, "No velocity data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    for idx, (pt, g) in enumerate(vel.groupby("TaggedPitchType")):
        daily = g.sort_values("Date").groupby("Date")["RelSpeed"].mean().reset_index()
        ax.plot(daily["Date"], daily["RelSpeed"],
                label=pt, color=PITCH_PALETTE[idx % len(PITCH_PALETTE)],
                lw=1.8, marker="o", ms=4, alpha=0.9)

    ax.set_xlabel("Date"); ax.set_ylabel("Avg Velocity (mph)")
    ax.set_title(f"Velocity Tendency — {pitcher_name}", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, framealpha=0.3, edgecolor=BORDER)
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout(); return fig


def plot_movement_profile(df, pitcher_name):
    """
    Bubble chart: HorzBreak (x) vs InducedVertBreak (y).
    Each pitch type is one bubble, sized by usage count.
    """
    fig, ax = plt.subplots(figsize=(6, 5.5))
    apply_dark_theme(fig, [ax])

    needed = {"HorzBreak", "InducedVertBreak", "TaggedPitchType"}
    if not needed.issubset(df.columns):
        ax.text(0.5, 0.5, "No movement data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    sub = df.dropna(subset=["HorzBreak", "InducedVertBreak"])
    for idx, (pt, g) in enumerate(sub.groupby("TaggedPitchType")):
        x, y, n = g["HorzBreak"].mean(), g["InducedVertBreak"].mean(), len(g)
        color = PITCH_PALETTE[idx % len(PITCH_PALETTE)]
        ax.scatter(x, y, s=max(n * 3, 60), color=color,
                   alpha=0.85, edgecolors="white", linewidths=0.6, zorder=6)
        ax.annotate(pt, (x, y), textcoords="offset points",
                    xytext=(6, 4), fontsize=7, color=color, fontweight="bold")

    ax.axhline(0, color=BORDER, lw=0.8, alpha=0.6)
    ax.axvline(0, color=BORDER, lw=0.8, alpha=0.6)
    ax.set_xlabel("Horizontal Break (in)")
    ax.set_ylabel("Induced Vert Break (in)")
    ax.set_title(f"Movement Profile\n{pitcher_name}", fontsize=10, fontweight="bold")
    fig.tight_layout(); return fig


def plot_release_point(df, pitcher_name):
    """Scatter of release point: RelSide (x) vs RelHeight (y)."""
    fig, ax = plt.subplots(figsize=(5, 5))
    apply_dark_theme(fig, [ax])

    needed = {"RelSide", "RelHeight"}
    if not needed.issubset(df.columns) or df[list(needed)].dropna().empty:
        ax.text(0.5, 0.5, "No release-point data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    sub = df.dropna(subset=["RelSide", "RelHeight"])
    for idx, (pt, g) in enumerate(sub.groupby("TaggedPitchType")):
        ax.scatter(g["RelSide"], g["RelHeight"], label=pt,
                   color=PITCH_PALETTE[idx % len(PITCH_PALETTE)],
                   alpha=0.6, s=18, edgecolors="none", zorder=5)

    ax.set_xlabel("Release Side (ft)")
    ax.set_ylabel("Release Height (ft)")
    ax.set_title(f"Release Point\n{pitcher_name}", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, framealpha=0.3, edgecolor=BORDER)
    fig.tight_layout(); return fig


def export_pitching_pdf(summary_df, disc_df,
                         fig_loc, fig_kde, fig_vel,
                         fig_mov, fig_rel, pitcher_name):
    """Multi-page PDF: summary → discipline → charts."""
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Page 1 — summary table
        fh = max(3, len(summary_df) * 0.45 + 1.5)
        ft, at = plt.subplots(figsize=(12, fh))
        ft.patch.set_facecolor(BG)
        styled_table_pdf(at, summary_df, f"Pitching Summary — {pitcher_name}")
        ft.tight_layout()
        pdf.savefig(ft, bbox_inches="tight", facecolor=BG)
        plt.close(ft)

        # Page 2 — discipline table (if available)
        if not disc_df.empty:
            fh2 = max(3, len(disc_df) * 0.45 + 1.5)
            ft2, at2 = plt.subplots(figsize=(12, fh2))
            ft2.patch.set_facecolor(BG)
            styled_table_pdf(at2, disc_df, f"Pitch Discipline — {pitcher_name}")
            ft2.tight_layout()
            pdf.savefig(ft2, bbox_inches="tight", facecolor=BG)
            plt.close(ft2)

        # Remaining pages — charts
        for fig in [fig_loc, fig_kde, fig_vel, fig_mov, fig_rel]:
            pdf.savefig(fig, bbox_inches="tight", facecolor=BG)

    buf.seek(0); return buf.read()


def render_pitching_dashboard(df):
    """Full pitching dashboard with tab layout."""
    st.markdown('<div class="sh">⚾ Pitching Dashboard</div>', unsafe_allow_html=True)

    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column found."); return

    pitchers = sorted(df["Pitcher"].dropna().unique())
    selected = st.selectbox("Select Pitcher", pitchers, key="sel_pitcher")
    pdf_df   = df[df["Pitcher"] == selected].copy()
    n        = len(pdf_df)

    if n < 15:
        st.warning(
            f"⚠️ **{selected}** — only **{n}** pitches "
            "(min recommended: 15). Data may not be representative.")

    # ── Top KPI row ───────────────────────────────────────────────────────────
    avg_v  = pdf_df["RelSpeed"].mean()  if "RelSpeed"  in pdf_df.columns else np.nan
    max_v  = pdf_df["RelSpeed"].max()   if "RelSpeed"  in pdf_df.columns else np.nan
    avg_sp = pdf_df["SpinRate"].mean()  if "SpinRate"  in pdf_df.columns else np.nan
    ext    = pdf_df["Extension"].mean() if "Extension" in pdf_df.columns else np.nan
    n_pt   = pdf_df["TaggedPitchType"].nunique()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Total Pitches", f"{n:,}")
    with c2: st.metric("Avg Velocity",
                        f"{avg_v:.1f} mph" if not np.isnan(avg_v) else "—",
                        delta=f"Max {max_v:.1f}" if not np.isnan(max_v) else None)
    with c3: st.metric("Avg Spin Rate",
                        f"{avg_sp:.0f} rpm" if not np.isnan(avg_sp) else "—")
    with c4: st.metric("Extension",
                        f"{ext:.1f} ft" if not np.isnan(ext) else "—")
    with c5: st.metric("Pitch Types", str(n_pt))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Summary & Discipline",
        "📍 Locations & Hot Zone",
        "📈 Velocity & Movement",
        "🎯 Release Point",
    ])

    with tab1:
        st.markdown('<div class="sh">📋 Pitch Summary</div>', unsafe_allow_html=True)
        summary_df = build_pitch_summary(pdf_df)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        csv_dl(summary_df, f"{selected}_summary.csv")

        st.markdown('<div class="sh">🎯 Pitch Discipline</div>', unsafe_allow_html=True)
        disc_df = compute_pitch_discipline(pdf_df)
        if disc_df.empty:
            st.info("PitchCall column required for discipline metrics.")
        else:
            st.dataframe(disc_df, use_container_width=True, hide_index=True)
            csv_dl(disc_df, f"{selected}_discipline.csv")

    with tab2:
        cl, cr = st.columns(2)
        fig_loc = plot_pitch_locations(pdf_df, selected)
        fig_kde = plot_hot_zone(pdf_df, selected)
        with cl: st.pyplot(fig_loc, use_container_width=True)
        with cr: st.pyplot(fig_kde, use_container_width=True)

    with tab3:
        fig_vel = plot_velocity_tendency(pdf_df, selected)
        st.pyplot(fig_vel, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        fig_mov = plot_movement_profile(pdf_df, selected)
        st.pyplot(fig_mov, use_container_width=True)

    with tab4:
        fig_rel = plot_release_point(pdf_df, selected)
        st.pyplot(fig_rel, use_container_width=True)

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sh">📤 Export</div>', unsafe_allow_html=True)

    # Ensure all figs exist (user may not have opened every tab)
    if "fig_loc" not in locals(): fig_loc = plot_pitch_locations(pdf_df, selected)
    if "fig_kde" not in locals(): fig_kde = plot_hot_zone(pdf_df, selected)
    if "fig_vel" not in locals(): fig_vel = plot_velocity_tendency(pdf_df, selected)
    if "fig_mov" not in locals(): fig_mov = plot_movement_profile(pdf_df, selected)
    if "fig_rel" not in locals(): fig_rel = plot_release_point(pdf_df, selected)
    if "summary_df" not in locals(): summary_df = build_pitch_summary(pdf_df)
    if "disc_df"    not in locals(): disc_df    = compute_pitch_discipline(pdf_df)

    ec1, ec2 = st.columns(2)
    with ec1:
        pdf_bytes = export_pitching_pdf(
            summary_df,
            disc_df if not disc_df.empty else pd.DataFrame(),
            fig_loc, fig_kde, fig_vel, fig_mov, fig_rel,
            selected)
        st.download_button("⬇️ Download PDF Report", pdf_bytes,
                           f"{selected}_pitching_report.pdf", "application/pdf")
    with ec2:
        csv_dl(pdf_df, f"{selected}_raw_pitches.csv", "⬇️ Download Raw Pitches CSV")

    for fig in [fig_loc, fig_kde, fig_vel, fig_mov, fig_rel]:
        plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# ══ HITTING ANALYTICS ════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

def build_hitting_monthly(df):
    """
    Monthly progression: Pitches, Max/Avg EV, Max/Avg LA,
    Max/Avg Distance, Hard-Hit %, Barrel %.
    Most recent month first.
    """
    df = df.copy()
    df["YearMonth"] = df["Date"].dt.to_period("M")
    optional = {
        "ExitSpeed": ("Max EV",   "Avg EV"),
        "Angle":     ("Max LA",   "Avg LA"),
        "Distance":  ("Max Dist", "Avg Dist"),
    }
    rows = []
    for period, grp in df.groupby("YearMonth"):
        r = {"Month": str(period), "Pitches": len(grp)}
        for col, (mx, av) in optional.items():
            if col in df.columns:
                vals = grp[col].dropna()
                r[mx] = round(vals.max(),  1) if not vals.empty else np.nan
                r[av] = round(vals.mean(), 1) if not vals.empty else np.nan
        # Hard-hit
        if "ExitSpeed" in df.columns:
            ev = grp["ExitSpeed"].dropna()
            r["HH %"] = safe_pct((ev >= 95).sum(), len(ev))
        # Barrel
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrel = (
                (grp["ExitSpeed"].fillna(0) >= 98) &
                (grp["Angle"].fillna(-999)   >= 8)  &
                (grp["Angle"].fillna(-999)   <= 32)
            ).sum()
            r["Barrel %"] = safe_pct(barrel, len(grp))
        rows.append(r)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("Month", ascending=False).reset_index(drop=True)


def compute_plate_discipline(df):
    """
    Batter-level plate discipline: Zone%, Swing%, Contact%,
    Chase%, Whiff%, K%, BB%.  Returns a dict.
    """
    if "PitchCall" not in df.columns:
        return {}

    pc = df["PitchCall"].astype(str)
    ZONE    = {"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable",
               "FoulBallNotFieldable","InPlay"}
    SWING   = {"StrikeSwinging","FoulBall","FoulBallFieldable",
               "FoulBallNotFieldable","InPlay"}
    CONTACT = {"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    WHIFF   = {"StrikeSwinging"}
    BB      = {"BallCalled","HitByPitch","IntentionalBall"}
    KK      = {"StrikeoutSwinging","StrikeoutCalled"}

    n      = len(df)
    in_z   = pc.isin(ZONE).sum()
    swings = pc.isin(SWING).sum()
    cont   = pc.isin(CONTACT).sum()
    whiff  = pc.isin(WHIFF).sum()
    bb     = pc.isin(BB).sum()
    kk     = pc.isin(KK).sum()
    out_z  = max(n - in_z, 1)
    chase  = max(0, swings - cont)

    return {
        "Zone %":    safe_pct(in_z,  n),
        "Swing %":   safe_pct(swings, n),
        "Contact %": safe_pct(cont,  max(swings, 1)),
        "Chase %":   safe_pct(chase, out_z),
        "Whiff %":   safe_pct(whiff, max(swings, 1)),
        "K %":       safe_pct(kk, n),
        "BB %":      safe_pct(bb, n),
    }


def plot_spray_chart(df, batter_name):
    """Distance + Bearing → cartesian spray chart, coloured by ExitSpeed."""
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    apply_dark_theme(fig, [ax])
    ax.set_facecolor("#1a2a1a")

    spray = df.dropna(subset=["Distance", "Bearing"]).copy()
    if spray.empty:
        ax.text(0.5, 0.5, "No spray data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        ax.set_title(f"Spray Chart\n{batter_name}", fontsize=10, fontweight="bold")
        fig.tight_layout(); return fig

    brad = np.deg2rad(spray["Bearing"])
    spray["Hit_X"] = spray["Distance"] * np.sin(brad)
    spray["Hit_Y"] = spray["Distance"] * np.cos(brad)

    # Draw field
    for sign in [1, -1]:
        ax.plot([0, sign * 420 * np.sin(np.deg2rad(45))],
                [0, 420 * np.cos(np.deg2rad(45))],
                color="#8b6914", lw=1.5, alpha=0.7)
    ang = np.linspace(-45, 45, 200)
    for r, ls in [(230, "--"), (330, "--"), (400, "-")]:
        ax.plot(r * np.sin(np.deg2rad(ang)),
                r * np.cos(np.deg2rad(ang)),
                color="#4a5e3a", lw=0.9, alpha=0.45, linestyle=ls)
    bd = 90 * np.sqrt(2) / 2
    ax.plot([0, bd, 0, -bd, 0], [0, bd, 2*bd, bd, 0],
            color="#c8a850", lw=1.0, alpha=0.55)

    has_ev = "ExitSpeed" in spray.columns and spray["ExitSpeed"].notna().any()
    sc = ax.scatter(
        spray["Hit_X"], spray["Hit_Y"],
        c=spray["ExitSpeed"] if has_ev else ACCENT,
        cmap="coolwarm" if has_ev else None,
        s=38, alpha=0.85, edgecolors="none", zorder=5,
        vmin=60, vmax=110)
    if has_ev:
        cb = fig.colorbar(sc, ax=ax, pad=0.02, shrink=0.72)
        cb.set_label("Exit Speed (mph)", color=MUTED, fontsize=8)
        cb.ax.yaxis.set_tick_params(color=MUTED, labelcolor=MUTED)
        cb.outline.set_edgecolor(BORDER)

    ax.set_xlim(-350, 350); ax.set_ylim(-30, 450)
    ax.set_xlabel("Horizontal (ft)"); ax.set_ylabel("Vertical (ft)")
    ax.set_title(f"Spray Chart\n{batter_name}", fontsize=10, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(); return fig


def plot_damage_zone(df, batter_name):
    """Strike-zone scatter coloured by ExitSpeed (damage zone)."""
    fig, ax = plt.subplots(figsize=(5, 5.5))
    apply_dark_theme(fig, [ax])

    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        ax.text(0.5, 0.5, "No location data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
    else:
        has_ev = "ExitSpeed" in loc.columns and loc["ExitSpeed"].notna().any()
        sc = ax.scatter(
            loc["PlateLocSide"], loc["PlateLocHeight"],
            c=loc["ExitSpeed"] if has_ev else ACCENT,
            cmap="coolwarm" if has_ev else None,
            s=32, alpha=0.8, edgecolors="none", zorder=6,
            vmin=60, vmax=110)
        if has_ev:
            cb = fig.colorbar(sc, ax=ax, pad=0.02, shrink=0.72)
            cb.set_label("Exit Speed (mph)", color=MUTED, fontsize=8)
            cb.ax.yaxis.set_tick_params(color=MUTED, labelcolor=MUTED)
            cb.outline.set_edgecolor(BORDER)

    draw_strike_zone(ax)
    ax.set_xlim(-2.5, 2.5); ax.set_ylim(0.5, 5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Plate Height (ft)")
    ax.set_title(f"Damage Zone\n{batter_name}", fontsize=10, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(); return fig


def plot_ev_distribution(df, batter_name):
    """Histogram of Exit Velocity with mean line and hard-hit threshold."""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    apply_dark_theme(fig, [ax])

    ev = (df["ExitSpeed"].dropna()
          if "ExitSpeed" in df.columns else pd.Series(dtype=float))
    if ev.empty:
        ax.text(0.5, 0.5, "No EV data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    ax.hist(ev, bins=20, color=BLUE, alpha=0.75, edgecolor=BG, linewidth=0.4)
    ax.axvline(ev.mean(), color=ACCENT, lw=1.8, linestyle="--",
               label=f"Avg {ev.mean():.1f}")
    ax.axvline(95, color=RED, lw=1.4, linestyle=":", label="Hard Hit (95)")
    ax.set_xlabel("Exit Velocity (mph)"); ax.set_ylabel("Frequency")
    ax.set_title(f"Exit Velo Distribution\n{batter_name}",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, framealpha=0.3, edgecolor=BORDER)
    fig.tight_layout(); return fig


def plot_la_distribution(df, batter_name):
    """Histogram of Launch Angle with barrel-zone shading."""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    apply_dark_theme(fig, [ax])

    la = (df["Angle"].dropna()
          if "Angle" in df.columns else pd.Series(dtype=float))
    if la.empty:
        ax.text(0.5, 0.5, "No LA data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    ax.hist(la, bins=20, color=GREEN, alpha=0.75, edgecolor=BG, linewidth=0.4)
    ax.axvspan(8, 32, alpha=0.12, color=ACCENT, label="Barrel zone (8–32°)")
    ax.axvline(la.mean(), color=ACCENT, lw=1.8, linestyle="--",
               label=f"Avg {la.mean():.1f}°")
    ax.set_xlabel("Launch Angle (°)"); ax.set_ylabel("Frequency")
    ax.set_title(f"Launch Angle Distribution\n{batter_name}",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, framealpha=0.3, edgecolor=BORDER)
    fig.tight_layout(); return fig


def plot_rolling_ev(df, batter_name, window=7):
    """Rolling 7-day average exit speed trend with daily scatter."""
    fig, ax = plt.subplots(figsize=(11, 3.2))
    apply_dark_theme(fig, [ax])

    if "ExitSpeed" not in df.columns or df["ExitSpeed"].dropna().empty:
        ax.text(0.5, 0.5, "No EV data",
                ha="center", va="center", color=MUTED, transform=ax.transAxes)
        fig.tight_layout(); return fig

    daily = (df.dropna(subset=["ExitSpeed", "Date"])
               .groupby("Date")["ExitSpeed"].mean()
               .reset_index().sort_values("Date"))
    daily["Rolling"] = daily["ExitSpeed"].rolling(window, min_periods=1).mean()

    ax.fill_between(daily["Date"], daily["ExitSpeed"], alpha=0.13, color=BLUE)
    ax.plot(daily["Date"], daily["ExitSpeed"],
            color=BLUE, lw=1.0, alpha=0.5, label="Daily Avg")
    ax.plot(daily["Date"], daily["Rolling"],
            color=ACCENT, lw=2.0, label=f"{window}-day Rolling Avg")
    ax.axhline(95, color=RED, lw=1.0, linestyle=":", alpha=0.6, label="Hard Hit (95)")
    ax.set_xlabel("Date"); ax.set_ylabel("Exit Speed (mph)")
    ax.set_title(f"Rolling Avg Exit Speed — {batter_name}",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, framealpha=0.3, edgecolor=BORDER)
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout(); return fig


def export_hitting_pdf(monthly_df, disc_stats,
                        fig_spray, fig_dmg,
                        fig_ev, fig_la, fig_roll, batter_name):
    """Multi-page PDF: monthly → discipline → charts."""
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Page 1 — monthly table
        fh = max(3, len(monthly_df) * 0.5 + 1.5)
        ft, at = plt.subplots(figsize=(14, fh))
        ft.patch.set_facecolor(BG)
        styled_table_pdf(at, monthly_df, f"Monthly Progression — {batter_name}")
        ft.tight_layout()
        pdf.savefig(ft, bbox_inches="tight", facecolor=BG)
        plt.close(ft)

        # Page 2 — discipline table
        if disc_stats:
            ft2, at2 = plt.subplots(figsize=(12, 3))
            ft2.patch.set_facecolor(BG)
            styled_table_pdf(at2, pd.DataFrame([disc_stats]),
                             f"Plate Discipline — {batter_name}")
            ft2.tight_layout()
            pdf.savefig(ft2, bbox_inches="tight", facecolor=BG)
            plt.close(ft2)

        for fig in [fig_spray, fig_dmg, fig_ev, fig_la, fig_roll]:
            pdf.savefig(fig, bbox_inches="tight", facecolor=BG)

    buf.seek(0); return buf.read()


def render_hitting_dashboard(df):
    """Full hitting dashboard with tab layout."""
    st.markdown('<div class="sh">🏏 Hitting Dashboard</div>', unsafe_allow_html=True)

    if "Batter" not in df.columns or df["Batter"].dropna().empty:
        st.error("No 'Batter' column found."); return

    batters  = sorted(df["Batter"].dropna().unique())
    selected = st.selectbox("Select Batter", batters, key="sel_batter")
    bdf      = df[df["Batter"] == selected].copy()
    n        = len(bdf)

    if n < 15:
        st.warning(
            f"⚠️ **{selected}** — only **{n}** pitches seen "
            "(min recommended: 15).")

    # ── Compute summary stats ─────────────────────────────────────────────────
    avg_ev  = bdf["ExitSpeed"].mean()  if "ExitSpeed" in bdf.columns else np.nan
    max_ev  = bdf["ExitSpeed"].max()   if "ExitSpeed" in bdf.columns else np.nan
    avg_la  = bdf["Angle"].mean()      if "Angle"     in bdf.columns else np.nan
    avg_dis = bdf["Distance"].mean()   if "Distance"  in bdf.columns else np.nan

    hh_rate, barrel_rate = 0.0, 0.0
    if "ExitSpeed" in bdf.columns:
        ev_s = bdf["ExitSpeed"].dropna()
        hh_rate = safe_pct((ev_s >= 95).sum(), len(ev_s))
    if "ExitSpeed" in bdf.columns and "Angle" in bdf.columns:
        barrel = (
            (bdf["ExitSpeed"].fillna(0) >= 98) &
            (bdf["Angle"].fillna(-999)   >= 8)  &
            (bdf["Angle"].fillna(-999)   <= 32)
        ).sum()
        barrel_rate = safe_pct(barrel, n)

    disc = compute_plate_discipline(bdf)

    # ── Top KPI row ───────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("Pitches Seen", f"{n:,}")
    with c2: st.metric("Avg Exit Velo",
                        f"{avg_ev:.1f} mph" if not np.isnan(avg_ev) else "—",
                        delta=f"Max {max_ev:.1f}" if not np.isnan(max_ev) else None)
    with c3: st.metric("Avg Launch Angle",
                        f"{avg_la:.1f}°" if not np.isnan(avg_la) else "—")
    with c4: st.metric("Avg Distance",
                        f"{avg_dis:.0f} ft" if not np.isnan(avg_dis) else "—")
    with c5: st.metric("Hard Hit %",   f"{hh_rate:.1f}%")
    with c6: st.metric("Barrel %",     f"{barrel_rate:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Plate discipline badge row ────────────────────────────────────────────
    if disc:
        st.markdown('<div class="sh">🎯 Plate Discipline</div>', unsafe_allow_html=True)
        badge_cols = st.columns(len(disc))
        for col, (k, v) in zip(badge_cols, disc.items()):
            with col:
                st.markdown(f"""
                <div class="stat-badge">
                  <div class="val">{v}%</div>
                  <div class="lbl">{k}</div>
                </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "📅 Monthly Progression",
        "🗺️ Spray Chart & Damage Zone",
        "📊 EV & LA Distributions",
    ])

    with tab1:
        monthly_df = build_hitting_monthly(bdf)
        if monthly_df.empty:
            st.info("No monthly data available.")
        else:
            st.dataframe(monthly_df, use_container_width=True, hide_index=True)
            csv_dl(monthly_df, f"{selected}_monthly.csv")

    with tab2:
        cl, cr = st.columns(2)
        fig_spray = plot_spray_chart(bdf, selected)
        fig_dmg   = plot_damage_zone(bdf, selected)
        with cl: st.pyplot(fig_spray, use_container_width=True)
        with cr: st.pyplot(fig_dmg,   use_container_width=True)

    with tab3:
        cl2, cr2 = st.columns(2)
        fig_ev = plot_ev_distribution(bdf, selected)
        fig_la = plot_la_distribution(bdf, selected)
        with cl2: st.pyplot(fig_ev, use_container_width=True)
        with cr2: st.pyplot(fig_la, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        fig_roll = plot_rolling_ev(bdf, selected)
        st.pyplot(fig_roll, use_container_width=True)

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sh">📤 Export</div>', unsafe_allow_html=True)

    # Ensure all figures exist before building PDF
    if "monthly_df" not in locals(): monthly_df = build_hitting_monthly(bdf)
    if "fig_spray"  not in locals(): fig_spray  = plot_spray_chart(bdf, selected)
    if "fig_dmg"    not in locals(): fig_dmg    = plot_damage_zone(bdf, selected)
    if "fig_ev"     not in locals(): fig_ev     = plot_ev_distribution(bdf, selected)
    if "fig_la"     not in locals(): fig_la     = plot_la_distribution(bdf, selected)
    if "fig_roll"   not in locals(): fig_roll   = plot_rolling_ev(bdf, selected)

    ec1, ec2 = st.columns(2)
    with ec1:
        if not monthly_df.empty:
            pdf_bytes = export_hitting_pdf(
                monthly_df, disc,
                fig_spray, fig_dmg,
                fig_ev, fig_la, fig_roll,
                selected)
            st.download_button("⬇️ Download PDF Report", pdf_bytes,
                               f"{selected}_hitting_report.pdf", "application/pdf")
        else:
            st.info("Monthly data required for PDF export.")
    with ec2:
        csv_dl(bdf, f"{selected}_raw_pitches.csv", "⬇️ Download Raw Pitches CSV")

    for fig in [fig_spray, fig_dmg, fig_ev, fig_la, fig_roll]:
        plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # ── Hero banner ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero">
      <div class="hero-icon">⚾</div>
      <div>
        <div class="hero-title">
          Trackman <span>Analytics</span>
          <span style="font-size:1.1rem;color:#8b949e;font-weight:400"> v2.0</span>
        </div>
        <div class="hero-sub">
          Advanced baseball data science platform for pitching &amp; hitting
        </div>
        <div class="hero-pills">
          <span class="pill">Multi-Date Picker</span>
          <span class="pill">Pitch Discipline</span>
          <span class="pill">Movement Profile</span>
          <span class="pill">Release Point</span>
          <span class="pill">Barrel %</span>
          <span class="pill">Hard-Hit Rate</span>
          <span class="pill">Rolling EV Trend</span>
          <span class="pill">PDF + CSV Export</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar — File upload ─────────────────────────────────────────────────
    st.sidebar.markdown(
        '<span class="sb-label">📂 Upload Data</span>', unsafe_allow_html=True)
    uploaded = st.sidebar.file_uploader(
        "Upload Trackman CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help="One or more Trackman export CSV files.",
    )

    if not uploaded:
        st.markdown("""
        <div class="upload-zone">
          <div class="big">📂</div>
          <div class="ttl">Upload your Trackman CSV files to begin</div>
          <div class="sub">
            Use the sidebar to upload one or multiple Trackman export files.<br>
            The dashboard will automatically merge, clean, and analyse your data.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("🔄 Loading and cleaning data…"):
        master = load_and_clean(uploaded)

    if master.empty:
        st.error("❌ No valid data could be loaded. Please check your CSV files.")
        return

    st.sidebar.success(
        f"✅ **{len(master):,}** pitches from **{len(uploaded)}** file(s).")

    # ── Multi-date filter ─────────────────────────────────────────────────────
    filtered = sidebar_date_filter(master)
    if filtered.empty:
        st.warning("⚠️ No data matches the selected dates."); return

    # ── Advanced filters ──────────────────────────────────────────────────────
    filtered = advanced_filters(filtered)
    if filtered.empty:
        st.warning("⚠️ No data matches the advanced filters."); return

    # ── Dashboard mode selector ───────────────────────────────────────────────
    st.sidebar.markdown(
        '<span class="sb-label">🎯 Dashboard Mode</span>', unsafe_allow_html=True)
    mode = st.sidebar.radio(
        "mode",
        ["⚾ Pitching", "🏏 Hitting"],
        key="dash_mode",
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Built with ❤️ · Streamlit · Pandas · Matplotlib · Seaborn")

    # ── Route ─────────────────────────────────────────────────────────────────
    if mode == "⚾ Pitching":
        render_pitching_dashboard(filtered)
    else:
        render_hitting_dashboard(filtered)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()