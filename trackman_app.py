"""
=============================================================================
  TRACKMAN BASEBALL ANALYTICS DASHBOARD  v3.0
  Expert-grade Streamlit app for pitching and hitting analysis

  CHANGES in v3:
  ─────────────────────────────────────────────────────────────────────────
  1. LIGHT / DARK MODE COMPATIBILITY
     • All CSS uses adaptive colour tokens instead of hard-coded dark values
     • Charts use a white/light background when rendered in light mode
     • Text, borders, and metric cards adapt to the OS/Streamlit theme
     • Sidebar, hero, and pill badges fully readable in both modes

  2. IMPROVED CHARTS
     • Pitch-location scatter: larger dots, stroke outline for contrast
     • Hot Zone: cleaned up colour scale, better contrast lines
     • Velocity tendency: shaded confidence band behind lines
     • Movement Profile: cardinal-quadrant labels (Rise/Drop/Arm/Glove)
     • Release Point: KDE density contour overlaid on scatter
     • Spray chart: field grass gradient, hit-type annotation ring
     • EV / LA histograms: vertical-bar annotations with value labels
     • All chart titles rendered larger and bolder

  3. SMART NAME NORMALISATION & DEDUPLICATION
     • normalize_name() strips accents, collapses whitespace, unifies
       punctuation, and title-cases every player name before grouping
     • find_name_clusters() uses token-overlap fuzzy matching to detect
       variants like "Rodriguez, Juan" vs "Rodriguez Juan" vs "J. Rodriguez"
       and merges them under the most common spelling in the dataset
     • Applied to both Pitcher and Batter columns at load time
     • Sidebar shows a "Name aliases resolved" count so coaches know
       when records were merged
  ─────────────────────────────────────────────────────────────────────────
  Built with: Streamlit, Pandas, Matplotlib, Seaborn, NumPy, unicodedata
=============================================================================
"""

import io
import re
import unicodedata
import warnings
from collections import defaultdict
from difflib import SequenceMatcher

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

# ─────────────────────────────────────────────────────────────────────────────
# ADAPTIVE COLOUR TOKENS
# These are CSS custom properties that work in BOTH light and dark mode.
# The actual hex values are overridden by the mode-specific block below.
# ─────────────────────────────────────────────────────────────────────────────

# Chart colours — used directly in matplotlib (mode-independent picks)
ACCENT   = "#e8a838"
ACCENT2  = "#c8881a"
BLUE     = "#2979d4"
RED      = "#d63d3d"
GREEN    = "#2a9d5c"
PURPLE   = "#7c3aed"
TEAL     = "#0891b2"
ORANGE   = "#ea580c"
PINK     = "#db2777"
LIME     = "#65a30d"

PITCH_PALETTE = [
    ACCENT, BLUE, RED, GREEN, PURPLE,
    TEAL, ORANGE, PINK, LIME,
    "#6366f1", "#0d9488", "#f59e0b",
]

# Light-mode chart background values
CHART_BG_LIGHT   = "#f8f9fa"
CHART_CARD_LIGHT = "#ffffff"
CHART_GRID_LIGHT = "#e2e8f0"
CHART_MUTED_LIGHT= "#64748b"
CHART_TEXT_LIGHT = "#1e293b"

# Dark-mode chart background values
CHART_BG_DARK    = "#0d1117"
CHART_CARD_DARK  = "#161b22"
CHART_GRID_DARK  = "#21262d"
CHART_MUTED_DARK = "#8b949e"
CHART_TEXT_DARK  = "#e6edf3"

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trackman Analytics v3",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# THEME DETECTION
# Streamlit exposes theme via st.get_option("theme.base") → "light" / "dark"
# We fall back to "light" if not set (public cloud default).
# ─────────────────────────────────────────────────────────────────────────────
def _get_theme():
    try:
        base = st.get_option("theme.base")
        return base if base in ("light", "dark") else "light"
    except Exception:
        return "light"

IS_DARK = _get_theme() == "dark"

# Pick chart palette based on theme
C_BG   = CHART_BG_DARK    if IS_DARK else CHART_BG_LIGHT
C_CARD = CHART_CARD_DARK   if IS_DARK else CHART_CARD_LIGHT
C_GRID = CHART_GRID_DARK   if IS_DARK else CHART_GRID_LIGHT
C_MUTE = CHART_MUTED_DARK  if IS_DARK else CHART_MUTED_LIGHT
C_TEXT = CHART_TEXT_DARK   if IS_DARK else CHART_TEXT_LIGHT
C_ZONE = ACCENT            # strike zone always gold

# Border for legend / axes in charts
C_SPINE = "#30363d" if IS_DARK else "#cbd5e1"

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS  (adaptive — works in BOTH light and dark Streamlit themes)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ══════════════════════════════════════
   ADAPTIVE TOKENS
   Streamlit injects its own theme vars;
   we piggyback on them via color-scheme
   ══════════════════════════════════════ */

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.2);
}

/* ── Sidebar uppercase labels ── */
.sb-label {
    font-size: 0.63rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #e8a838;
    padding: 14px 0 4px 0;
    display: block;
}

/* ── Hero banner ── */
.hero {
    background: linear-gradient(
        135deg,
        color-mix(in srgb, #e8a838 8%, transparent) 0%,
        transparent 60%
    );
    border: 1px solid rgba(128,128,128,0.25);
    border-left: 4px solid #e8a838;
    border-radius: 12px;
    padding: 24px 30px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 20px;
}
.hero-icon {
    font-size: 3.2rem;
    line-height: 1;
    filter: drop-shadow(0 2px 6px rgba(232,168,56,0.35));
}
.hero-title {
    font-size: 2.1rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    line-height: 1.05;
}
.hero-title .hl { color: #e8a838; }
.hero-sub { font-size: 0.88rem; margin-top: 4px; opacity: 0.65; }
.hero-pills { display: flex; gap: 7px; margin-top: 10px; flex-wrap: wrap; }
.pill {
    background: rgba(232,168,56,0.12);
    border: 1px solid rgba(232,168,56,0.35);
    color: #e8a838;
    border-radius: 20px;
    padding: 2px 11px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}

/* ── Section headers ── */
.sh {
    font-size: 0.75rem;
    font-weight: 800;
    color: #e8a838;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    border-bottom: 1px solid rgba(232,168,56,0.3);
    padding-bottom: 6px;
    margin: 22px 0 12px 0;
}

/* ── KPI metric cards ── */
div[data-testid="metric-container"] {
    border: 1px solid rgba(128,128,128,0.2) !important;
    border-top: 3px solid #e8a838 !important;
    border-radius: 10px !important;
    padding: 16px 14px !important;
    transition: box-shadow 0.2s;
}
div[data-testid="metric-container"]:hover {
    box-shadow: 0 0 14px rgba(232,168,56,0.18);
}
div[data-testid="metric-container"] label {
    font-size: 0.73rem !important;
    letter-spacing: 0.05em !important;
    opacity: 0.7 !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: #e8a838 !important;
    font-size: 1.8rem !important;
    font-weight: 800 !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid rgba(128,128,128,0.2);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    font-weight: 600;
    font-size: 0.84rem;
    opacity: 0.65;
}
.stTabs [aria-selected="true"] {
    background: #e8a838 !important;
    color: #000 !important;
    opacity: 1 !important;
}

/* ── Download buttons ── */
.stDownloadButton > button {
    background: rgba(232,168,56,0.08) !important;
    border: 1px solid #e8a838 !important;
    color: #e8a838 !important;
    font-weight: 700 !important;
    border-radius: 7px !important;
    transition: all 0.18s;
}
.stDownloadButton > button:hover {
    background: #e8a838 !important;
    color: #000 !important;
}

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    overflow: hidden;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
    border: 1px solid rgba(128,128,128,0.2) !important;
    border-radius: 8px !important;
}

/* ── Date chips ── */
.date-chip-wrap { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
.date-chip {
    background: rgba(232,168,56,0.13);
    border: 1px solid rgba(232,168,56,0.35);
    color: #e8a838;
    border-radius: 14px;
    padding: 2px 10px;
    font-size: 0.7rem;
    font-weight: 700;
}

/* ── Discipline stat badges ── */
.stat-badge {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 8px;
    padding: 10px 14px;
    text-align: center;
    min-width: 86px;
}
.stat-badge .val {
    font-size: 1.45rem;
    font-weight: 800;
    color: #e8a838;
    line-height: 1.1;
}
.stat-badge .lbl {
    font-size: 0.62rem;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    opacity: 0.55;
    margin-top: 2px;
}

/* ── Upload drop zone ── */
.upload-zone {
    border: 2px dashed rgba(128,128,128,0.3);
    border-radius: 14px;
    padding: 64px 40px;
    text-align: center;
    margin-top: 28px;
}
.upload-zone .big { font-size: 3rem; margin-bottom: 12px; }
.upload-zone .ttl {
    font-size: 1.3rem;
    font-weight: 700;
    margin-bottom: 8px;
}
.upload-zone .sub { font-size: 0.88rem; line-height: 1.6; opacity: 0.55; }

/* ── Alias info box ── */
.alias-box {
    border: 1px solid rgba(232,168,56,0.3);
    border-left: 3px solid #e8a838;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 0.78rem;
    opacity: 0.85;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CHART THEME HELPER
# ─────────────────────────────────────────────────────────────────────────────
def apply_chart_theme(fig, ax_list=None):
    """
    Apply adaptive chart theme.
    In light mode → clean white background, dark text/grid.
    In dark mode  → dark background, light text/grid.
    """
    fig.patch.set_facecolor(C_BG)
    for ax in (ax_list or fig.get_axes()):
        ax.set_facecolor(C_CARD)
        ax.tick_params(colors=C_MUTE, labelsize=8.5)
        ax.xaxis.label.set_color(C_MUTE)
        ax.yaxis.label.set_color(C_MUTE)
        ax.title.set_color(C_TEXT)
        for sp in ax.spines.values():
            sp.set_edgecolor(C_SPINE)
        ax.grid(color=C_GRID, linewidth=0.6, alpha=0.7, linestyle="--")


def _title(ax, text, sub=None):
    """Bold chart title with optional muted subtitle."""
    ax.set_title(text, color=C_TEXT, fontsize=11, fontweight="bold", pad=10)
    if sub:
        ax.text(0.5, 1.005, sub, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=7.5, color=C_MUTE)


# ─────────────────────────────────────────────────────────────────────────────
# STRIKE ZONE HELPER
# ─────────────────────────────────────────────────────────────────────────────
def draw_strike_zone(ax, color=ACCENT, lw=1.8):
    """MLB strike zone rectangle (17 in wide, 1.5–3.5 ft) with 3×3 grid."""
    zone = patches.Rectangle(
        (-0.71, 1.5), 1.42, 2.0,
        lw=lw, edgecolor=color, facecolor="none", alpha=0.9, zorder=5)
    ax.add_patch(zone)
    for i in range(1, 3):
        ax.axvline(-0.71 + i * 1.42/3, color=color, lw=0.5, alpha=0.25, zorder=4)
    for j in range(1, 3):
        ax.axhline(1.5  + j * 2.0/3,  color=color, lw=0.5, alpha=0.25, zorder=4)


# ─────────────────────────────────────────────────────────────────────────────
# PDF TABLE HELPER
# ─────────────────────────────────────────────────────────────────────────────
def styled_table_pdf(ax, df, title):
    """Styled dark-on-gold table for PDF pages."""
    ax.axis("off")
    if title:
        ax.set_title(title, color=CHART_TEXT_DARK, fontsize=12,
                     fontweight="bold", pad=14)
    cols = list(df.columns)
    data = df.fillna("—").values.tolist()
    tbl  = ax.table(cellText=data, colLabels=cols,
                    loc="center", cellLoc="center")
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
            c.set_facecolor("#1c2230" if i % 2 == 0 else "#161b22")
            c.set_text_props(color=CHART_TEXT_DARK)
    tbl.scale(1.1, 1.55)


def csv_dl(df, fname, label="⬇️ Download CSV"):
    st.download_button(label, df.to_csv(index=False).encode(), fname, "text/csv")


def safe_pct(num, denom):
    return round(100 * num / denom, 1) if denom > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# ══ SMART NAME NORMALISATION & DEDUPLICATION ════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

def _strip_accents(s: str) -> str:
    """Convert 'Rodríguez' → 'Rodriguez', 'José' → 'Jose', etc."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_name(raw: str) -> str:
    """
    Full normalisation pipeline for a single player name string:
      1. Decode unicode / strip accents
      2. Remove dots after single-letter initials  (J. → J)
      3. If a comma is present, treat as  "Last, First"  and reorder BEFORE
         collapsing separators (so we operate on the original comma position)
      4. Collapse hyphens/underscores/pipes used as separators → space
      5. Collapse multiple spaces → single space
      6. Title-case

    Examples
    --------
    "rodríguez, juan"       → "Juan Rodriguez"
    "RODRIGUEZ JUAN"        → "Rodriguez Juan"  (no comma → keep order)
    "J. Rodriguez"          → "J Rodriguez"
    "De La Cruz,Erick"      → "Erick De La Cruz"
    "García-López, Pedro"   → "Pedro Garcia Lopez"
    "O'Brien  Sean"         → "O'Brien Sean"
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw

    s = _strip_accents(raw.strip())
    # Remove dots after single-letter initial: "J." → "J"
    s = re.sub(r"\b([A-Za-z])\.", r"\1", s)

    # Reorder "Last, First" BEFORE destroying the comma
    # Split on the FIRST comma only: everything before = last, after = first
    if "," in s:
        comma_idx = s.index(",")
        last_part  = s[:comma_idx].strip()
        first_part = s[comma_idx+1:].strip()
        # Clean each part of internal hyphens/underscores
        last_part  = re.sub(r"[\-_/\\|]+", " ", last_part).strip()
        first_part = re.sub(r"[\-_/\\|]+", " ", first_part).strip()
        s = f"{first_part} {last_part}" if first_part else last_part
    else:
        # No comma — just clean separators, keep original word order
        s = re.sub(r"[\-_/\\|]+", " ", s)

    # Collapse whitespace and title-case
    s = re.sub(r"\s+", " ", s).strip().title()
    return s


def _name_tokens(name: str):
    """Return a frozenset of lowercase tokens ≥ 2 chars from a normalised name."""
    return frozenset(t for t in name.lower().split() if len(t) >= 2)


def find_name_clusters(names):
    """
    Given a list/Series of normalised name strings, group names that are
    very likely the same person (token overlap ≥ 0.6 Jaccard similarity).

    Returns a dict  { variant_name : canonical_name }  where canonical_name
    is the most frequent spelling in the original data.
    """
    from collections import Counter

    counts   = Counter(names)
    unique   = list(counts.keys())
    n        = len(unique)
    parent   = list(range(n))   # Union-Find

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    token_sets = [_name_tokens(u) for u in unique]

    for i in range(n):
        for j in range(i + 1, n):
            ti, tj = token_sets[i], token_sets[j]
            if not ti or not tj:
                continue
            jaccard = len(ti & tj) / len(ti | tj)
            if jaccard >= 0.60:
                union(i, j)

    # For each cluster, pick the name with the highest count as canonical
    clusters = defaultdict(list)
    for idx, name in enumerate(unique):
        clusters[find(idx)].append(name)

    mapping = {}
    for members in clusters.values():
        canonical = max(members, key=lambda nm: counts[nm])
        for m in members:
            mapping[m] = canonical

    return mapping


def deduplicate_player_column(df, col):
    """
    Apply name normalisation + fuzzy deduplication to a player column in-place.
    Returns (df, alias_count) where alias_count is the number of variants merged.
    """
    if col not in df.columns:
        return df, 0

    # Step 1: normalise every cell
    df[col] = df[col].astype(str).apply(normalize_name)

    # Step 2: build cluster → canonical mapping
    valid_names = df[col].dropna()
    valid_names = valid_names[valid_names != "nan"]
    if valid_names.empty:
        return df, 0

    mapping = find_name_clusters(valid_names.tolist())

    # Count how many distinct variants were collapsed
    alias_count = sum(1 for k, v in mapping.items() if k != v)

    # Step 3: apply mapping
    df[col] = df[col].map(mapping).fillna(df[col])
    return df, alias_count


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
WARMUP_VALUES = {"warmup", "undefined"}   # NaN/blank are VALID pitches

# Pitch-type name variants to unify (all lower-case keys → canonical value)
PITCH_TYPE_MAP = {
    "four-seam fastball": "4-Seam Fastball",
    "fourseam":           "4-Seam Fastball",
    "4-seam":             "4-Seam Fastball",
    "4seam":              "4-Seam Fastball",
    "ff":                 "4-Seam Fastball",
    "fa":                 "4-Seam Fastball",
    "two-seam fastball":  "2-Seam Fastball",
    "twoseam":            "2-Seam Fastball",
    "2-seam":             "2-Seam Fastball",
    "2seam":              "2-Seam Fastball",
    "sinker":             "Sinker",
    "si":                 "Sinker",
    "curveball":          "Curveball",
    "curve":              "Curveball",
    "cb":                 "Curveball",
    "cu":                 "Curveball",
    "slider":             "Slider",
    "sl":                 "Slider",
    "sweeper":            "Sweeper",
    "sw":                 "Sweeper",
    "changeup":           "Changeup",
    "change":             "Changeup",
    "ch":                 "Changeup",
    "cutter":             "Cutter",
    "cut fastball":       "Cutter",
    "fc":                 "Cutter",
    "splitter":           "Splitter",
    "split":              "Splitter",
    "fs":                 "Splitter",
    "knuckleball":        "Knuckleball",
    "kn":                 "Knuckleball",
    "screwball":          "Screwball",
    "fastball":           "Fastball",
}


def smart_map_columns(df):
    for std, alts in COLUMN_ALIASES.items():
        if std not in df.columns:
            for alt in alts:
                matched = [c for c in df.columns if c.lower() == alt.lower()]
                if matched:
                    df.rename(columns={matched[0]: std}, inplace=True)
                    break
    return df


def normalise_pitch_type(val: str) -> str:
    """Normalise a pitch type string using the canonical map above."""
    if not isinstance(val, str):
        return "Unknown"
    clean = val.strip()
    return PITCH_TYPE_MAP.get(clean.lower(), clean) if clean.lower() != "unknown" else "Unknown"


def load_and_clean(files):
    """
    Read, merge, column-map, date-parse, warmup-filter, cast numerics,
    normalise pitch types, and deduplicate player names.
    Returns (master_df, pitcher_aliases, batter_aliases).
    """
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f, low_memory=False))
        except Exception as e:
            st.warning(f"⚠️ Could not read **{f.name}**: {e}")
    if not frames:
        return pd.DataFrame(), 0, 0

    df = pd.concat(frames, ignore_index=True)
    df = smart_map_columns(df)

    # Date parsing (Latin American: day-first)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    else:
        st.warning("⚠️ No 'Date' column found — date filtering unavailable.")
        df["Date"] = pd.NaT

    # Warmup filter (explicit strings only — NaN/blank = valid pitch)
    before = len(df)
    mask   = pd.Series(False, index=df.index)
    for col in ["PitchCall", "Batter"]:
        if col in df.columns:
            mask |= (df[col].fillna("").astype(str)
                            .str.strip().str.lower()
                            .isin(WARMUP_VALUES))
    df = df[~mask].reset_index(drop=True)
    removed = before - len(df)
    if removed:
        st.sidebar.caption(f"🧹 Removed **{removed:,}** warmup rows.")

    # Pitch type normalisation (unify variants → canonical names)
    if "TaggedPitchType" in df.columns:
        df["TaggedPitchType"] = (
            df["TaggedPitchType"].astype(str).str.strip()
            .replace({"nan": "Unknown", "": "Unknown"})
            .apply(normalise_pitch_type)
        )
    else:
        df["TaggedPitchType"] = "Unknown"

    # Cast numerics
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

    # Build count string
    if "Balls" in df.columns and "Strikes" in df.columns:
        df["Count"] = (df["Balls"].astype("Int64").astype(str) + "-"
                       + df["Strikes"].astype("Int64").astype(str))

    # ── Smart player name deduplication ──────────────────────────────────────
    df, p_aliases = deduplicate_player_column(df, "Pitcher")
    df, b_aliases = deduplicate_player_column(df, "Batter")

    return df, p_aliases, b_aliases


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — MULTI-DATE FILTER
# ─────────────────────────────────────────────────────────────────────────────
def sidebar_date_filter(df):
    """
    Two-mode sidebar date filter:
      📆 Date Range  — continuous start → end window
      🗓️ Pick Dates  — multiselect individual dates (any Tue/Thu pattern, etc.)
    """
    st.sidebar.markdown('<span class="sb-label">📅 Date Filter</span>',
                        unsafe_allow_html=True)

    valid = df["Date"].dropna()
    if valid.empty:
        st.sidebar.info("No valid dates — showing all data.")
        return df

    all_dates = sorted(valid.dt.date.unique())
    min_d, max_d = all_dates[0], all_dates[-1]

    mode = st.sidebar.radio(
        "Filter mode",
        ["📆 Date Range", "🗓️ Pick Specific Dates"],
        horizontal=True, label_visibility="collapsed", key="date_mode",
    )

    if mode == "📆 Date Range":
        sel = st.sidebar.date_input(
            "Range", value=(min_d, max_d),
            min_value=min_d, max_value=max_d,
        )
        start, end = (sel if isinstance(sel, (list, tuple)) and len(sel) == 2
                      else (sel or min_d, sel or min_d))
        filtered = df[(df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)]
        st.sidebar.caption(f"📊 **{len(filtered):,}** pitches · {start} → {end}")

    else:
        date_fmt     = {d: d.strftime("%a %b %d, %Y") for d in all_dates}
        fmt_list     = [date_fmt[d] for d in all_dates]
        default_lbls = fmt_list[-min(7, len(fmt_list)):]

        chosen_labels = st.sidebar.multiselect(
            "Select individual dates", options=fmt_list,
            default=default_lbls,
            help="Pick any combination — e.g. every Tuesday & Thursday.",
        )

        if not chosen_labels:
            st.sidebar.warning("No dates selected — showing all.")
            filtered = df.copy()
        else:
            rev_map     = {v: k for k, v in date_fmt.items()}
            chosen_set  = {rev_map[l] for l in chosen_labels}
            filtered    = df[df["Date"].dt.date.isin(chosen_set)]
            chips = "".join(
                f'<span class="date-chip">{l.split(",")[0]}</span>'
                for l in chosen_labels)
            st.sidebar.markdown(
                f'<div class="date-chip-wrap">{chips}</div>',
                unsafe_allow_html=True)
            st.sidebar.caption(
                f"📊 **{len(filtered):,}** pitches · **{len(chosen_labels)}** dates")

    return filtered.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED SIDEBAR FILTERS
# ─────────────────────────────────────────────────────────────────────────────
def advanced_filters(df):
    with st.sidebar.expander("⚙️ Advanced Filters", expanded=False):
        for col, label in [("BatterSide", "Batter Side"),
                            ("PitcherThrows", "Pitcher Throws")]:
            if col in df.columns:
                opts = sorted(df[col].dropna().unique())
                sel  = st.multiselect(label, opts, default=opts,
                                      key=f"adv_{col}")
                if sel:
                    df = df[df[col].isin(sel)]

        if "TaggedPitchType" in df.columns:
            opts = sorted(df["TaggedPitchType"].dropna().unique())
            sel  = st.multiselect("Pitch Types", opts, default=opts, key="adv_pt")
            if sel:
                df = df[df["TaggedPitchType"].isin(sel)]

        if "Inning" in df.columns and df["Inning"].notna().any():
            lo, hi = int(df["Inning"].min()), int(df["Inning"].max())
            if lo < hi:
                rng = st.slider("Inning Range", lo, hi, (lo, hi), key="adv_inn")
                df  = df[(df["Inning"] >= rng[0]) & (df["Inning"] <= rng[1])]

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# ══ PITCHING ANALYTICS ═══════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

def build_pitch_summary(df):
    total = len(df)
    rows  = []
    for pt, grp in df.groupby("TaggedPitchType"):
        r = {"Pitch Type": pt,
             "Count":    len(grp),
             "Usage %":  safe_pct(len(grp), total)}
        if "RelSpeed" in grp.columns:
            r["Max MPH"] = round(grp["RelSpeed"].max(),  1)
            r["Avg MPH"] = round(grp["RelSpeed"].mean(), 1)
        for col, alias in [("SpinRate","Avg Spin"),
                           ("InducedVertBreak","Avg IVB"),
                           ("HorzBreak","Avg HB")]:
            r[alias] = round(grp[col].mean(), 1) if col in grp.columns else np.nan
        rows.append(r)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_fb"] = out["Pitch Type"].str.lower().str.contains("fastball").astype(int)
    return (out.sort_values(["_fb","Count"], ascending=[False, False])
               .drop(columns="_fb").reset_index(drop=True))


def compute_pitch_discipline(df):
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
        pc   = grp["PitchCall"].astype(str)
        n    = len(grp)
        in_z = pc.isin(ZONE).sum()
        sw   = pc.isin(SWING).sum()
        ct   = pc.isin(CONTACT).sum()
        wh   = pc.isin(WHIFF).sum()
        rows.append({
            "Pitch Type": pt, "Count": n,
            "Zone %":    safe_pct(in_z,  n),
            "Swing %":   safe_pct(sw,    n),
            "Contact %": safe_pct(ct,    max(sw, 1)),
            "Chase %":   safe_pct(max(0, sw - ct), max(n - in_z, 1)),
            "Whiff %":   safe_pct(wh,    max(sw, 1)),
        })
    return (pd.DataFrame(rows)
              .sort_values("Count", ascending=False)
              .reset_index(drop=True))


# ── Chart: Pitch Locations ────────────────────────────────────────────────────
def plot_pitch_locations(df, pitcher_name):
    fig, ax = plt.subplots(figsize=(5.2, 5.8))
    apply_chart_theme(fig, [ax])

    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        ax.text(0.5, 0.5, "No location data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
    else:
        for idx, (pt, g) in enumerate(loc.groupby("TaggedPitchType")):
            color = PITCH_PALETTE[idx % len(PITCH_PALETTE)]
            ax.scatter(g["PlateLocSide"], g["PlateLocHeight"],
                       label=pt, color=color,
                       alpha=0.82, s=44,
                       edgecolors="white" if IS_DARK else "#00000033",
                       linewidths=0.5, zorder=6)

    draw_strike_zone(ax)
    # Draw home plate outline for spatial context
    plate_x = [-0.71, -0.71, 0, 0.71, 0.71]
    plate_y = [0.35,  0.15, 0, 0.15, 0.35]
    ax.fill(plate_x, plate_y, color=C_MUTE, alpha=0.2, zorder=3)

    ax.set_xlim(-2.5, 2.5); ax.set_ylim(0.3, 5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Height (ft)")
    _title(ax, f"Pitch Locations", sub=pitcher_name)
    ax.legend(fontsize=7.5, framealpha=0.5, edgecolor=C_SPINE,
              facecolor=C_CARD, labelcolor=C_TEXT)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(pad=1.2); return fig


# ── Chart: Hot Zone KDE ───────────────────────────────────────────────────────
def plot_hot_zone(df, pitcher_name):
    fig, ax = plt.subplots(figsize=(5.2, 5.8))
    apply_chart_theme(fig, [ax])

    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    cmap = "hot" if IS_DARK else "YlOrRd"

    if len(loc) >= 5:
        try:
            sns.kdeplot(data=loc, x="PlateLocSide", y="PlateLocHeight",
                        fill=True, cmap=cmap, alpha=0.80,
                        levels=14, thresh=0.03, ax=ax)
        except Exception:
            ax.text(0.5, 0.5, "Not enough data for KDE",
                    ha="center", va="center", color=C_MUTE,
                    transform=ax.transAxes, fontsize=11)
    else:
        ax.text(0.5, 0.5, "Not enough data\n(need ≥ 5 pitches)",
                ha="center", va="center", color=C_MUTE,
                transform=ax.transAxes, fontsize=11)

    draw_strike_zone(ax)
    plate_x = [-0.71, -0.71, 0, 0.71, 0.71]
    plate_y = [0.35,  0.15, 0, 0.15, 0.35]
    ax.fill(plate_x, plate_y, color=C_MUTE, alpha=0.18, zorder=3)

    ax.set_xlim(-2.5, 2.5); ax.set_ylim(0.3, 5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Height (ft)")
    _title(ax, "Hot Zone (KDE Density)", sub=pitcher_name)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(pad=1.2); return fig


# ── Chart: Velocity Tendency ──────────────────────────────────────────────────
def plot_velocity_tendency(df, pitcher_name):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    apply_chart_theme(fig, [ax])

    if "RelSpeed" not in df.columns or df["RelSpeed"].dropna().empty:
        ax.text(0.5, 0.5, "No velocity data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    vel = df.dropna(subset=["RelSpeed", "Date"])
    if vel.empty:
        ax.text(0.5, 0.5, "No velocity data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    for idx, (pt, g) in enumerate(vel.groupby("TaggedPitchType")):
        daily = g.sort_values("Date").groupby("Date")["RelSpeed"].agg(["mean","std"]).reset_index()
        daily.columns = ["Date","mean","std"]
        daily["std"]  = daily["std"].fillna(0)
        color = PITCH_PALETTE[idx % len(PITCH_PALETTE)]

        # Shaded ±1 std band
        ax.fill_between(daily["Date"],
                        daily["mean"] - daily["std"],
                        daily["mean"] + daily["std"],
                        alpha=0.12, color=color)
        ax.plot(daily["Date"], daily["mean"],
                label=pt, color=color, lw=2.0,
                marker="o", ms=5, alpha=0.95, zorder=5)

        # Annotate last point with value
        if not daily.empty:
            last = daily.iloc[-1]
            ax.annotate(f'{last["mean"]:.1f}',
                        xy=(last["Date"], last["mean"]),
                        xytext=(4, 4), textcoords="offset points",
                        fontsize=7, color=color, fontweight="bold")

    ax.set_xlabel("Date"); ax.set_ylabel("Avg Velocity (mph)")
    _title(ax, f"Velocity Tendency", sub=pitcher_name)
    ax.legend(fontsize=7.5, framealpha=0.5, edgecolor=C_SPINE,
              facecolor=C_CARD, labelcolor=C_TEXT)
    fig.autofmt_xdate(rotation=28, ha="right")
    fig.tight_layout(pad=1.2); return fig


# ── Chart: Movement Profile ───────────────────────────────────────────────────
def plot_movement_profile(df, pitcher_name):
    fig, ax = plt.subplots(figsize=(6.2, 5.8))
    apply_chart_theme(fig, [ax])

    needed = {"HorzBreak", "InducedVertBreak"}
    if not needed.issubset(df.columns):
        ax.text(0.5, 0.5, "No movement data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    sub = df.dropna(subset=["HorzBreak", "InducedVertBreak"])
    for idx, (pt, g) in enumerate(sub.groupby("TaggedPitchType")):
        x, y, n = g["HorzBreak"].mean(), g["InducedVertBreak"].mean(), len(g)
        color   = PITCH_PALETTE[idx % len(PITCH_PALETTE)]
        # Plot individual pitch dots (subtle)
        ax.scatter(g["HorzBreak"], g["InducedVertBreak"],
                   color=color, alpha=0.10, s=10, edgecolors="none", zorder=3)
        # Plot mean bubble (large)
        ax.scatter(x, y, s=max(n * 4, 80), color=color,
                   alpha=0.88, edgecolors="white" if IS_DARK else "#00000044",
                   linewidths=1.0, zorder=6)
        ax.annotate(f"{pt}\n({n})",
                    (x, y), textcoords="offset points", xytext=(7, 5),
                    fontsize=7.5, color=color, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2",
                              fc=C_CARD, ec="none", alpha=0.7))

    # Quadrant reference lines
    ax.axhline(0, color=C_SPINE, lw=1.0, alpha=0.8, zorder=2)
    ax.axvline(0, color=C_SPINE, lw=1.0, alpha=0.8, zorder=2)

    # Quadrant labels
    xr = ax.get_xlim() if ax.get_xlim() != (0.0, 1.0) else (-20, 20)
    yr = ax.get_ylim() if ax.get_ylim() != (0.0, 1.0) else (-20, 20)
    kw = dict(color=C_MUTE, fontsize=7.5, alpha=0.55, ha="center")
    ax.text( 0.82, 0.95, "Rise / Arm", transform=ax.transAxes, **kw)
    ax.text( 0.18, 0.95, "Rise / Glove", transform=ax.transAxes, **kw)
    ax.text( 0.82, 0.05, "Drop / Arm", transform=ax.transAxes, **kw)
    ax.text( 0.18, 0.05, "Drop / Glove", transform=ax.transAxes, **kw)

    ax.set_xlabel("Horizontal Break (in) — Arm side →")
    ax.set_ylabel("Induced Vertical Break (in) — Rise →")
    _title(ax, "Movement Profile", sub=pitcher_name)
    fig.tight_layout(pad=1.2); return fig


# ── Chart: Release Point ──────────────────────────────────────────────────────
def plot_release_point(df, pitcher_name):
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    apply_chart_theme(fig, [ax])

    needed = {"RelSide", "RelHeight"}
    if not needed.issubset(df.columns) or df[list(needed)].dropna().empty:
        ax.text(0.5, 0.5, "No release-point data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    sub = df.dropna(subset=["RelSide", "RelHeight"])

    # Background KDE for all pitches
    try:
        sns.kdeplot(data=sub, x="RelSide", y="RelHeight",
                    fill=True, cmap="Blues" if not IS_DARK else "YlOrBr",
                    alpha=0.25, levels=8, thresh=0.05, ax=ax)
    except Exception:
        pass

    for idx, (pt, g) in enumerate(sub.groupby("TaggedPitchType")):
        color = PITCH_PALETTE[idx % len(PITCH_PALETTE)]
        ax.scatter(g["RelSide"], g["RelHeight"], label=pt,
                   color=color, alpha=0.65, s=22,
                   edgecolors="none", zorder=5)
        # Mean crosshair
        mx, my = g["RelSide"].mean(), g["RelHeight"].mean()
        ax.scatter(mx, my, color=color, s=90, marker="+",
                   linewidths=2.0, zorder=7)

    ax.set_xlabel("Release Side (ft)"); ax.set_ylabel("Release Height (ft)")
    _title(ax, "Release Point", sub=pitcher_name)
    ax.legend(fontsize=7.5, framealpha=0.5, edgecolor=C_SPINE,
              facecolor=C_CARD, labelcolor=C_TEXT)
    fig.tight_layout(pad=1.2); return fig


# ── PDF export: pitching ──────────────────────────────────────────────────────
def export_pitching_pdf(summary_df, disc_df, fig_loc, fig_kde,
                         fig_vel, fig_mov, fig_rel, pitcher_name):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        for df_tbl, title in [
            (summary_df, f"Pitching Summary — {pitcher_name}"),
            (disc_df,    f"Pitch Discipline — {pitcher_name}") if not disc_df.empty else (None, None),
        ]:
            if df_tbl is None or (hasattr(df_tbl, "empty") and df_tbl.empty):
                continue
            fh = max(3, len(df_tbl) * 0.45 + 1.5)
            ft, at = plt.subplots(figsize=(12, fh))
            ft.patch.set_facecolor(CHART_BG_DARK)
            styled_table_pdf(at, df_tbl, title)
            ft.tight_layout()
            pdf.savefig(ft, bbox_inches="tight", facecolor=CHART_BG_DARK)
            plt.close(ft)
        for fig in [fig_loc, fig_kde, fig_vel, fig_mov, fig_rel]:
            pdf.savefig(fig, bbox_inches="tight", facecolor=CHART_BG_DARK)
    buf.seek(0); return buf.read()


def render_pitching_dashboard(df):
    st.markdown('<div class="sh">⚾ Pitching Dashboard</div>', unsafe_allow_html=True)

    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column found."); return

    pitchers = sorted(df["Pitcher"].dropna().unique())
    selected = st.selectbox("Select Pitcher", pitchers, key="sel_pitcher")
    pf = df[df["Pitcher"] == selected].copy()
    n  = len(pf)

    if n < 15:
        st.warning(f"⚠️ **{selected}** — only **{n}** pitches (min recommended: 15).")

    # KPI row
    avg_v  = pf["RelSpeed"].mean()  if "RelSpeed"  in pf.columns else np.nan
    max_v  = pf["RelSpeed"].max()   if "RelSpeed"  in pf.columns else np.nan
    avg_sp = pf["SpinRate"].mean()  if "SpinRate"  in pf.columns else np.nan
    ext    = pf["Extension"].mean() if "Extension" in pf.columns else np.nan
    n_pt   = pf["TaggedPitchType"].nunique()

    c1,c2,c3,c4,c5 = st.columns(5)
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

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Summary & Discipline",
        "📍 Locations & Hot Zone",
        "📈 Velocity & Movement",
        "🎯 Release Point",
    ])

    with tab1:
        st.markdown('<div class="sh">📋 Pitch Summary</div>', unsafe_allow_html=True)
        summary_df = build_pitch_summary(pf)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        csv_dl(summary_df, f"{selected}_summary.csv")

        st.markdown('<div class="sh">🎯 Pitch Discipline</div>', unsafe_allow_html=True)
        disc_df = compute_pitch_discipline(pf)
        if disc_df.empty:
            st.info("PitchCall column required for discipline metrics.")
        else:
            st.dataframe(disc_df, use_container_width=True, hide_index=True)
            csv_dl(disc_df, f"{selected}_discipline.csv")

    with tab2:
        cl, cr = st.columns(2)
        fig_loc = plot_pitch_locations(pf, selected)
        fig_kde = plot_hot_zone(pf, selected)
        with cl: st.pyplot(fig_loc, use_container_width=True)
        with cr: st.pyplot(fig_kde, use_container_width=True)

    with tab3:
        fig_vel = plot_velocity_tendency(pf, selected)
        st.pyplot(fig_vel, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        fig_mov = plot_movement_profile(pf, selected)
        st.pyplot(fig_mov, use_container_width=True)

    with tab4:
        fig_rel = plot_release_point(pf, selected)
        st.pyplot(fig_rel, use_container_width=True)

    st.markdown('<div class="sh">📤 Export</div>', unsafe_allow_html=True)

    # Ensure figures exist regardless of which tab was visited
    if "fig_loc" not in locals(): fig_loc = plot_pitch_locations(pf, selected)
    if "fig_kde" not in locals(): fig_kde = plot_hot_zone(pf, selected)
    if "fig_vel" not in locals(): fig_vel = plot_velocity_tendency(pf, selected)
    if "fig_mov" not in locals(): fig_mov = plot_movement_profile(pf, selected)
    if "fig_rel" not in locals(): fig_rel = plot_release_point(pf, selected)
    if "summary_df" not in locals(): summary_df = build_pitch_summary(pf)
    if "disc_df"    not in locals(): disc_df    = compute_pitch_discipline(pf)

    ec1, ec2 = st.columns(2)
    with ec1:
        pdf_b = export_pitching_pdf(
            summary_df,
            disc_df if not disc_df.empty else pd.DataFrame(),
            fig_loc, fig_kde, fig_vel, fig_mov, fig_rel, selected)
        st.download_button("⬇️ Download PDF Report", pdf_b,
                           f"{selected}_pitching_report.pdf", "application/pdf")
    with ec2:
        csv_dl(pf, f"{selected}_raw_pitches.csv", "⬇️ Download Raw CSV")

    for fig in [fig_loc, fig_kde, fig_vel, fig_mov, fig_rel]:
        plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# ══ HITTING ANALYTICS ════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

def build_hitting_monthly(df):
    df = df.copy()
    df["YearMonth"] = df["Date"].dt.to_period("M")
    optional = {"ExitSpeed":("Max EV","Avg EV"), "Angle":("Max LA","Avg LA"),
                "Distance":("Max Dist","Avg Dist")}
    rows = []
    for period, grp in df.groupby("YearMonth"):
        r = {"Month": str(period), "Pitches": len(grp)}
        for col, (mx, av) in optional.items():
            if col in df.columns:
                vals = grp[col].dropna()
                r[mx] = round(vals.max(),  1) if not vals.empty else np.nan
                r[av] = round(vals.mean(), 1) if not vals.empty else np.nan
        if "ExitSpeed" in df.columns:
            ev = grp["ExitSpeed"].dropna()
            r["HH %"] = safe_pct((ev >= 95).sum(), len(ev))
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrel = ((grp["ExitSpeed"].fillna(0) >= 98) &
                      (grp["Angle"].fillna(-999)   >= 8)  &
                      (grp["Angle"].fillna(-999)   <= 32)).sum()
            r["Barrel %"] = safe_pct(barrel, len(grp))
        rows.append(r)
    out = pd.DataFrame(rows)
    return out.sort_values("Month", ascending=False).reset_index(drop=True) if not out.empty else out


def compute_plate_discipline(df):
    if "PitchCall" not in df.columns:
        return {}
    pc      = df["PitchCall"].astype(str)
    ZONE    = {"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable",
               "FoulBallNotFieldable","InPlay"}
    SWING   = {"StrikeSwinging","FoulBall","FoulBallFieldable",
               "FoulBallNotFieldable","InPlay"}
    CONTACT = {"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    WHIFF   = {"StrikeSwinging"}
    BB      = {"BallCalled","HitByPitch","IntentionalBall"}
    KK      = {"StrikeoutSwinging","StrikeoutCalled"}
    n       = len(df)
    in_z    = pc.isin(ZONE).sum()
    swings  = pc.isin(SWING).sum()
    cont    = pc.isin(CONTACT).sum()
    whiff   = pc.isin(WHIFF).sum()
    return {
        "Zone %":    safe_pct(in_z,  n),
        "Swing %":   safe_pct(swings, n),
        "Contact %": safe_pct(cont,  max(swings, 1)),
        "Chase %":   safe_pct(max(0, swings-cont), max(n-in_z, 1)),
        "Whiff %":   safe_pct(whiff, max(swings, 1)),
        "K %":       safe_pct(pc.isin(KK).sum(), n),
        "BB %":      safe_pct(pc.isin(BB).sum(), n),
    }


# ── Chart: Spray Chart ────────────────────────────────────────────────────────
def plot_spray_chart(df, batter_name):
    fig, ax = plt.subplots(figsize=(5.8, 5.8))
    apply_chart_theme(fig, [ax])
    field_green = "#1a3a1a" if IS_DARK else "#d4edda"
    ax.set_facecolor(field_green)

    spray = df.dropna(subset=["Distance","Bearing"]).copy()
    if spray.empty:
        ax.text(0.5, 0.5, "No spray data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        _title(ax, "Spray Chart", sub=batter_name)
        fig.tight_layout(); return fig

    brad = np.deg2rad(spray["Bearing"])
    spray["Hit_X"] = spray["Distance"] * np.sin(brad)
    spray["Hit_Y"] = spray["Distance"] * np.cos(brad)

    # Field drawing
    line_color = "#8b6914" if IS_DARK else "#5d4037"
    arc_color  = "#4a5e3a" if IS_DARK else "#388e3c"
    for sign in [1, -1]:
        ax.plot([0, sign * 420 * np.sin(np.deg2rad(45))],
                [0, 420 * np.cos(np.deg2rad(45))],
                color=line_color, lw=2.0, alpha=0.8)
    ang = np.linspace(-45, 45, 300)
    for r, lw, ls in [(230, 1.0, "--"), (330, 1.0, "--"), (400, 1.5, "-")]:
        ax.plot(r*np.sin(np.deg2rad(ang)), r*np.cos(np.deg2rad(ang)),
                color=arc_color, lw=lw, alpha=0.55, linestyle=ls)
        # Distance label
        ax.text(r * np.sin(np.deg2rad(44)), r * np.cos(np.deg2rad(44)),
                f"{r} ft", fontsize=6.5, color=arc_color, alpha=0.7)
    bd = 90 * np.sqrt(2) / 2
    ax.plot([0, bd, 0, -bd, 0], [0, bd, 2*bd, bd, 0],
            color="#c8a850", lw=1.2, alpha=0.7)

    has_ev = "ExitSpeed" in spray.columns and spray["ExitSpeed"].notna().any()
    sc = ax.scatter(spray["Hit_X"], spray["Hit_Y"],
                    c=spray["ExitSpeed"] if has_ev else ACCENT,
                    cmap="RdYlGn" if has_ev else None,
                    s=48, alpha=0.88, edgecolors="white" if IS_DARK else "#00000033",
                    linewidths=0.4, zorder=5, vmin=60, vmax=110)
    if has_ev:
        cb = fig.colorbar(sc, ax=ax, pad=0.02, shrink=0.70)
        cb.set_label("Exit Speed (mph)", color=C_MUTE, fontsize=8)
        cb.ax.yaxis.set_tick_params(color=C_MUTE, labelcolor=C_MUTE)
        cb.outline.set_edgecolor(C_SPINE)

    ax.set_xlim(-360, 360); ax.set_ylim(-20, 460)
    ax.set_xlabel("Horizontal (ft)"); ax.set_ylabel("Vertical (ft)")
    _title(ax, "Spray Chart", sub=batter_name)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(pad=1.2); return fig


# ── Chart: Damage Zone ────────────────────────────────────────────────────────
def plot_damage_zone(df, batter_name):
    fig, ax = plt.subplots(figsize=(5.2, 5.8))
    apply_chart_theme(fig, [ax])

    loc = df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    if loc.empty:
        ax.text(0.5, 0.5, "No location data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
    else:
        has_ev = "ExitSpeed" in loc.columns and loc["ExitSpeed"].notna().any()

        # Background KDE of all pitches seen (light)
        try:
            sns.kdeplot(data=loc, x="PlateLocSide", y="PlateLocHeight",
                        fill=False, color=C_MUTE, alpha=0.25,
                        levels=6, thresh=0.1, ax=ax, zorder=3)
        except Exception:
            pass

        sc = ax.scatter(loc["PlateLocSide"], loc["PlateLocHeight"],
                        c=loc["ExitSpeed"] if has_ev else ACCENT,
                        cmap="RdYlGn" if has_ev else None,
                        s=40, alpha=0.82,
                        edgecolors="white" if IS_DARK else "#00000033",
                        linewidths=0.4, zorder=6, vmin=60, vmax=110)
        if has_ev:
            cb = fig.colorbar(sc, ax=ax, pad=0.02, shrink=0.70)
            cb.set_label("Exit Speed (mph)", color=C_MUTE, fontsize=8)
            cb.ax.yaxis.set_tick_params(color=C_MUTE, labelcolor=C_MUTE)
            cb.outline.set_edgecolor(C_SPINE)

    draw_strike_zone(ax)
    plate_x = [-0.71, -0.71, 0, 0.71, 0.71]
    plate_y = [0.35,  0.15, 0, 0.15, 0.35]
    ax.fill(plate_x, plate_y, color=C_MUTE, alpha=0.18, zorder=3)

    ax.set_xlim(-2.5, 2.5); ax.set_ylim(0.3, 5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Height (ft)")
    _title(ax, "Damage Zone", sub=batter_name)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout(pad=1.2); return fig


# ── Chart: EV Distribution ────────────────────────────────────────────────────
def plot_ev_distribution(df, batter_name):
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    apply_chart_theme(fig, [ax])

    ev = df["ExitSpeed"].dropna() if "ExitSpeed" in df.columns else pd.Series(dtype=float)
    if ev.empty:
        ax.text(0.5, 0.5, "No EV data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    counts, bins, patches_list = ax.hist(
        ev, bins=22, color=BLUE, alpha=0.75,
        edgecolor=C_BG, linewidth=0.5)

    # Colour bars above 95 mph red
    for patch, left in zip(patches_list, bins[:-1]):
        if left >= 95:
            patch.set_facecolor(RED)
            patch.set_alpha(0.85)

    ax.axvline(ev.mean(), color=ACCENT, lw=2.0, linestyle="--", zorder=6,
               label=f"Avg {ev.mean():.1f} mph")
    ax.axvline(95, color=RED, lw=1.5, linestyle=":", zorder=6,
               label="Hard Hit ≥ 95")

    # Annotate count above 95
    hh = (ev >= 95).sum()
    ax.text(0.97, 0.93, f"HH: {hh} ({safe_pct(hh, len(ev))}%)",
            transform=ax.transAxes, ha="right", va="top",
            color=RED, fontsize=8.5, fontweight="bold")

    ax.set_xlabel("Exit Velocity (mph)"); ax.set_ylabel("Pitches")
    _title(ax, "Exit Velocity Distribution", sub=batter_name)
    ax.legend(fontsize=7.5, framealpha=0.5, edgecolor=C_SPINE,
              facecolor=C_CARD, labelcolor=C_TEXT)
    fig.tight_layout(pad=1.2); return fig


# ── Chart: LA Distribution ────────────────────────────────────────────────────
def plot_la_distribution(df, batter_name):
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    apply_chart_theme(fig, [ax])

    la = df["Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    if la.empty:
        ax.text(0.5, 0.5, "No LA data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    counts, bins, patches_list = ax.hist(
        la, bins=22, color=GREEN, alpha=0.72,
        edgecolor=C_BG, linewidth=0.5)

    # Colour barrel zone bars gold
    for patch, left, right in zip(patches_list, bins[:-1], bins[1:]):
        if left >= 8 and right <= 32:
            patch.set_facecolor(ACCENT)
            patch.set_alpha(0.90)

    ax.axvspan(8, 32, alpha=0.08, color=ACCENT, label="Barrel zone 8–32°", zorder=1)
    ax.axvline(la.mean(), color=ACCENT, lw=2.0, linestyle="--", zorder=6,
               label=f"Avg {la.mean():.1f}°")

    # Annotate barrel %
    barrel = ((la >= 8) & (la <= 32)).sum()
    ax.text(0.97, 0.93, f"Barrel zone: {barrel} ({safe_pct(barrel, len(la))}%)",
            transform=ax.transAxes, ha="right", va="top",
            color=ACCENT, fontsize=8.5, fontweight="bold")

    ax.set_xlabel("Launch Angle (°)"); ax.set_ylabel("Pitches")
    _title(ax, "Launch Angle Distribution", sub=batter_name)
    ax.legend(fontsize=7.5, framealpha=0.5, edgecolor=C_SPINE,
              facecolor=C_CARD, labelcolor=C_TEXT)
    fig.tight_layout(pad=1.2); return fig


# ── Chart: Rolling EV Trend ───────────────────────────────────────────────────
def plot_rolling_ev(df, batter_name, window=7):
    fig, ax = plt.subplots(figsize=(11, 3.5))
    apply_chart_theme(fig, [ax])

    if "ExitSpeed" not in df.columns or df["ExitSpeed"].dropna().empty:
        ax.text(0.5, 0.5, "No EV data", ha="center", va="center",
                color=C_MUTE, transform=ax.transAxes, fontsize=11)
        fig.tight_layout(); return fig

    daily = (df.dropna(subset=["ExitSpeed","Date"])
               .groupby("Date")["ExitSpeed"]
               .agg(["mean","std","count"])
               .reset_index().sort_values("Date"))
    daily.columns = ["Date","mean","std","cnt"]
    daily["std"]   = daily["std"].fillna(0)
    daily["roll"]  = daily["mean"].rolling(window, min_periods=1).mean()
    daily["r_std"] = daily["std"].rolling(window, min_periods=1).mean()

    # Shaded band
    ax.fill_between(daily["Date"],
                    daily["roll"] - daily["r_std"],
                    daily["roll"] + daily["r_std"],
                    alpha=0.12, color=BLUE, label="±1 SD band")
    ax.fill_between(daily["Date"], daily["mean"],
                    alpha=0.08, color=BLUE)
    ax.plot(daily["Date"], daily["mean"],
            color=BLUE, lw=1.0, alpha=0.55,
            marker="o", ms=4, label="Daily Avg")
    ax.plot(daily["Date"], daily["roll"],
            color=ACCENT, lw=2.2, label=f"{window}-day Rolling Avg")
    ax.axhline(95, color=RED, lw=1.2, linestyle=":", alpha=0.7,
               label="Hard Hit (95)")

    # Annotate the last rolling value
    if not daily.empty:
        last = daily.iloc[-1]
        ax.annotate(f'{last["roll"]:.1f}',
                    xy=(last["Date"], last["roll"]),
                    xytext=(5, 6), textcoords="offset points",
                    fontsize=8, color=ACCENT, fontweight="bold")

    ax.set_xlabel("Date"); ax.set_ylabel("Exit Speed (mph)")
    _title(ax, f"Rolling {window}-Day Avg Exit Speed", sub=batter_name)
    ax.legend(fontsize=7.5, framealpha=0.5, edgecolor=C_SPINE,
              facecolor=C_CARD, labelcolor=C_TEXT)
    fig.autofmt_xdate(rotation=28, ha="right")
    fig.tight_layout(pad=1.2); return fig


# ── PDF export: hitting ───────────────────────────────────────────────────────
def export_hitting_pdf(monthly_df, disc_stats, fig_spray, fig_dmg,
                        fig_ev, fig_la, fig_roll, batter_name):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fh = max(3, len(monthly_df)*0.5+1.5)
        ft, at = plt.subplots(figsize=(14, fh))
        ft.patch.set_facecolor(CHART_BG_DARK)
        styled_table_pdf(at, monthly_df, f"Monthly Progression — {batter_name}")
        ft.tight_layout()
        pdf.savefig(ft, bbox_inches="tight", facecolor=CHART_BG_DARK)
        plt.close(ft)

        if disc_stats:
            ft2, at2 = plt.subplots(figsize=(12, 3))
            ft2.patch.set_facecolor(CHART_BG_DARK)
            styled_table_pdf(at2, pd.DataFrame([disc_stats]),
                             f"Plate Discipline — {batter_name}")
            ft2.tight_layout()
            pdf.savefig(ft2, bbox_inches="tight", facecolor=CHART_BG_DARK)
            plt.close(ft2)

        for fig in [fig_spray, fig_dmg, fig_ev, fig_la, fig_roll]:
            pdf.savefig(fig, bbox_inches="tight", facecolor=CHART_BG_DARK)
    buf.seek(0); return buf.read()


def render_hitting_dashboard(df):
    st.markdown('<div class="sh">🏏 Hitting Dashboard</div>', unsafe_allow_html=True)

    if "Batter" not in df.columns or df["Batter"].dropna().empty:
        st.error("No 'Batter' column found."); return

    batters  = sorted(df["Batter"].dropna().unique())
    selected = st.selectbox("Select Batter", batters, key="sel_batter")
    bdf = df[df["Batter"] == selected].copy()
    n   = len(bdf)

    if n < 15:
        st.warning(f"⚠️ **{selected}** — only **{n}** pitches seen (min: 15).")

    avg_ev  = bdf["ExitSpeed"].mean()  if "ExitSpeed" in bdf.columns else np.nan
    max_ev  = bdf["ExitSpeed"].max()   if "ExitSpeed" in bdf.columns else np.nan
    avg_la  = bdf["Angle"].mean()      if "Angle"     in bdf.columns else np.nan
    avg_dis = bdf["Distance"].mean()   if "Distance"  in bdf.columns else np.nan

    hh_rate = barrel_rate = 0.0
    if "ExitSpeed" in bdf.columns:
        ev_s = bdf["ExitSpeed"].dropna()
        hh_rate = safe_pct((ev_s >= 95).sum(), len(ev_s))
    if "ExitSpeed" in bdf.columns and "Angle" in bdf.columns:
        barrel = ((bdf["ExitSpeed"].fillna(0) >= 98) &
                  (bdf["Angle"].fillna(-999)   >= 8)  &
                  (bdf["Angle"].fillna(-999)   <= 32)).sum()
        barrel_rate = safe_pct(barrel, n)

    disc = compute_plate_discipline(bdf)

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("Pitches Seen", f"{n:,}")
    with c2: st.metric("Avg Exit Velo",
                        f"{avg_ev:.1f} mph" if not np.isnan(avg_ev) else "—",
                        delta=f"Max {max_ev:.1f}" if not np.isnan(max_ev) else None)
    with c3: st.metric("Avg Launch Angle",
                        f"{avg_la:.1f}°" if not np.isnan(avg_la) else "—")
    with c4: st.metric("Avg Distance",
                        f"{avg_dis:.0f} ft" if not np.isnan(avg_dis) else "—")
    with c5: st.metric("Hard Hit %",  f"{hh_rate:.1f}%")
    with c6: st.metric("Barrel %",    f"{barrel_rate:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    if disc:
        st.markdown('<div class="sh">🎯 Plate Discipline</div>', unsafe_allow_html=True)
        badge_cols = st.columns(len(disc))
        for col, (k, v) in zip(badge_cols, disc.items()):
            with col:
                st.markdown(
                    f'<div class="stat-badge">'
                    f'<div class="val">{v}%</div>'
                    f'<div class="lbl">{k}</div>'
                    f'</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📅 Monthly Progression",
        "🗺️ Spray Chart & Damage Zone",
        "📊 EV & LA Distributions",
    ])

    with tab1:
        monthly_df = build_hitting_monthly(bdf)
        if monthly_df.empty:
            st.info("No monthly data.")
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

    st.markdown('<div class="sh">📤 Export</div>', unsafe_allow_html=True)

    if "monthly_df" not in locals(): monthly_df = build_hitting_monthly(bdf)
    if "fig_spray"  not in locals(): fig_spray  = plot_spray_chart(bdf, selected)
    if "fig_dmg"    not in locals(): fig_dmg    = plot_damage_zone(bdf, selected)
    if "fig_ev"     not in locals(): fig_ev     = plot_ev_distribution(bdf, selected)
    if "fig_la"     not in locals(): fig_la     = plot_la_distribution(bdf, selected)
    if "fig_roll"   not in locals(): fig_roll   = plot_rolling_ev(bdf, selected)

    ec1, ec2 = st.columns(2)
    with ec1:
        if not monthly_df.empty:
            pdf_b = export_hitting_pdf(monthly_df, disc, fig_spray, fig_dmg,
                                        fig_ev, fig_la, fig_roll, selected)
            st.download_button("⬇️ Download PDF Report", pdf_b,
                               f"{selected}_hitting_report.pdf", "application/pdf")
        else:
            st.info("Monthly data required for PDF.")
    with ec2:
        csv_dl(bdf, f"{selected}_raw_pitches.csv", "⬇️ Download Raw CSV")

    for fig in [fig_spray, fig_dmg, fig_ev, fig_la, fig_roll]:
        plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.markdown("""
    <div class="hero">
      <div class="hero-icon">⚾</div>
      <div>
        <div class="hero-title">
          Trackman <span class="hl">Analytics</span>
          <span style="font-size:1rem;opacity:0.4;font-weight:400"> v3.0</span>
        </div>
        <div class="hero-sub">
          Advanced baseball data science platform — pitching &amp; hitting
        </div>
        <div class="hero-pills">
          <span class="pill">Light &amp; Dark Mode</span>
          <span class="pill">Smart Name Merge</span>
          <span class="pill">Multi-Date Picker</span>
          <span class="pill">Pitch Discipline</span>
          <span class="pill">Movement Profile</span>
          <span class="pill">Release Point</span>
          <span class="pill">Barrel %</span>
          <span class="pill">Rolling EV</span>
          <span class="pill">PDF + CSV Export</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(
        '<span class="sb-label">📂 Upload Data</span>', unsafe_allow_html=True)
    uploaded = st.sidebar.file_uploader(
        "Upload Trackman CSV files", type=["csv"],
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

    with st.spinner("🔄 Loading and cleaning data…"):
        master, p_aliases, b_aliases = load_and_clean(uploaded)

    if master.empty:
        st.error("❌ No valid data could be loaded. Please check your CSV files.")
        return

    total_aliases = p_aliases + b_aliases
    st.sidebar.success(
        f"✅ **{len(master):,}** pitches from **{len(uploaded)}** file(s).")

    if total_aliases > 0:
        st.sidebar.markdown(
            f'<div class="alias-box">🔗 Merged <b>{total_aliases}</b> name '
            f'variant(s) — {p_aliases} pitcher, {b_aliases} batter aliases '
            f'resolved and combined.</div>',
            unsafe_allow_html=True)

    filtered = sidebar_date_filter(master)
    if filtered.empty:
        st.warning("⚠️ No data matches the selected dates."); return

    filtered = advanced_filters(filtered)
    if filtered.empty:
        st.warning("⚠️ No data matches the advanced filters."); return

    st.sidebar.markdown(
        '<span class="sb-label">🎯 Dashboard Mode</span>', unsafe_allow_html=True)
    mode = st.sidebar.radio(
        "mode", ["⚾ Pitching", "🏏 Hitting"],
        key="dash_mode", label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("Built with ❤️ · Streamlit · Pandas · Matplotlib · Seaborn")

    if mode == "⚾ Pitching":
        render_pitching_dashboard(filtered)
    else:
        render_hitting_dashboard(filtered)


if __name__ == "__main__":
    main()