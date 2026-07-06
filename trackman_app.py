"""
=============================================================================
  TRACKMAN BASEBALL ANALYTICS DASHBOARD  v4.2 — SAVANT EDITION
  Expert-grade Streamlit app with Baseball Savant–inspired visuals
  ─────────────────────────────────────────────────────────────────────────
  KEY FEATURES:
    ✓ Player search bar (live filtering for 100+ rosters)
    ✓ vs RHP / vs LHP splits with dual spray charts & damage zones
    ✓ Play result breakdown (1B, 2B, 3B, HR, K, BB, etc.)
    ✓ K% / BB% per plate appearance (v4.2 fix)
    ✓ Zone% / Chase% from true pitch location (v4.2 fix)
    ✓ Savant-style dynamic barrel definition per batted ball (v4.2 fix)
    ✓ Pitch usage by count, rolling EV trend, per-pitch heatmaps, wOBA (v4.2)
    ✓ League averages & stadium intelligence
    ✓ Park factor heatmaps (hitter vs pitcher friendly)
    ✓ EV × LA quality scatter with barrel zone highlight
    ✓ Savant-style chart design: clean grids, minimal decoration, pro aesthetics
    ✓ PDF reports with 2-charts-per-page layout
  ─────────────────────────────────────────────────────────────────────────
  SAVANT DESIGN PRINCIPLES:
    • Clean white backgrounds, minimal grid lines
    • Tufte-style (hide top/right spines for clarity)
    • Professional fonts, no drop shadows or gradients
    • Colour-coded by outcome (HR=red, 2B=green, single=blue, out=grey)
    • Strike zone drawn as minimal rectangle, not bold
    • Custom palettes: Savant blue (#1f77b4), pitcher red, hitter green
  ─────────────────────────────────────────────────────────────────────────
  Built with: Streamlit, Pandas, Matplotlib, Seaborn, NumPy
=============================================================================
"""

import io, re, unicodedata, warnings
from collections import defaultdict, Counter

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

# ══════════════════════════════════════════════════════════════════════════════
# SAVANT DESIGN SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
SAVANT_BLUE    = "#1f77b4"
SAVANT_RED     = "#d62728"
SAVANT_GREEN   = "#2ca02c"
SAVANT_ORANGE  = "#ff7f0e"
SAVANT_PURPLE  = "#9467bd"
SAVANT_BROWN   = "#8c564b"
SAVANT_PINK    = "#e377c2"
SAVANT_GREY    = "#7f7f7f"
SAVANT_BG      = "#ffffff"
SAVANT_GRID    = "#f0f0f0"
SAVANT_TEXT    = "#333333"
SAVANT_ACCENT  = "#1f77b4"

PITCH_PALETTE = [SAVANT_BLUE, SAVANT_RED, SAVANT_GREEN, SAVANT_ORANGE,
                 SAVANT_PURPLE, SAVANT_BROWN, SAVANT_PINK, SAVANT_GREY,
                 "#2ca02c", "#ff9896", "#98df8a", "#c5b0d5"]

# Result → Savant colour mapping
RESULT_COLORS = {
    "HR": SAVANT_RED,      # Home run = red
    "3B": SAVANT_PURPLE,   # Triple = purple
    "2B": SAVANT_GREEN,    # Double = green
    "1B": SAVANT_BLUE,     # Single = blue
    "K": SAVANT_GREY,      # Strikeout = grey
    "BB": SAVANT_ORANGE,   # Walk = orange
    "Out": "#cccccc",      # Out = light grey
    "HBP": SAVANT_PINK,    # HBP = pink
    "FC": SAVANT_BROWN,    # Fielder's choice = brown
}

COL_ALIASES={
    "TaggedPitchType":["AutoPitchType","PitchType"],
    "PitchCall":      ["Call","PitchResult"],
    "Batter":         ["BatterName","HitterName"],
    "Pitcher":        ["PitcherName","ThrowerName"],
    "BatterSide":     ["BatterHand","BatterHandedness","Side"],
    "PitcherThrows":  ["PitcherHand","Throws"],
    "Stadium":        ["BallPark","Ballpark","Venue","Park","Field","Location"],
    "PlayResult":     ["KorBB","TaggedHitType","HitType","Result","PlayOutcome"],
}
WARMUP={"warmup","undefined"}
PITCH_MAP={
    "four-seam fastball":"4-Seam","fourseam":"4-Seam","4-seam":"4-Seam","4seam":"4-Seam",
    "ff":"4-Seam","fa":"4-Seam","two-seam fastball":"2-Seam","twoseam":"2-Seam",
    "2-seam":"2-Seam","2seam":"2-Seam","sinker":"Sinker","si":"Sinker",
    "curveball":"Curve","curve":"Curve","cb":"Curve","cu":"Curve",
    "slider":"Slider","sl":"Slider","sweeper":"Sweeper","sw":"Sweeper",
    "changeup":"Change","change":"Change","ch":"Change","cutter":"Cutter",
    "cut fastball":"Cutter","fc":"Cutter","splitter":"Split","split":"Split",
    "fs":"Split","knuckleball":"Knuckleball","kn":"Knuckleball","screwball":"Screwball",
    "fastball":"Fastball",
}
RESULT_MAP={
    "single":"1B","1b":"1B","hit":"1B","double":"2B","2b":"2B","triple":"3B","3b":"3B",
    "homerun":"HR","home_run":"HR","hr":"HR","out":"Out","fieldersChoice":"FC",
    "fielderschoice":"FC","fc":"FC","error":"Error","sacrificefly":"SacFly",
    "sacfly":"SacFly","sacrificebunt":"SacBunt","sacbunt":"SacBunt",
    "strikeout":"K","strikeoutswinging":"K","strikeoutlooking":"K","k":"K","kk":"K",
    "walk":"BB","intentionalwalk":"BB","bb":"BB","hitbypitch":"HBP","hbp":"HBP",
    "undefined":"—","nan":"—","":"—",
}
NUMERIC_COLS=["RelSpeed","SpinRate","InducedVertBreak","HorzBreak",
              "PlateLocSide","PlateLocHeight","ExitSpeed","Angle","Distance",
              "Bearing","RelHeight","RelSide","Extension","SpinAxis",
              "VertApprAngle","HorzApprAngle","Balls","Strikes","Inning"]

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Trackman Analytics v4.2 (Savant)", page_icon="⚾",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
section[data-testid="stSidebar"]{border-right:1px solid #e0e0e0}
.sb-label{font-size:.65rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;
  color:#1f77b4;padding:12px 0 4px 0;display:block}
.hero{background:linear-gradient(135deg,rgba(31,119,180,.08) 0%,transparent 60%);
  border:1px solid #d0d0d0;border-left:4px solid #1f77b4;border-radius:8px;
  padding:20px 24px;margin-bottom:16px;display:flex;align-items:center;gap:16px}
.hero-icon{font-size:2.8rem;line-height:1}
.hero-title{font-size:1.9rem;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.hero-title .hl{color:#1f77b4}
.hero-sub{font-size:.85rem;margin-top:3px;opacity:.65;line-height:1.4}
.hero-pills{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.pill{background:rgba(31,119,180,.08);border:1px solid rgba(31,119,180,.25);color:#1f77b4;
  border-radius:16px;padding:2px 10px;font-size:.68rem;font-weight:600;letter-spacing:.02em}
.sh{font-size:.7rem;font-weight:700;color:#1f77b4;text-transform:uppercase;
  letter-spacing:.12em;border-bottom:1px solid #e8e8e8;padding-bottom:6px;margin:18px 0 10px 0}
div[data-testid="metric-container"]{border:1px solid #e0e0e0!important;
  border-top:3px solid #1f77b4!important;border-radius:6px!important;
  padding:12px 10px!important;background:#fafafa!important}
div[data-testid="metric-container"] label{font-size:.7rem!important;opacity:.6!important}
div[data-testid="metric-container"] div[data-testid="stMetricValue"]{color:#1f77b4!important;font-size:1.6rem!important;font-weight:700!important}
.stTabs [data-baseweb="tab-list"]{gap:2px;border-radius:0;padding:0;border:1px solid #e0e0e0}
.stTabs [data-baseweb="tab"]{border-radius:0;font-weight:600;font-size:.8rem;opacity:.55}
.stTabs [aria-selected="true"]{background:#1f77b4!important;color:#fff!important;opacity:1!important}
.stDownloadButton>button{background:rgba(31,119,180,.1)!important;border:1px solid #1f77b4!important;
  color:#1f77b4!important;font-weight:600!important;border-radius:4px!important}
.stDownloadButton>button:hover{background:#1f77b4!important;color:#fff!important}
div[data-testid="stDataFrame"]{border:1px solid #e0e0e0;border-radius:4px;overflow:hidden}
.stat-badge{border:1px solid #e0e0e0;border-radius:4px;padding:8px 10px;
  text-align:center;min-width:75px;background:#fafafa}
.stat-badge .val{font-size:1.4rem;font-weight:700;color:#1f77b4;line-height:1}
.stat-badge .lbl{font-size:.6rem;letter-spacing:.05em;text-transform:uppercase;opacity:.5;margin-top:2px}
</style>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SAVANT CHART STYLING
# ══════════════════════════════════════════════════════════════════════════════
# Savant rcParams — applied once at module level for all charts
plt.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          9,
    "axes.titlesize":     12,
    "axes.titleweight":   "bold",
    "axes.titlepad":      10,
    "axes.labelsize":     9,
    "axes.labelcolor":    "#333333",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.linewidth":     0.7,
    "xtick.labelsize":    8.5,
    "ytick.labelsize":    8.5,
    "xtick.major.width":  0.7,
    "ytick.major.width":  0.7,
    "xtick.major.size":   3.5,
    "ytick.major.size":   3.5,
    "legend.fontsize":    8,
    "legend.framealpha":  0.0,
    "legend.edgecolor":   "none",
    "figure.dpi":         150,
    "savefig.dpi":        150,
    "figure.facecolor":   "#ffffff",
    "axes.facecolor":     "#ffffff",
    "axes.grid":          True,
    "grid.color":         "#f0f0f0",
    "grid.linewidth":     0.7,
    "lines.linewidth":    1.6,
})

def setup_savant_fig(figsize=(10, 6)):
    """Create a figure with Savant-style defaults (dpi=150, constrained layout)."""
    fig, ax = plt.subplots(figsize=figsize, layout="constrained")
    fig.patch.set_facecolor(SAVANT_BG)
    ax.set_facecolor(SAVANT_BG)
    return fig, ax

def style_savant_ax(ax, hide_spines=True):
    """Apply Savant typography & grid to axes."""
    ax.grid(True, color=SAVANT_GRID, linewidth=0.65, alpha=1.0, linestyle='-', zorder=0)
    ax.set_axisbelow(True)
    if hide_spines:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color("#cccccc")
        ax.spines['bottom'].set_color("#cccccc")
        ax.spines['left'].set_linewidth(0.65)
        ax.spines['bottom'].set_linewidth(0.65)
    ax.tick_params(which="both", colors=SAVANT_TEXT, labelsize=8.5,
                   length=3, width=0.65, direction="out")
    ax.tick_params(which="minor", length=0)
    ax.xaxis.label.set_color(SAVANT_TEXT)
    ax.yaxis.label.set_color(SAVANT_TEXT)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontsize(8.5); label.set_color(SAVANT_TEXT)

def savant_title(ax, title, subtitle=''):
    """Add Savant-style title — bold, clean, left-aligned like Savant cards."""
    ax.text(0.0, 1.06, title, transform=ax.transAxes, ha='left', va='bottom',
            fontsize=11, fontweight='bold', color=SAVANT_TEXT)
    if subtitle:
        ax.text(0.0, 1.01, subtitle, transform=ax.transAxes, ha='left', va='bottom',
                fontsize=8.5, color=SAVANT_GREY, style='italic')

def draw_savant_zone(ax, alpha=0.4):
    """Draw strike zone as minimal grey rectangle."""
    zone = patches.Rectangle((-0.71, 1.5), 1.42, 2.0,
        lw=1.2, edgecolor=SAVANT_GREY, facecolor='none', alpha=alpha, zorder=3)
    ax.add_patch(zone)
    for i in range(1, 3):
        ax.axvline(-0.71+i*0.71, color=SAVANT_GREY, lw=0.4, alpha=alpha*0.4, zorder=2)
    for j in range(1, 3):
        ax.axhline(1.5+j*2.0/3, color=SAVANT_GREY, lw=0.4, alpha=alpha*0.4, zorder=2)

def draw_plate(ax):
    """Draw home plate."""
    ax.fill([-0.71,-0.71,0,0.71,0.71],[0.35,0.15,0,0.15,0.35],
            color=SAVANT_GREY, alpha=0.15, zorder=2)

def safe_pct(num, denom): return round(100*num/denom,1) if denom>0 else 0.0
def csv_dl(df, fname, label="⬇️ Download CSV"):
    st.download_button(label, df.to_csv(index=False).encode(), fname, "text/csv")
def fmt(v, suffix="", decimals=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    return f"{v:.{decimals}f}{suffix}"

# ══════════════════════════════════════════════════════════════════════════════
# CORE SABERMETRIC HELPERS (v4.2 — correct denominators & true zone)
# ══════════════════════════════════════════════════════════════════════════════
TERMINAL_RESULTS={"1B","2B","3B","HR","Out","K","BB","HBP","FC","Error","SacFly","SacBunt"}
SWING_CALLS={"StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
CONTACT_CALLS={"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
# Rulebook zone (±0.71 ft) + one ball radius of margin, typical 1.5–3.5 ft height
ZONE_HALF_WIDTH=0.83
ZONE_BOTTOM, ZONE_TOP=1.5, 3.5
# wOBA linear weights (FanGraphs ~2023, stable enough for scouting use)
WOBA_W={"BB":0.69,"HBP":0.72,"1B":0.89,"2B":1.27,"3B":1.62,"HR":2.10}

def count_pa(df):
    """Plate appearances = pitches whose PlayResult is a terminal outcome."""
    if "PlayResult" in df.columns:
        pa=int(df["PlayResult"].astype(str).isin(TERMINAL_RESULTS).sum())
        if pa>0: return pa
    if "PitchCall" in df.columns:                      # rough fallback
        return int(df["PitchCall"].astype(str).isin({"InPlay","HitByPitch"}).sum())
    return 0

def in_zone_mask(df):
    """(mask, has_location) — true strike-zone membership from PlateLoc columns."""
    if {"PlateLocSide","PlateLocHeight"}.issubset(df.columns) and df["PlateLocSide"].notna().any():
        m=((df["PlateLocSide"].abs()<=ZONE_HALF_WIDTH)
           &(df["PlateLocHeight"].between(ZONE_BOTTOM,ZONE_TOP)))
        return m.fillna(False), True
    return pd.Series(False,index=df.index), False

def batted_ball_mask(df):
    """Balls put in play — denominator for HH% / Barrel%."""
    if "PitchCall" in df.columns:
        m=df["PitchCall"].astype(str).eq("InPlay")
        if m.any(): return m
    if "ExitSpeed" in df.columns: return df["ExitSpeed"].notna()
    return pd.Series(False,index=df.index)

def barrel_mask(df, barrel_ev_base=98):
    """
    Savant-style barrel: EV ≥ 98 opens an LA window of 26–30° that widens
    ~1°/mph downward and ~1.1°/mph upward until 8–50° at 116+ mph.
    barrel_ev_base rescales for College/HS levels (e.g. 92 → treated as 98).
    """
    if not {"ExitSpeed","Angle"}.issubset(df.columns):
        return pd.Series(False,index=df.index)
    ev=df["ExitSpeed"]+(98-barrel_ev_base)
    la=df["Angle"]
    lo=(26-(ev-98)).clip(lower=8)
    hi=(30+(ev-98)*(20/18)).clip(upper=50)
    return ((ev>=98)&(la>=lo)&(la<=hi)).fillna(False)

def count_k_bb(df):
    """(K, BB) counted once per PA from PlayResult, PitchCall fallback for K."""
    kk=bb=0
    if "PlayResult" in df.columns:
        pr=df["PlayResult"].astype(str)
        kk=int(pr.eq("K").sum()); bb=int(pr.eq("BB").sum())
    if kk==0 and "PitchCall" in df.columns:
        kk=int(df["PitchCall"].astype(str).isin({"StrikeoutSwinging","StrikeoutCalled"}).sum())
    return kk,bb

def compute_woba(df):
    """wOBA from tagged PlayResults. Returns np.nan without PA data."""
    pa=count_pa(df)
    if pa==0 or "PlayResult" not in df.columns: return np.nan
    pr=df["PlayResult"].astype(str)
    num=sum(w*int(pr.eq(res).sum()) for res,w in WOBA_W.items())
    # exclude sac bunts from denominator (standard wOBA convention)
    denom=pa-int(pr.eq("SacBunt").sum())
    return round(num/denom,3) if denom>0 else np.nan

# ══════════════════════════════════════════════════════════════════════════════
# NAME NORMALISATION (unchanged from v4)
# ══════════════════════════════════════════════════════════════════════════════
def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD",s)
                   if unicodedata.category(c)!="Mn")

def normalize_name(raw):
    if not isinstance(raw,str) or not raw.strip(): return raw
    s = _strip_accents(raw.strip())
    s = re.sub(r"\b([A-Za-z])\.",r"\1",s)
    if "," in s:
        ci=s.index(",")
        last=re.sub(r"[\-_/\\|]+"," ",s[:ci].strip())
        first=re.sub(r"[\-_/\\|]+"," ",s[ci+1:].strip())
        s=f"{first} {last}" if first else last
    else:
        s=re.sub(r"[\-_/\\|]+"," ",s)
    return re.sub(r"\s+"," ",s).strip().title()

def _tokens(n): return frozenset(t for t in n.lower().split() if len(t)>=2)

def find_clusters(names):
    counts=Counter(names); unique=list(counts.keys()); n=len(unique)
    parent=list(range(n))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    tsets=[_tokens(u) for u in unique]
    for i in range(n):
        for j in range(i+1,n):
            ti,tj=tsets[i],tsets[j]
            if ti and tj and len(ti&tj)/len(ti|tj)>=0.60: union(i,j)
    clusters=defaultdict(list)
    for idx,name in enumerate(unique): clusters[find(idx)].append(name)
    mapping={}
    for members in clusters.values():
        canonical=max(members,key=lambda nm:counts[nm])
        for m in members: mapping[m]=canonical
    return mapping

def dedup_col(df,col):
    if col not in df.columns: return df,0
    df[col]=df[col].astype(str).apply(normalize_name)
    valid=df[col].dropna(); valid=valid[valid!="nan"]
    if valid.empty: return df,0
    mapping=find_clusters(valid.tolist())
    aliases=sum(1 for k,v in mapping.items() if k!=v)
    df[col]=df[col].map(mapping).fillna(df[col])
    return df,aliases

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════
def map_cols(df):
    for std,alts in COL_ALIASES.items():
        if std not in df.columns:
            for alt in alts:
                m=[c for c in df.columns if c.lower()==alt.lower()]
                if m: df.rename(columns={m[0]:std},inplace=True); break
    return df

def norm_pt(v):
    if not isinstance(v,str): return "Unknown"
    c=v.strip()
    return PITCH_MAP.get(c.lower(),c) if c.lower()!="unknown" else "Unknown"

def norm_result(v):
    if not isinstance(v,str): return "—"
    c=v.strip().lower().replace(" ","").replace("-","").replace("_","")
    return RESULT_MAP.get(c,v.strip())

def _read_csv_any_encoding(raw_bytes, filename):
    """
    Try common encodings in order until one works.
    0xAD and similar bytes appear in Windows-1252 / Latin-1 exports
    from Excel, TrackMan desktop, or older scoring software.
    Falls back to UTF-8 with replacement characters as a last resort
    so a single bad byte never blocks the whole file.
    """
    ENCODINGS = [
        "utf-8",          # standard — try first
        "utf-8-sig",      # UTF-8 with BOM (common from Excel "Save as CSV")
        "cp1252",         # Windows Western European — most common culprit
        "latin-1",        # ISO-8859-1 — superset of ASCII, never raises
        "utf-16",         # rare but seen in some export tools
    ]
    for enc in ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(raw_bytes), encoding=enc,
                               low_memory=False), enc
        except (UnicodeDecodeError, Exception):
            continue
    # Absolute fallback: replace undecodable bytes with the replacement char
    return pd.read_csv(io.BytesIO(raw_bytes), encoding="utf-8",
                       encoding_errors="replace", low_memory=False), "utf-8 (lossy)"

@st.cache_data(show_spinner=False)
def load_and_clean(_files_bytes, _file_names, _cache_key):
    frames=[]
    for b,n in zip(_files_bytes,_file_names):
        try:
            df_file, enc = _read_csv_any_encoding(b, n)
            if enc != "utf-8":
                st.sidebar.caption(f"ℹ️ **{n}** read as `{enc}`")
            frames.append(df_file)
        except Exception as e:
            st.warning(f"⚠️ Could not read **{n}**: {e}")
    if not frames: return pd.DataFrame(),0,0
    df=pd.concat(frames,ignore_index=True)
    df=map_cols(df)
    if "Date" in df.columns:
        # v4.2: TrackMan exports are month-first (US); only fall back to
        # dayfirst if standard parsing fails on most rows.
        parsed=pd.to_datetime(df["Date"],errors="coerce",format="mixed")
        if parsed.notna().mean()<0.5:
            alt=pd.to_datetime(df["Date"],dayfirst=True,errors="coerce",format="mixed")
            if alt.notna().sum()>parsed.notna().sum(): parsed=alt
        df["Date"]=parsed
    else:
        df["Date"]=pd.NaT
    before=len(df)
    mask=pd.Series(False,index=df.index)
    for col in ["PitchCall","Batter"]:
        if col in df.columns:
            mask|=(df[col].fillna("").astype(str).str.strip().str.lower().isin(WARMUP))
    df=df[~mask].reset_index(drop=True)
    if "TaggedPitchType" in df.columns:
        df["TaggedPitchType"]=(df["TaggedPitchType"].astype(str).str.strip()
                               .replace({"nan":"Unknown","":"Unknown"}).apply(norm_pt))
    else:
        df["TaggedPitchType"]="Unknown"
    if "PlayResult" in df.columns:
        df["PlayResult"]=df["PlayResult"].astype(str).apply(norm_result)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col]=pd.to_numeric(df[col],errors="coerce")
    if "Balls" in df.columns and "Strikes" in df.columns:
        df["Count"]=(df["Balls"].astype("Int64").astype(str)+"-"
                    +df["Strikes"].astype("Int64").astype(str))
    if "Stadium" in df.columns:
        df["Stadium"]=df["Stadium"].astype(str).str.strip().str.title()
        df["Stadium"]=df["Stadium"].replace({"Nan":"Unknown","":"Unknown"})
    df,pa=dedup_col(df,"Pitcher")
    df,ba=dedup_col(df,"Batter")
    return df,pa,ba

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR FILTERS
# ══════════════════════════════════════════════════════════════════════════════
def sidebar_date_filter(df):
    st.sidebar.markdown('<span class="sb-label">📅 Date Filter</span>',unsafe_allow_html=True)
    valid=df["Date"].dropna()
    if valid.empty: return df
    all_dates=sorted(valid.dt.date.unique())
    min_d,max_d=all_dates[0],all_dates[-1]
    mode=st.sidebar.radio("dm",["📆 Range","🗓️ Specific"],
                          horizontal=True,label_visibility="collapsed",key="date_mode")
    if mode=="📆 Range":
        sel=st.sidebar.date_input("Range",value=(min_d,max_d),min_value=min_d,max_value=max_d)
        s,e=(sel if isinstance(sel,(list,tuple)) and len(sel)==2 else (sel or min_d,sel or min_d))
        filtered=df[(df["Date"].dt.date>=s)&(df["Date"].dt.date<=e)]
        st.sidebar.caption(f"📊 **{len(filtered):,}** pitches · {s}→{e}")
    else:
        dfmt={d:d.strftime("%a %b %d") for d in all_dates}
        fl=[dfmt[d] for d in all_dates]
        chosen=st.sidebar.multiselect("Dates",options=fl,default=fl[-min(7,len(fl)):])
        if not chosen:
            filtered=df.copy()
        else:
            rev={v:k for k,v in dfmt.items()}
            filtered=df[df["Date"].dt.date.isin({rev[l] for l in chosen})]
            st.sidebar.caption(f"📊 **{len(filtered):,}** pitches · **{len(chosen)}** dates")
    return filtered.reset_index(drop=True)

def advanced_filters(df):
    with st.sidebar.expander("⚙️ Advanced Filters",expanded=False):
        for col,lbl in [("BatterSide","Batter Side"),("PitcherThrows","Pitcher Throws")]:
            if col in df.columns:
                opts=sorted(df[col].dropna().unique())
                sel=st.multiselect(lbl,opts,default=opts,key=f"adv_{col}")
                if sel: df=df[df[col].isin(sel)]
        if "TaggedPitchType" in df.columns:
            opts=sorted(df["TaggedPitchType"].dropna().unique())
            sel=st.multiselect("Pitch Types",opts,default=opts,key="adv_pt")
            if sel: df=df[df["TaggedPitchType"].isin(sel)]
        if "Stadium" in df.columns:
            opts=sorted([o for o in df["Stadium"].dropna().unique() if o not in ("Unknown","Nan","")])
            if opts:
                sel=st.multiselect("Stadiums",opts,default=opts,key="adv_stad")
                if sel: df=df[df["Stadium"].isin(sel)]
        if "Inning" in df.columns and df["Inning"].notna().any():
            lo,hi=int(df["Inning"].min()),int(df["Inning"].max())
            if lo<hi:
                rng=st.slider("Inning",lo,hi,(lo,hi),key="adv_inn")
                df=df[(df["Inning"]>=rng[0])&(df["Inning"]<=rng[1])]
    return df.reset_index(drop=True)

def player_search_select(all_players, label, key):
    query=st.text_input(f"🔍 Search {label}",value="",key=f"search_{key}",
                        placeholder=f"Type name to filter {len(all_players)} players…")
    if query.strip():
        q=query.strip().lower()
        filtered=[p for p in all_players if q in p.lower()]
    else:
        filtered=all_players
    if not filtered:
        st.warning("No matches — showing all."); filtered=all_players
    return st.selectbox(label,filtered,key=f"sel_{key}")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
def build_pitch_summary(df):
    total=len(df); rows=[]
    for pt,grp in df.groupby("TaggedPitchType"):
        r={"Pitch":pt,"Count":len(grp),"Usage %":safe_pct(len(grp),total)}
        if "RelSpeed" in grp.columns:
            r["Avg mph"]=round(grp["RelSpeed"].mean(),1)
            r["Max mph"]=round(grp["RelSpeed"].max(),1)
        for col,alias in [("SpinRate","Spin"),("InducedVertBreak","IVB"),("HorzBreak","HB")]:
            r[alias]=round(grp[col].mean(),1) if col in grp.columns else np.nan
        rows.append(r)
    out=pd.DataFrame(rows)
    if out.empty: return out
    out["_fb"]=out["Pitch"].str.lower().str.contains("fastball|4-seam|2-seam").astype(int)
    return out.sort_values(["_fb","Count"],ascending=[False,False]).drop(columns="_fb").reset_index(drop=True)

def compute_pitch_discipline(df):
    """
    Per-pitch-type discipline (v4.2):
      Zone %  = pitches inside the true zone (PlateLoc) / located pitches
      Chase % = swings at pitches OUT of zone / out-of-zone pitches
    Falls back to PitchCall approximation when location data is missing.
    """
    if "PitchCall" not in df.columns: return pd.DataFrame()
    ZONE_CALLS={"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    rows=[]
    for pt,grp in df.groupby("TaggedPitchType"):
        pc=grp["PitchCall"].astype(str)
        n=len(grp)
        sw_m=pc.isin(SWING_CALLS); ct_m=pc.isin(CONTACT_CALLS); wh_m=pc.eq("StrikeSwinging")
        sw,ct,wh=int(sw_m.sum()),int(ct_m.sum()),int(wh_m.sum())
        zone_m,has_loc=in_zone_mask(grp)
        if has_loc:
            located=grp["PlateLocSide"].notna()&grp["PlateLocHeight"].notna()
            n_loc=int(located.sum())
            in_z=int(zone_m.sum())
            oz=located&~zone_m
            zone_pct=safe_pct(in_z,n_loc)
            chase_pct=safe_pct(int((sw_m&oz).sum()),max(int(oz.sum()),1))
        else:
            in_z=int(pc.isin(ZONE_CALLS).sum())
            zone_pct=safe_pct(in_z,n)
            chase_pct=safe_pct(max(0,sw-ct),max(n-in_z,1))
        rows.append({"Pitch":pt,"Count":n,
                     "Zone %":zone_pct,"Swing %":safe_pct(sw,n),
                     "Contact %":safe_pct(ct,max(sw,1)),
                     "Chase %":chase_pct,
                     "Whiff %":safe_pct(wh,max(sw,1))})
    return pd.DataFrame(rows).sort_values("Count",ascending=False).reset_index(drop=True)

def build_play_result_table(df):
    if "PlayResult" not in df.columns: return pd.DataFrame()
    counts=df["PlayResult"].value_counts().reset_index()
    counts.columns=["Result","Count"]
    counts=counts[counts["Result"]!="—"]
    pa=max(count_pa(df),1)                      # v4.2: real PA denominator
    counts["% of PAs"]=counts["Count"].apply(lambda x:safe_pct(x,pa))
    return counts.reset_index(drop=True)

def compute_plate_discipline_batter(df):
    """
    Batter plate discipline (v4.2 fixes):
      • Zone % / Chase % from true pitch location when available
      • K % and BB % per PLATE APPEARANCE (not per pitch)
      • BB counted from PlayResult (a called ball is NOT a walk)
    """
    if "PitchCall" not in df.columns: return {}
    pc=df["PitchCall"].astype(str)
    ZONE_CALLS={"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    n=len(df)
    sw_m=pc.isin(SWING_CALLS); ct_m=pc.isin(CONTACT_CALLS)
    sw,cont,whiff=int(sw_m.sum()),int(ct_m.sum()),int(pc.eq("StrikeSwinging").sum())
    zone_m,has_loc=in_zone_mask(df)
    if has_loc:
        located=df["PlateLocSide"].notna()&df["PlateLocHeight"].notna()
        in_z=int(zone_m.sum()); n_loc=int(located.sum())
        oz=located&~zone_m
        zone_pct=safe_pct(in_z,n_loc)
        chase_pct=safe_pct(int((sw_m&oz).sum()),max(int(oz.sum()),1))
    else:
        in_z=int(pc.isin(ZONE_CALLS).sum())
        zone_pct=safe_pct(in_z,n)
        chase_pct=safe_pct(max(0,sw-cont),max(n-in_z,1))
    pa=count_pa(df)
    kk,bb=count_k_bb(df)
    return {"Zone %":zone_pct, "Swing %":safe_pct(sw,n),
            "Contact %":safe_pct(cont,max(sw,1)),
            "Chase %":chase_pct,
            "Whiff %":safe_pct(whiff,max(sw,1)),
            "K %":safe_pct(kk,max(pa,1)), "BB %":safe_pct(bb,max(pa,1))}

def build_split_table(df, split_col="PitcherThrows", ev_hard=95):
    if split_col not in df.columns: return pd.DataFrame()
    rows=[]
    for hand,grp in df.groupby(split_col):
        n=len(grp); r={"vs":hand,"Pitches":n,"PA":count_pa(grp)}
        if "ExitSpeed" in grp.columns:
            ev=grp["ExitSpeed"].dropna()
            r["Avg EV"]=round(ev.mean(),1) if not ev.empty else np.nan
            r["HH %"]=safe_pct((ev>=ev_hard).sum(),len(ev))
        if "Angle" in grp.columns:
            la=grp["Angle"].dropna()
            r["Avg LA"]=round(la.mean(),1) if not la.empty else np.nan
        disc=compute_plate_discipline_batter(grp)
        r.update({k:v for k,v in disc.items()})
        r["wOBA"]=compute_woba(grp)
        rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)

def build_hitting_monthly(df, lmeta=None):
    ev_hard=(lmeta or {}).get("ev_hard",95)
    barrel_base=(lmeta or {}).get("barrel_ev",98)
    df=df.copy(); df["YearMonth"]=df["Date"].dt.to_period("M")
    rows=[]
    for period,grp in df.groupby("YearMonth"):
        r={"Month":str(period),"Pitches":len(grp),"PA":count_pa(grp)}
        for col,(mx,av) in [("ExitSpeed",("Max EV","Avg EV")),("Angle",("Max LA","Avg LA")),("Distance",("Max Dist","Avg Dist"))]:
            if col in df.columns:
                vals=grp[col].dropna()
                r[mx]=round(vals.max(),1) if not vals.empty else np.nan
                r[av]=round(vals.mean(),1) if not vals.empty else np.nan
        bip=batted_ball_mask(grp)                     # v4.2: batted-ball denominator
        n_bip=int(bip.sum())
        if "ExitSpeed" in df.columns:
            ev=grp.loc[bip,"ExitSpeed"].dropna()
            r["HH %"]=safe_pct(int((ev>=ev_hard).sum()),max(len(ev),1))
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrels=int(barrel_mask(grp[bip],barrel_base).sum()) if n_bip else 0
            r["Barrel %"]=safe_pct(barrels,max(n_bip,1))
        kk,bb=count_k_bb(grp); pa=max(count_pa(grp),1)
        r["K %"]=safe_pct(kk,pa); r["BB %"]=safe_pct(bb,pa)
        r["wOBA"]=compute_woba(grp)
        rows.append(r)
    out=pd.DataFrame(rows)
    return out.sort_values("Month",ascending=False).reset_index(drop=True) if not out.empty else out

def build_league_pitching_avg(df):
    rows=[]
    for pt,grp in df.groupby("TaggedPitchType"):
        n=len(grp)
        if n<10: continue
        r={"Pitch":pt,"Pitches":n}
        for col,alias,dec in [("RelSpeed","Avg mph",1),("SpinRate","Avg Spin",0),
                               ("InducedVertBreak","IVB",1),("HorzBreak","HB",1)]:
            r[alias]=round(grp[col].mean(),dec) if col in grp.columns else np.nan
        rows.append(r)
    out=pd.DataFrame(rows)
    if out.empty: return out
    out["_fb"]=out["Pitch"].str.lower().str.contains("fastball|4-seam|2-seam").astype(int)
    return out.sort_values(["_fb","Pitches"],ascending=[False,False]).drop(columns="_fb").reset_index(drop=True)

def build_league_hitting_avg(df, lmeta=None):
    if "ExitSpeed" not in df.columns: return pd.DataFrame()
    ev_hard=(lmeta or {}).get("ev_hard",95)
    barrel_base=(lmeta or {}).get("barrel_ev",98)
    bip=batted_ball_mask(df); n_bip=max(int(bip.sum()),1)
    ev=df.loc[bip,"ExitSpeed"].dropna()
    la=df.loc[bip,"Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    dist=df.loc[bip,"Distance"].dropna() if "Distance" in df.columns else pd.Series(dtype=float)
    barrels=int(barrel_mask(df[bip],barrel_base).sum()) if "Angle" in df.columns else 0
    kk,bb=count_k_bb(df); pa=max(count_pa(df),1)
    rows=[
        {"Metric":"Avg Exit Velo","League":fmt(ev.mean()," mph"),"Median":fmt(ev.median()," mph"),"Max":fmt(ev.max()," mph")},
        {"Metric":"Avg LA","League":fmt(la.mean(),"°"),"Median":fmt(la.median(),"°"),"Max":fmt(la.max(),"°")},
        {"Metric":"Avg Distance","League":fmt(dist.mean()," ft"),"Median":fmt(dist.median()," ft"),"Max":fmt(dist.max()," ft")},
        {"Metric":f"Hard Hit % (≥{ev_hard})","League":f"{safe_pct(int((ev>=ev_hard).sum()),max(len(ev),1))}%","Median":"—","Max":"—"},
        {"Metric":"Barrel % (of BIP)","League":f"{safe_pct(barrels,n_bip)}%","Median":"—","Max":"—"},
        {"Metric":"K % (per PA)","League":f"{safe_pct(kk,pa)}%","Median":"—","Max":"—"},
        {"Metric":"BB % (per PA)","League":f"{safe_pct(bb,pa)}%","Median":"—","Max":"—"},
        {"Metric":"wOBA","League":fmt(compute_woba(df),"",3),"Median":"—","Max":"—"},
    ]
    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════════════════════════
# SAVANT-STYLE CHARTS
# ══════════════════════════════════════════════════════════════════════════════
def plot_pitch_locations(df, name):
    fig, ax = setup_savant_fig((5.5, 6))
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    for idx,(pt,g) in enumerate(loc.groupby("TaggedPitchType") if not loc.empty else []):
        color=PITCH_PALETTE[idx%len(PITCH_PALETTE)]
        ax.scatter(g["PlateLocSide"],g["PlateLocHeight"],label=pt,color=color,
                   alpha=0.75,s=38,edgecolors="white",linewidths=0.5,zorder=6)
    if loc.empty:
        ax.text(.5,.5,"No location data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
    draw_savant_zone(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)", fontsize=9); ax.set_ylabel("Height (ft)", fontsize=9)
    savant_title(ax,"Pitch Locations",name)
    style_savant_ax(ax)
    ax.legend(fontsize=7.5,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    ax.set_aspect("equal",adjustable="box")
    return fig

def plot_hot_zone(df, name):
    fig, ax = setup_savant_fig((5.5, 6))
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    if len(loc)>=5:
        try:
            sns.kdeplot(data=loc,x="PlateLocSide",y="PlateLocHeight",fill=True,
                        cmap="RdYlBu_r",alpha=0.65,levels=12,thresh=0.04,ax=ax)
        except Exception: pass
    else:
        ax.text(.5,.5,"Need ≥ 5 pitches",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
    draw_savant_zone(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)", fontsize=9); ax.set_ylabel("Height (ft)", fontsize=9)
    savant_title(ax,"Hot Zone (Density)",name)
    style_savant_ax(ax)
    ax.set_aspect("equal",adjustable="box")
    return fig

def plot_spray_chart(df, name):
    fig, ax = setup_savant_fig((6.5, 6.5))
    # v4.2: guard against missing Distance/Bearing columns (was a KeyError)
    if not {"Distance","Bearing"}.issubset(df.columns):
        spray=pd.DataFrame()
    else:
        spray=df.dropna(subset=["Distance","Bearing"]).copy()
    if spray.empty:
        ax.text(.5,.5,"No spray data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        savant_title(ax,"Spray Chart",name); style_savant_ax(ax)
        fig.tight_layout(); return fig
    brad=np.deg2rad(spray["Bearing"])
    spray["Hit_X"]=spray["Distance"]*np.sin(brad)
    spray["Hit_Y"]=spray["Distance"]*np.cos(brad)
    # Field
    for sign in [1,-1]:
        ax.plot([0,sign*420*np.sin(np.deg2rad(45))],[0,420*np.cos(np.deg2rad(45))],
                color=SAVANT_GREY, lw=1.5, alpha=0.5)
    ang=np.linspace(-45,45,300)
    for r, ls in [(230,"--"),(330,"--"),(400,"-")]:
        ax.plot(r*np.sin(np.deg2rad(ang)),r*np.cos(np.deg2rad(ang)),
                color=SAVANT_GREY, lw=0.7, alpha=0.4, linestyle=ls)
    has_ev="ExitSpeed" in spray.columns and spray["ExitSpeed"].notna().any()
    sc=ax.scatter(spray["Hit_X"],spray["Hit_Y"],
                  c=spray["ExitSpeed"] if has_ev else SAVANT_BLUE,
                  cmap="coolwarm" if has_ev else None,
                  s=45, alpha=0.80, edgecolors="white", linewidths=0.5,
                  zorder=5, vmin=65, vmax=112, rasterized=True)
    if has_ev:
        cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.7)
        cb.set_label("Exit Speed (mph)", fontsize=8, color=SAVANT_TEXT)
        cb.ax.tick_params(labelsize=8)
    ax.set_xlim(-360,360); ax.set_ylim(-20,460)
    ax.set_xlabel("Horizontal (ft)", fontsize=9); ax.set_ylabel("Vertical (ft)", fontsize=9)
    savant_title(ax,"Spray Chart",name)
    style_savant_ax(ax)
    ax.set_aspect("equal",adjustable="box")
    return fig

def plot_ev_la_scatter(df, name):
    fig, ax = setup_savant_fig((7, 5))
    needed={"ExitSpeed","Angle"}
    sub=df.dropna(subset=list(needed)).copy() if needed.issubset(df.columns) else pd.DataFrame()
    if sub.empty:
        ax.text(.5,.5,"No EV/LA data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    if "PlayResult" in sub.columns:
        for res,color in RESULT_COLORS.items():
            pts=sub[sub["PlayResult"]==res]
            if len(pts):
                ax.scatter(pts["ExitSpeed"],pts["Angle"],color=color,alpha=0.78,
                           s=30,label=res,edgecolors="white",linewidths=0.5,zorder=5)
        others=sub[~sub["PlayResult"].isin(RESULT_COLORS)]
        if len(others):
            ax.scatter(others["ExitSpeed"],others["Angle"],color="#cccccc",alpha=0.40,
                       s=18,edgecolors="white",linewidths=0.3,zorder=3)
    else:
        ax.scatter(sub["ExitSpeed"],sub["Angle"],color=SAVANT_BLUE,alpha=0.60,
                   s=30,edgecolors="white",linewidths=0.5,zorder=4)
    # Barrel zone
    ax.add_patch(patches.Rectangle((98,8),20,24,lw=1.8,edgecolor=SAVANT_ACCENT,
                                   facecolor=SAVANT_ACCENT,alpha=0.06,linestyle="--",zorder=2))
    ax.text(108.5,20,"BARREL",ha="center",va="center",color=SAVANT_ACCENT,fontsize=9,fontweight="bold",alpha=0.7)
    ax.set_xlabel("Exit Velocity (mph)", fontsize=9); ax.set_ylabel("Launch Angle (°)", fontsize=9)
    savant_title(ax,"Hit Quality Map — Exit Velo × Launch Angle",name)
    style_savant_ax(ax)
    ax.legend(fontsize=7.5,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT,loc="upper left")
    return fig

def plot_damage_zone(df, name):
    fig, ax = setup_savant_fig((5.5, 6))
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    if not loc.empty:
        has_ev="ExitSpeed" in loc.columns and loc["ExitSpeed"].notna().any()
        try:
            sns.kdeplot(data=loc,x="PlateLocSide",y="PlateLocHeight",fill=False,
                        color=SAVANT_GREY,alpha=0.3,levels=5,thresh=0.1,ax=ax,zorder=3)
        except Exception: pass
        sc=ax.scatter(loc["PlateLocSide"],loc["PlateLocHeight"],
                      c=loc["ExitSpeed"] if has_ev else SAVANT_ACCENT,
                      cmap="coolwarm" if has_ev else None,
                      s=42,alpha=0.75,edgecolors="white",
                      linewidths=0.5,zorder=6,vmin=65,vmax=112)
        if has_ev:
            cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.7)
            cb.set_label("Exit Speed (mph)", fontsize=8, color=SAVANT_TEXT)
            cb.ax.tick_params(labelsize=8)
    else:
        ax.text(.5,.5,"No location data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
    draw_savant_zone(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)", fontsize=9); ax.set_ylabel("Height (ft)", fontsize=9)
    savant_title(ax,"Damage Zone",name)
    style_savant_ax(ax)
    ax.set_aspect("equal",adjustable="box")
    return fig

def plot_ev_distribution(df, name):
    fig, ax = setup_savant_fig((7, 4))
    ev=df["ExitSpeed"].dropna() if "ExitSpeed" in df.columns else pd.Series(dtype=float)
    if ev.empty:
        ax.text(.5,.5,"No EV data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    _,bins,patches_list=ax.hist(ev,bins=24,color=SAVANT_BLUE,alpha=0.72,
                                 edgecolor="#ffffff",linewidth=0.6)
    for p,left in zip(patches_list,bins[:-1]):
        if left>=95: p.set_facecolor(SAVANT_RED); p.set_alpha(0.85)
    ax.axvline(ev.mean(),color=SAVANT_TEXT,lw=1.6,linestyle="--",zorder=6,
               label=f"Avg {ev.mean():.1f}")
    ax.axvline(95,color=SAVANT_RED,lw=1.4,linestyle=":",zorder=6,label="Hard Hit (95)")
    hh=(ev>=95).sum()
    ax.text(0.97,0.93,f"HH: {hh} ({safe_pct(hh,len(ev))}%)",transform=ax.transAxes,
            ha="right",va="top",color=SAVANT_RED,fontsize=9,fontweight="bold")
    ax.set_xlabel("Exit Velocity (mph)", fontsize=9); ax.set_ylabel("Count", fontsize=9)
    savant_title(ax,"Exit Velocity Distribution",name)
    style_savant_ax(ax)
    ax.legend(fontsize=8,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    return fig

def plot_la_distribution(df, name):
    fig, ax = setup_savant_fig((7, 4))
    la=df["Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    if la.empty:
        ax.text(.5,.5,"No LA data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    _,bins,patches_list=ax.hist(la,bins=24,color=SAVANT_BLUE,alpha=0.72,
                                 edgecolor="#ffffff",linewidth=0.6)
    for p,left,right in zip(patches_list,bins[:-1],bins[1:]):
        if left>=8 and right<=32: p.set_facecolor(SAVANT_GREEN); p.set_alpha(0.85)
    ax.axvspan(8,32,alpha=0.07,color=SAVANT_GREEN,label="Barrel 8–32°",zorder=1)
    ax.axvline(la.mean(),color=SAVANT_TEXT,lw=1.6,linestyle="--",zorder=6,
               label=f"Avg {la.mean():.1f}°")
    barrel=((la>=8)&(la<=32)).sum()
    ax.text(0.97,0.93,f"Barrel: {barrel} ({safe_pct(barrel,len(la))}%)",transform=ax.transAxes,
            ha="right",va="top",color=SAVANT_GREEN,fontsize=9,fontweight="bold")
    ax.set_xlabel("Launch Angle (°)", fontsize=9); ax.set_ylabel("Count", fontsize=9)
    savant_title(ax,"Launch Angle Distribution",name)
    style_savant_ax(ax)
    ax.legend(fontsize=8,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    return fig

def plot_velocity_tendency(df, name):
    fig, ax = setup_savant_fig((11, 3.8))
    vel=df.dropna(subset=["RelSpeed","Date"]) if "RelSpeed" in df.columns else pd.DataFrame()
    if vel.empty:
        ax.text(.5,.5,"No velocity data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    for idx,(pt,g) in enumerate(vel.groupby("TaggedPitchType")):
        daily=g.sort_values("Date").groupby("Date")["RelSpeed"].agg(["mean","std"]).reset_index()
        daily.columns=["Date","mean","std"]; daily["std"]=daily["std"].fillna(0)
        color=PITCH_PALETTE[idx%len(PITCH_PALETTE)]
        ax.fill_between(daily["Date"],daily["mean"]-daily["std"],daily["mean"]+daily["std"],
                        alpha=0.08,color=color,zorder=1)
        ax.plot(daily["Date"],daily["mean"],label=pt,color=color,lw=2.0,
                marker="o",ms=4.5,markeredgecolor="white",markeredgewidth=0.6,
                alpha=0.90,zorder=5,solid_capstyle="round")
        if not daily.empty:
            last=daily.iloc[-1]
            ax.annotate(f'{last["mean"]:.1f}',(last["Date"],last["mean"]),
                        xytext=(4,4),textcoords="offset points",fontsize=8,color=color,fontweight="bold")
    ax.set_xlabel("Date", fontsize=9); ax.set_ylabel("Avg Velocity (mph)", fontsize=9)
    savant_title(ax,"Velocity Tendency",name)
    style_savant_ax(ax)
    ax.legend(fontsize=7.5,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    fig.autofmt_xdate(rotation=28,ha="right"); return fig

def plot_movement_profile(df, name):
    fig, ax = setup_savant_fig((6.5, 5.8))
    needed={"HorzBreak","InducedVertBreak"}
    if not needed.issubset(df.columns):
        ax.text(.5,.5,"No movement data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    sub=df.dropna(subset=["HorzBreak","InducedVertBreak"])
    for idx,(pt,g) in enumerate(sub.groupby("TaggedPitchType")):
        x,y,n=g["HorzBreak"].mean(),g["InducedVertBreak"].mean(),len(g)
        color=PITCH_PALETTE[idx%len(PITCH_PALETTE)]
        ax.scatter(g["HorzBreak"],g["InducedVertBreak"],color=color,alpha=0.08,s=8,edgecolors="none",zorder=3)
        ax.scatter(x,y,s=max(n*3.5,70),color=color,alpha=0.88,
                   edgecolors="white",linewidths=1.2,zorder=6)
        ax.annotate(f"{pt}\n(n={n})",(x,y),xytext=(6,4),textcoords="offset points",
                    fontsize=8,color=color,fontweight="bold")
    ax.axhline(0,color=SAVANT_GREY,lw=0.8,alpha=0.6,zorder=2)
    ax.axvline(0,color=SAVANT_GREY,lw=0.8,alpha=0.6,zorder=2)
    ax.text(0.82,0.95,"Rise/Arm",transform=ax.transAxes,ha="center",fontsize=7.5,color=SAVANT_GREY,alpha=0.5)
    ax.text(0.18,0.95,"Rise/Glove",transform=ax.transAxes,ha="center",fontsize=7.5,color=SAVANT_GREY,alpha=0.5)
    ax.text(0.82,0.05,"Drop/Arm",transform=ax.transAxes,ha="center",fontsize=7.5,color=SAVANT_GREY,alpha=0.5)
    ax.text(0.18,0.05,"Drop/Glove",transform=ax.transAxes,ha="center",fontsize=7.5,color=SAVANT_GREY,alpha=0.5)
    ax.set_xlabel("Horizontal Break (in) — Arm side →", fontsize=9)
    ax.set_ylabel("Induced Vert Break (in) — Rise →", fontsize=9)
    savant_title(ax,"Movement Profile",name)
    style_savant_ax(ax); return fig

# ══════════════════════════════════════════════════════════════════════════════
# NEW ANALYTICS v4.2 — usage by count, rolling EV, per-pitch heatmaps
# ══════════════════════════════════════════════════════════════════════════════
def build_usage_by_count(df):
    """Pitch usage % by ball-strike count (rows=pitch, cols=count)."""
    if "Count" not in df.columns or df["Count"].isna().all(): return pd.DataFrame()
    sub=df[df["Count"].notna()&~df["Count"].str.contains("<NA>",na=True)]
    if sub.empty: return pd.DataFrame()
    order=[f"{b}-{s}" for b in range(4) for s in range(3)]
    tab=pd.crosstab(sub["TaggedPitchType"],sub["Count"],normalize="columns")*100
    cols=[c for c in order if c in tab.columns]
    return tab[cols].round(1) if cols else pd.DataFrame()

def plot_usage_by_count(df, name):
    tab=build_usage_by_count(df)
    fig, ax = setup_savant_fig((11, 0.55*max(len(tab),4)+2))
    if tab.empty:
        ax.text(.5,.5,"Balls/Strikes columns required",ha="center",va="center",
                color=SAVANT_GREY,transform=ax.transAxes)
        ax.axis("off"); return fig
    im=ax.imshow(tab.values,cmap="Blues",aspect="auto",vmin=0,vmax=max(tab.values.max(),1))
    ax.set_xticks(range(len(tab.columns)),tab.columns,fontsize=8.5)
    ax.set_yticks(range(len(tab.index)),tab.index,fontsize=8.5)
    for i in range(tab.shape[0]):
        for j in range(tab.shape[1]):
            v=tab.values[i,j]
            if v>0:
                ax.text(j,i,f"{v:.0f}",ha="center",va="center",fontsize=7.5,
                        color="#ffffff" if v>tab.values.max()*0.6 else SAVANT_TEXT)
    ax.set_xlabel("Count (Balls-Strikes)",fontsize=9)
    savant_title(ax,"Pitch Usage % by Count",name)
    ax.grid(False)
    for s in ax.spines.values(): s.set_visible(False)
    cb=fig.colorbar(im,ax=ax,pad=0.02,shrink=0.8); cb.set_label("Usage %",fontsize=8)
    return fig

def plot_rolling_ev(df, name, window=15):
    """Rolling exit-velocity trend over batted balls, chronological."""
    fig, ax = setup_savant_fig((11, 3.8))
    bip=df[batted_ball_mask(df)].dropna(subset=["ExitSpeed"]).copy()
    if "Date" in bip.columns: bip=bip.sort_values("Date")
    if len(bip)<5:
        ax.text(.5,.5,"Need ≥ 5 batted balls",ha="center",va="center",
                color=SAVANT_GREY,transform=ax.transAxes)
        return fig
    ev=bip["ExitSpeed"].reset_index(drop=True)
    roll=ev.rolling(window,min_periods=max(3,window//3)).mean()
    x=np.arange(1,len(ev)+1)
    ax.scatter(x,ev,s=16,color=SAVANT_BLUE,alpha=0.35,edgecolors="none",zorder=3,label="Batted ball EV")
    ax.plot(x,roll,color=SAVANT_RED,lw=2.2,zorder=5,label=f"Rolling avg ({window} BIP)")
    ax.axhline(ev.mean(),color=SAVANT_GREY,lw=1.1,linestyle="--",zorder=2,label=f"Season avg {ev.mean():.1f}")
    ax.set_xlabel("Batted ball # (chronological)",fontsize=9)
    ax.set_ylabel("Exit Velocity (mph)",fontsize=9)
    savant_title(ax,"Rolling Exit Velocity",name)
    style_savant_ax(ax)
    ax.legend(fontsize=8,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    return fig

def plot_location_by_pitch(df, name, max_types=6):
    """Small-multiple location heatmaps, one per pitch type."""
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    types=(loc["TaggedPitchType"].value_counts().head(max_types).index.tolist()
           if not loc.empty else [])
    n=len(types)
    if n==0:
        fig, ax = setup_savant_fig((6,4))
        ax.text(.5,.5,"No location data",ha="center",va="center",
                color=SAVANT_GREY,transform=ax.transAxes)
        ax.axis("off"); return fig
    ncols=min(n,3); nrows=int(np.ceil(n/ncols))
    fig, axes = plt.subplots(nrows,ncols,figsize=(3.6*ncols,4.2*nrows),layout="constrained")
    fig.patch.set_facecolor(SAVANT_BG)
    axes=np.atleast_1d(axes).ravel()
    for ax,pt in zip(axes,types):
        g=loc[loc["TaggedPitchType"]==pt]
        ax.set_facecolor(SAVANT_BG)
        if len(g)>=5:
            try:
                sns.kdeplot(data=g,x="PlateLocSide",y="PlateLocHeight",fill=True,
                            cmap="RdYlBu_r",alpha=0.65,levels=10,thresh=0.05,ax=ax)
            except Exception: pass
        ax.scatter(g["PlateLocSide"],g["PlateLocHeight"],s=8,color=SAVANT_TEXT,
                   alpha=0.25,edgecolors="none",zorder=5)
        draw_savant_zone(ax); draw_plate(ax)
        ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
        ax.set_title(f"{pt} (n={len(g)})",fontsize=9,fontweight="bold",color=SAVANT_TEXT)
        ax.set_xlabel(""); ax.set_ylabel("")
        style_savant_ax(ax)
        ax.set_aspect("equal",adjustable="box")
    for ax in axes[n:]: ax.axis("off")
    fig.suptitle(f"Location by Pitch Type — {name}",fontsize=11,fontweight="bold",color=SAVANT_TEXT)
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# TOP PLAYS v4.2 — leaderboards, quick questions & social-media cards
# ══════════════════════════════════════════════════════════════════════════════
def _lb_cols(df, wanted):
    return [c for c in wanted if c in df.columns]

def top_hardest_hits(df, n=10, unique_player=False):
    if "ExitSpeed" not in df.columns: return pd.DataFrame()
    bip=df[batted_ball_mask(df)].dropna(subset=["ExitSpeed"]).copy()
    if bip.empty: return pd.DataFrame()
    bip=bip.sort_values("ExitSpeed",ascending=False)
    if unique_player and "Batter" in bip.columns:
        bip=bip.drop_duplicates(subset=["Batter"])
    cols=_lb_cols(bip,["Batter","ExitSpeed","Angle","Distance","PlayResult","Pitcher","Stadium","Date"])
    out=bip[cols].head(n).reset_index(drop=True)
    if "Date" in out.columns: out["Date"]=pd.to_datetime(out["Date"]).dt.strftime("%b %d")
    return out

def top_longest_hrs(df, n=10, unique_player=False):
    if "PlayResult" not in df.columns: return pd.DataFrame()
    hrs=df[df["PlayResult"].astype(str)=="HR"].copy()
    if hrs.empty: return pd.DataFrame()
    sort_col="Distance" if "Distance" in hrs.columns and hrs["Distance"].notna().any() else "ExitSpeed"
    if sort_col not in hrs.columns: return pd.DataFrame()
    hrs=hrs.dropna(subset=[sort_col]).sort_values(sort_col,ascending=False)
    if unique_player and "Batter" in hrs.columns:
        hrs=hrs.drop_duplicates(subset=["Batter"])
    cols=_lb_cols(hrs,["Batter","Distance","ExitSpeed","Angle","Pitcher","Stadium","Date"])
    out=hrs[cols].head(n).reset_index(drop=True)
    if "Date" in out.columns: out["Date"]=pd.to_datetime(out["Date"]).dt.strftime("%b %d")
    return out

def top_fastest_pitches(df, n=10, unique_player=False):
    if "RelSpeed" not in df.columns: return pd.DataFrame()
    p=df.dropna(subset=["RelSpeed"]).sort_values("RelSpeed",ascending=False).copy()
    if p.empty: return pd.DataFrame()
    if unique_player and "Pitcher" in p.columns:
        p=p.drop_duplicates(subset=["Pitcher"])
    cols=_lb_cols(p,["Pitcher","RelSpeed","TaggedPitchType","SpinRate","PitchCall","Stadium","Date"])
    out=p[cols].head(n).reset_index(drop=True)
    if "Date" in out.columns: out["Date"]=pd.to_datetime(out["Date"]).dt.strftime("%b %d")
    return out

def top_spin_pitches(df, n=10, unique_player=False):
    if "SpinRate" not in df.columns: return pd.DataFrame()
    p=df.dropna(subset=["SpinRate"]).sort_values("SpinRate",ascending=False).copy()
    if p.empty: return pd.DataFrame()
    if unique_player and "Pitcher" in p.columns:
        p=p.drop_duplicates(subset=["Pitcher"])
    cols=_lb_cols(p,["Pitcher","SpinRate","TaggedPitchType","RelSpeed","Stadium","Date"])
    out=p[cols].head(n).reset_index(drop=True)
    if "Date" in out.columns: out["Date"]=pd.to_datetime(out["Date"]).dt.strftime("%b %d")
    return out

def top_barrels_lb(df, n=10, unique_player=False, barrel_base=98):
    bm=barrel_mask(df,barrel_base)&batted_ball_mask(df)
    b=df[bm].copy()
    if b.empty or "ExitSpeed" not in b.columns: return pd.DataFrame()
    b=b.sort_values("ExitSpeed",ascending=False)
    if unique_player and "Batter" in b.columns:
        b=b.drop_duplicates(subset=["Batter"])
    cols=_lb_cols(b,["Batter","ExitSpeed","Angle","Distance","PlayResult","Stadium","Date"])
    out=b[cols].head(n).reset_index(drop=True)
    if "Date" in out.columns: out["Date"]=pd.to_datetime(out["Date"]).dt.strftime("%b %d")
    return out

QUICK_QUESTIONS={
    "🔥 ¿Cuáles fueron los batazos más fuertes?":
        {"fn":top_hardest_hits,"player_col":"Batter","value_col":"ExitSpeed",
         "unit":"mph","title":"BATAZOS MÁS FUERTES","accent":"#ff4d4d"},
    "🚀 ¿Cuáles fueron los HRs más largos?":
        {"fn":top_longest_hrs,"player_col":"Batter","value_col":"Distance",
         "unit":"ft","title":"HOME RUNS MÁS LARGOS","accent":"#ffb347"},
    "⚡ ¿Cuáles fueron los lanzamientos más rápidos?":
        {"fn":top_fastest_pitches,"player_col":"Pitcher","value_col":"RelSpeed",
         "unit":"mph","title":"LANZAMIENTOS MÁS RÁPIDOS","accent":"#4da6ff"},
    "🌪️ ¿Quién generó más spin?":
        {"fn":top_spin_pitches,"player_col":"Pitcher","value_col":"SpinRate",
         "unit":"rpm","title":"MAYOR SPIN RATE","accent":"#b98aff"},
    "🎯 ¿Cuáles fueron los mejores barrels?":
        {"fn":top_barrels_lb,"player_col":"Batter","value_col":"ExitSpeed",
         "unit":"mph","title":"MEJORES BARRELS","accent":"#3ddc84"},
}

def make_social_card(lb, meta, subtitle, tournament=""):
    """
    1080×1080 social-media-ready graphic (dark theme) with the top-5 plays.
    Readable by anyone: rank, player, big value, context line.
    """
    BG,FG,SUB="#0d1b2a","#ffffff","#8ea8c3"
    accent=meta["accent"]
    fig=plt.figure(figsize=(10.8,10.8),dpi=100)
    fig.patch.set_facecolor(BG)
    ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.axis("off"); ax.set_facecolor(BG)
    ax.add_patch(patches.Rectangle((0,0.90),1,0.10,color=accent,alpha=0.14))
    ax.add_patch(patches.Rectangle((0,0.90),0.012,0.10,color=accent))
    ax.text(0.05,0.955,"TRACKMAN · TOP PLAYS",fontsize=15,color=SUB,fontweight="bold",va="center")
    ax.text(0.05,0.915,meta["title"],fontsize=30,color=FG,fontweight="bold",va="center")
    line3=subtitle+(f"  ·  {tournament}" if tournament else "")
    ax.text(0.05,0.868,line3,fontsize=13,color=SUB,va="center")
    n=min(len(lb),5)
    row_h=0.145
    y0=0.80-(0.725-n*row_h)/2          # center the block when fewer than 5 rows
    pcol=meta["player_col"]; vcol=meta["value_col"]
    for i in range(n):
        r=lb.iloc[i]; y=y0-i*row_h
        ax.add_patch(patches.FancyBboxPatch((0.045,y-row_h+0.028),0.91,row_h-0.036,
            boxstyle="round,pad=0.008",linewidth=1.2,
            edgecolor=accent if i==0 else "#22334a",
            facecolor="#13263d" if i==0 else "#102135"))
        ax.text(0.085,y-row_h/2+0.01,f"{i+1}",fontsize=30,color=accent,
                fontweight="bold",ha="center",va="center")
        player=str(r.get(pcol,"—"))
        ax.text(0.13,y-row_h/2+0.032,player,fontsize=19,color=FG,fontweight="bold",va="center")
        bits=[]
        for c,suf in [("TaggedPitchType",""),("PlayResult",""),("Angle","° LA"),("Stadium",""),("Date","")]:
            v=r.get(c)
            if v is not None and str(v) not in ("nan","—","NaT","None",""):
                bits.append(f"{v:.0f}{suf}" if isinstance(v,(int,float,np.floating)) else str(v))
        ax.text(0.13,y-row_h/2-0.026,"  ·  ".join(bits[:4]),fontsize=11.5,color=SUB,va="center")
        val=r.get(vcol)
        vtxt=f"{val:.1f}" if isinstance(val,(int,float,np.floating)) else str(val)
        ax.text(0.885,y-row_h/2+0.012,vtxt,fontsize=28,color=accent,
                fontweight="bold",ha="right",va="center")
        ax.text(0.885,y-row_h/2-0.032,meta["unit"],fontsize=11,color=SUB,ha="right",va="center")
    ax.text(0.5,0.035,"Generado con Trackman Analytics v4.2",fontsize=10,
            color=SUB,alpha=0.6,ha="center")
    return fig

def render_top_plays(df, lmeta, tournament=""):
    st.markdown('<div class="sh">🔥 Top Plays — Contenido para redes</div>',unsafe_allow_html=True)
    if df["Date"].notna().any():
        max_d=df["Date"].max()
        period=st.radio("Periodo",["Última semana","Últimos 14 días","Últimos 30 días","Todo"],
                        horizontal=True,key="tp_period")
        days={"Última semana":7,"Últimos 14 días":14,"Últimos 30 días":30}.get(period)
        sub=df[df["Date"]>=max_d-pd.Timedelta(days=days)] if days else df
        dr=(f"{sub['Date'].min().strftime('%b %d')} – {sub['Date'].max().strftime('%b %d, %Y')}"
            if sub["Date"].notna().any() else "Todas las fechas")
    else:
        sub=df; dr="Todas las fechas"
        st.caption("Sin columna de fecha válida — mostrando todo el dataset.")
    c1,c2,c3=st.columns([3,1,1])
    with c1:
        q=st.selectbox("Pregúntale a los datos",list(QUICK_QUESTIONS.keys()),key="tp_q")
    with c2:
        topn=st.number_input("Top N",3,25,10,key="tp_n")
    with c3:
        uniq=st.checkbox("1 por jugador",value=True,key="tp_uniq",
                         help="Muestra solo la mejor jugada de cada jugador")
    meta=QUICK_QUESTIONS[q]
    kw={"n":int(topn),"unique_player":uniq}
    if meta["fn"] is top_barrels_lb: kw["barrel_base"]=lmeta.get("barrel_ev",98)
    lb=meta["fn"](sub,**kw)
    if lb.empty:
        st.warning("No hay datos suficientes para esta pregunta en el periodo seleccionado.")
        return
    st.markdown(f'<div class="sh">{meta["title"]} · {dr}</div>',unsafe_allow_html=True)
    st.dataframe(lb,use_container_width=True)
    csv_dl(lb,"top_plays.csv")
    if "Stadium" in sub.columns and sub["Stadium"].nunique()>1:
        with st.expander("🏟️ Ver top por estadio / región"):
            for stad,grp in sub.groupby("Stadium"):
                if stad in ("Unknown","Nan",""): continue
                kw_s=dict(kw); kw_s["n"]=min(int(topn),5)
                lb_s=meta["fn"](grp,**kw_s)
                if lb_s.empty: continue
                st.markdown(f"**{stad}**")
                st.dataframe(lb_s,use_container_width=True)
    st.markdown('<div class="sh">📱 Tarjeta para redes sociales</div>',unsafe_allow_html=True)
    fig_card=make_social_card(lb,meta,dr,tournament)
    cl,cr=st.columns([2,1])
    with cl: st.pyplot(fig_card,use_container_width=True)
    with cr:
        st.caption("Imagen 1080×1080 lista para Instagram / X / Facebook.")
        buf=io.BytesIO()
        fig_card.savefig(buf,format="png",dpi=100,facecolor=fig_card.get_facecolor())
        buf.seek(0)
        st.download_button("⬇️ Descargar PNG",buf.read(),
                           f"top_plays_{meta['value_col'].lower()}.png","image/png")
    plt.close(fig_card)

# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT (fixed for matplotlib 3.8+)
# ══════════════════════════════════════════════════════════════════════════════
def _fig_to_img(src_fig):
    import matplotlib.image as mpimg
    img_buf = io.BytesIO()
    src_fig.savefig(img_buf, format="png", dpi=150,
                    bbox_inches="tight", facecolor=src_fig.get_facecolor())
    img_buf.seek(0)
    return mpimg.imread(img_buf)

def _pdf_cover(pdf, name, date_range, dtype):
    fig=plt.figure(figsize=(11,8.5)); fig.patch.set_facecolor(SAVANT_BG)
    ax=fig.add_subplot(111); ax.axis("off"); ax.set_facecolor(SAVANT_BG)
    ax.text(0.5,0.88,"⚾  TRACKMAN ANALYTICS",transform=ax.transAxes,
            ha="center",va="center",fontsize=20,fontweight="bold",color=SAVANT_ACCENT,fontfamily="monospace")
    ax.text(0.5,0.72,name,transform=ax.transAxes,
            ha="center",va="center",fontsize=28,fontweight="bold",color=SAVANT_TEXT)
    ax.text(0.5,0.62,dtype,transform=ax.transAxes,
            ha="center",va="center",fontsize=12,color=SAVANT_GREY)
    ax.text(0.5,0.52,f"Date Range: {date_range}",transform=ax.transAxes,
            ha="center",va="center",fontsize=10,color=SAVANT_GREY)
    ax.text(0.5,0.22,"Generated by Trackman Analytics Dashboard v4.2 (Savant Edition)",
            transform=ax.transAxes,ha="center",va="center",
            fontsize=9,color=SAVANT_GREY,alpha=0.6)
    pdf.savefig(fig,bbox_inches="tight",facecolor=SAVANT_BG); plt.close(fig)

def _pdf_table_page(pdf, df, title, subtitle=""):
    fh=max(4,min(len(df)*0.5+2,10))
    fig=plt.figure(figsize=(13,fh)); fig.patch.set_facecolor(SAVANT_BG)
    ax=fig.add_subplot(111); ax.axis("off"); ax.set_facecolor(SAVANT_BG)
    ax.text(0.02,0.97,title,transform=ax.transAxes,va="center",fontsize=11,fontweight="bold",color=SAVANT_TEXT)
    if subtitle: ax.text(0.98,0.97,subtitle,transform=ax.transAxes,va="center",ha="right",fontsize=9,color=SAVANT_GREY)
    cols=list(df.columns); data=df.fillna("—").values.tolist()
    tbl=ax.table(cellText=data,colLabels=cols,loc="center",cellLoc="center",bbox=[0,0.05,1,0.85])
    tbl.auto_set_font_size(False); tbl.set_fontsize(8.5); tbl.auto_set_column_width(col=list(range(len(cols))))
    for j in range(len(cols)):
        c=tbl[0,j]; c.set_facecolor(SAVANT_ACCENT); c.set_text_props(color="#fff",fontweight="bold")
        c.set_edgecolor(SAVANT_BG); c.set_linewidth(0.5)
    for i in range(1,len(data)+1):
        for j in range(len(cols)):
            c=tbl[i,j]; c.set_facecolor(SAVANT_GRID if i%2==0 else SAVANT_BG)
            c.set_text_props(color=SAVANT_TEXT); c.set_edgecolor(SAVANT_BG); c.set_linewidth(0.5)
    tbl.scale(1,1.4); fig.tight_layout()
    pdf.savefig(fig,bbox_inches="tight",facecolor=SAVANT_BG); plt.close(fig)

def _pdf_two_charts(pdf, fig1, fig2, label1="", label2=""):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.patch.set_facecolor(SAVANT_BG)
    for ax_new, src_fig, lbl in zip(axes, [fig1, fig2], [label1, label2]):
        ax_new.set_facecolor(SAVANT_BG); ax_new.axis("off")
        if src_fig is not None:
            try:
                img = _fig_to_img(src_fig)
                ax_new.imshow(img, aspect="auto")
            except Exception:
                ax_new.text(0.5, 0.5, "Chart unavailable", ha="center", va="center",
                            color=SAVANT_GREY, transform=ax_new.transAxes)
        if lbl: ax_new.set_title(lbl, color=SAVANT_GREY, fontsize=9, pad=4)
    fig.tight_layout(pad=0.3)
    pdf.savefig(fig, bbox_inches="tight", facecolor=SAVANT_BG)
    plt.close(fig)

def _pdf_single_chart(pdf, src_fig, label=""):
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(SAVANT_BG); ax.set_facecolor(SAVANT_BG); ax.axis("off")
    if src_fig is not None:
        try:
            img = _fig_to_img(src_fig)
            ax.imshow(img, aspect="auto")
        except Exception:
            ax.text(0.5, 0.5, "Chart unavailable", ha="center", va="center",
                    color=SAVANT_GREY, transform=ax.transAxes)
    if label: ax.set_title(label, color=SAVANT_GREY, fontsize=9, pad=4)
    fig.tight_layout(pad=0.3)
    pdf.savefig(fig, bbox_inches="tight", facecolor=SAVANT_BG)
    plt.close(fig)

def export_pitching_pdf(pitcher, summary_df, disc_df, fig_loc, fig_kde, fig_vel, fig_mov, date_range):
    buf=io.BytesIO()
    with PdfPages(buf) as pdf:
        _pdf_cover(pdf, pitcher, date_range, "Pitching Report")
        if not summary_df.empty: _pdf_table_page(pdf, summary_df, "Arsenal Summary", pitcher)
        if not disc_df.empty: _pdf_table_page(pdf, disc_df, "Pitch Discipline", pitcher)
        _pdf_two_charts(pdf, fig_loc, fig_kde, "Pitch Locations", "Hot Zone")
        _pdf_single_chart(pdf, fig_vel, "Velocity Tendency")
        _pdf_single_chart(pdf, fig_mov, "Movement Profile")
    buf.seek(0); return buf.read()

def export_hitting_pdf(batter, monthly_df, disc_dict, result_df, split_df, fig_spray, fig_dmg, fig_ev, fig_la, fig_ev_la, date_range):
    buf=io.BytesIO()
    with PdfPages(buf) as pdf:
        _pdf_cover(pdf, batter, date_range, "Hitting Report")
        if not monthly_df.empty: _pdf_table_page(pdf, monthly_df, "Monthly Progression", batter)
        if disc_dict:
            disc_df=pd.DataFrame([disc_dict]); _pdf_table_page(pdf, disc_df, "Plate Discipline", batter)
        if not result_df.empty: _pdf_table_page(pdf, result_df, "Play Results", batter)
        if not split_df.empty: _pdf_table_page(pdf, split_df, "vs RHP / LHP Splits", batter)
        _pdf_two_charts(pdf, fig_spray, fig_dmg, "Spray Chart", "Damage Zone")
        _pdf_two_charts(pdf, fig_ev, fig_la, "Exit Velo Dist", "Launch Angle Dist")
        _pdf_single_chart(pdf, fig_ev_la, "Hit Quality Map")
    buf.seek(0); return buf.read()

# ══════════════════════════════════════════════════════════════════════════════
# RENDER: PITCHING
# ══════════════════════════════════════════════════════════════════════════════
def render_pitching(df, master_df, lmeta):
    st.markdown('<div class="sh">⚾ Pitching Dashboard</div>',unsafe_allow_html=True)
    st.info(f"📋 **{lmeta['label']} benchmarks** · "
            f"Elite velo: {lmeta['velo_elite']}+ mph · Avg: {lmeta['velo_avg']} mph · "
            f"{lmeta['context']}")
    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column."); return
    pitchers=sorted(df["Pitcher"].dropna().unique())
    selected=player_search_select(pitchers,"Select Pitcher","pitcher")
    pf=df[df["Pitcher"]==selected].copy(); n=len(pf)
    if n<15: st.warning(f"⚠️ **{selected}** — only **{n}** pitches (min: 15).")
    avg_v=pf["RelSpeed"].mean() if "RelSpeed" in pf.columns else np.nan
    max_v=pf["RelSpeed"].max() if "RelSpeed" in pf.columns else np.nan
    avg_sp=pf["SpinRate"].mean() if "SpinRate" in pf.columns else np.nan
    c1,c2,c3,c4,c5=st.columns(5)
    with c1: st.metric("Pitches",f"{n:,}")
    with c2: st.metric("Avg Velo",fmt(avg_v," mph"),delta=f"Max {max_v:.1f}" if not np.isnan(max_v) else None)
    with c3: st.metric("Avg Spin",fmt(avg_sp," rpm",0))
    with c4: st.metric("Pitches Types",str(pf["TaggedPitchType"].nunique()))
    with c5: st.metric("Distinct Dates",str(pf["Date"].dt.date.nunique()) if "Date" in pf.columns else "—")
    st.markdown("<br>",unsafe_allow_html=True)
    tab1,tab2,tab3,tab4=st.tabs(["📋 Summary","📍 Location","📊 Trends","🏟️ Stadium"])
    with tab1:
        st.markdown('<div class="sh">Arsenal</div>',unsafe_allow_html=True)
        summary_df=build_pitch_summary(pf)
        st.dataframe(summary_df,use_container_width=True,hide_index=True)
        csv_dl(summary_df,f"{selected}_summary.csv")
        st.markdown('<div class="sh">Discipline</div>',unsafe_allow_html=True)
        disc_df=compute_pitch_discipline(pf)
        if disc_df.empty: st.info("PitchCall column required.")
        else:
            st.dataframe(disc_df,use_container_width=True,hide_index=True)
            csv_dl(disc_df,f"{selected}_discipline.csv")
    with tab2:
        cl,cr=st.columns(2)
        fig_loc=plot_pitch_locations(pf,selected)
        fig_kde=plot_hot_zone(pf,selected)
        with cl: st.pyplot(fig_loc,use_container_width=True)
        with cr: st.pyplot(fig_kde,use_container_width=True)
        st.markdown('<div class="sh">Location by Pitch Type</div>',unsafe_allow_html=True)
        fig_bytype=plot_location_by_pitch(pf,selected)
        st.pyplot(fig_bytype,use_container_width=True); plt.close(fig_bytype)
    with tab3:
        fig_vel=plot_velocity_tendency(pf,selected)
        st.pyplot(fig_vel,use_container_width=True)
        st.markdown("<br>",unsafe_allow_html=True)
        fig_usage=plot_usage_by_count(pf,selected)
        st.pyplot(fig_usage,use_container_width=True); plt.close(fig_usage)
        st.markdown("<br>",unsafe_allow_html=True)
        fig_mov=plot_movement_profile(pf,selected)
        st.pyplot(fig_mov,use_container_width=True)
    with tab4:
        st.info("Stadium analysis coming soon.")
    st.markdown('<div class="sh">📤 Export</div>',unsafe_allow_html=True)
    dr=f"{df['Date'].min().date()}→{df['Date'].max().date()}" if df["Date"].notna().any() else "All dates"
    ec1,ec2=st.columns(2)
    with ec1:
        # v4.2: PDF built only on demand — avoids regenerating on every rerun
        if st.button("📄 Build PDF Report",key="btn_pdf_pitch"):
            with st.spinner("Building PDF…"):
                pdf_b=export_pitching_pdf(selected,summary_df,
                                           disc_df if not disc_df.empty else pd.DataFrame(),
                                           fig_loc,fig_kde,fig_vel,fig_mov,dr)
            st.download_button("⬇️ Download PDF",pdf_b,f"{selected}_pitching.pdf",
                               "application/pdf",key="dl_pdf_pitch")
    with ec2:
        csv_dl(pf,f"{selected}_raw.csv","⬇️ Raw CSV")
    for f in [fig_loc,fig_kde,fig_vel,fig_mov]: plt.close(f)

# ══════════════════════════════════════════════════════════════════════════════
# RENDER: HITTING
# ══════════════════════════════════════════════════════════════════════════════
def render_hitting(df, master_df, lmeta):
    st.markdown('<div class="sh">🏏 Hitting Dashboard</div>',unsafe_allow_html=True)
    st.info(f"📋 **{lmeta['label']} benchmarks** · "
            f"Hard Hit: ≥{lmeta['ev_hard']} mph · Elite EV: {lmeta['ev_elite']}+ mph · "
            f"{lmeta['barrel_note']}")
    EV_HARD  = lmeta['ev_hard']
    EV_ELITE = lmeta['ev_elite']
    if "Batter" not in df.columns or df["Batter"].dropna().empty:
        st.error("No 'Batter' column."); return
    batters=sorted(df["Batter"].dropna().unique())
    selected=player_search_select(batters,"Select Batter","batter")
    bdf=df[df["Batter"]==selected].copy(); n=len(bdf)
    if n<15: st.warning(f"⚠️ **{selected}** — only **{n}** pitches (min: 15).")
    barrel_base=lmeta.get("barrel_ev",98)
    bip=batted_ball_mask(bdf); n_bip=int(bip.sum())
    avg_ev=bdf.loc[bip,"ExitSpeed"].mean() if "ExitSpeed" in bdf.columns else np.nan
    max_ev=bdf.loc[bip,"ExitSpeed"].max() if "ExitSpeed" in bdf.columns else np.nan
    avg_la=bdf.loc[bip,"Angle"].mean() if "Angle" in bdf.columns else np.nan
    hh_rate=barrel_rate=0.0
    if "ExitSpeed" in bdf.columns:
        ev_s=bdf.loc[bip,"ExitSpeed"].dropna()
        hh_rate=safe_pct(int((ev_s>=EV_HARD).sum()),max(len(ev_s),1))
    if "ExitSpeed" in bdf.columns and "Angle" in bdf.columns and n_bip:
        # v4.2: dynamic Savant barrel over batted balls (not all pitches)
        barrel_rate=safe_pct(int(barrel_mask(bdf[bip],barrel_base).sum()),n_bip)
    disc=compute_plate_discipline_batter(bdf)
    pa=count_pa(bdf); woba=compute_woba(bdf)
    c1,c2,c3,c4,c5,c6,c7=st.columns(7)
    with c1: st.metric("Pitches",f"{n:,}",delta=f"{pa} PA" if pa else None,delta_color="off")
    with c2: st.metric("Avg EV",fmt(avg_ev," mph"),delta=f"Max {max_ev:.1f}" if not (isinstance(max_ev,float) and np.isnan(max_ev)) else None)
    with c3: st.metric("Avg LA",fmt(avg_la,"°"))
    with c4: st.metric("HH %",f"{hh_rate:.1f}%")
    with c5: st.metric("Barrel %",f"{barrel_rate:.1f}%")
    with c6: st.metric("wOBA",fmt(woba,"",3))
    with c7: st.metric("Dates",str(bdf["Date"].dt.date.nunique()) if "Date" in bdf.columns else "—")
    st.markdown("<br>",unsafe_allow_html=True)
    if disc:
        st.markdown('<div class="sh">🎯 Plate Discipline</div>',unsafe_allow_html=True)
        bcols=st.columns(len(disc))
        for col,(k,v) in zip(bcols,disc.items()):
            with col:
                st.markdown(f'<div class="stat-badge"><div class="val">{v}%</div>'
                            f'<div class="lbl">{k}</div></div>',unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)
    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs([
        "📅 Monthly","🔄 Splits","📋 Results","🗺️ Spray","📊 Distributions","🏟️ Stadium"])
    with tab1:
        monthly_df=build_hitting_monthly(bdf,lmeta)
        if monthly_df.empty: st.info("No monthly data.")
        else:
            st.dataframe(monthly_df,use_container_width=True,hide_index=True)
            csv_dl(monthly_df,f"{selected}_monthly.csv")
        st.markdown("<br>",unsafe_allow_html=True)
        fig_roll=plot_rolling_ev(bdf,selected)
        st.pyplot(fig_roll,use_container_width=True); plt.close(fig_roll)
    with tab2:
        st.markdown('<div class="sh">vs RHP / LHP</div>',unsafe_allow_html=True)
        split_df=build_split_table(bdf,ev_hard=EV_HARD)
        if split_df.empty: st.info("PitcherThrows column required.")
        else:
            st.dataframe(split_df,use_container_width=True,hide_index=True)
            csv_dl(split_df,f"{selected}_splits.csv")
            hands=bdf["PitcherThrows"].dropna().unique() if "PitcherThrows" in bdf.columns else []
            if len(hands)>=2:
                st.markdown('<div class="sh">Spray by Pitcher Hand</div>',unsafe_allow_html=True)
                cols_h=st.columns(len(hands))
                for col_h,hand in zip(cols_h,sorted(hands)):
                    with col_h:
                        sub_h=bdf[bdf["PitcherThrows"]==hand]
                        fig_h=plot_spray_chart(sub_h,f"{selected} vs {hand}")
                        st.pyplot(fig_h,use_container_width=True); plt.close(fig_h)
    with tab3:
        st.markdown('<div class="sh">Play Results</div>',unsafe_allow_html=True)
        result_df=build_play_result_table(bdf)
        if result_df.empty: st.info("PlayResult column not found.")
        else:
            st.dataframe(result_df,use_container_width=True,hide_index=True)
            csv_dl(result_df,f"{selected}_results.csv")
    with tab4:
        cl,cr=st.columns(2)
        fig_spray=plot_spray_chart(bdf,selected)
        fig_dmg=plot_damage_zone(bdf,selected)
        with cl: st.pyplot(fig_spray,use_container_width=True)
        with cr: st.pyplot(fig_dmg,use_container_width=True)
    with tab5:
        cl2,cr2=st.columns(2)
        fig_ev=plot_ev_distribution(bdf,selected)
        fig_la=plot_la_distribution(bdf,selected)
        with cl2: st.pyplot(fig_ev,use_container_width=True)
        with cr2: st.pyplot(fig_la,use_container_width=True)
        st.markdown("<br>",unsafe_allow_html=True)
        fig_ev_la=plot_ev_la_scatter(bdf,selected)
        st.pyplot(fig_ev_la,use_container_width=True)
    with tab6:
        st.info("Stadium analysis coming soon.")
    st.markdown('<div class="sh">📤 Export</div>',unsafe_allow_html=True)
    dr=f"{df['Date'].min().date()}→{df['Date'].max().date()}" if df["Date"].notna().any() else "All dates"
    ec1,ec2=st.columns(2)
    with ec1:
        # v4.2: PDF built only on demand — avoids regenerating on every rerun
        if st.button("📄 Build PDF Report",key="btn_pdf_hit"):
            with st.spinner("Building PDF…"):
                pdf_b=export_hitting_pdf(selected,monthly_df,disc,result_df,split_df,
                                          fig_spray,fig_dmg,fig_ev,fig_la,fig_ev_la,dr)
            st.download_button("⬇️ Download PDF",pdf_b,f"{selected}_hitting.pdf",
                               "application/pdf",key="dl_pdf_hit")
    with ec2:
        csv_dl(bdf,f"{selected}_raw.csv","⬇️ Raw CSV")
    for f in [fig_spray,fig_dmg,fig_ev,fig_la,fig_ev_la]: plt.close(f)

# ══════════════════════════════════════════════════════════════════════════════
# RENDER: LEAGUE & STADIUM
# ══════════════════════════════════════════════════════════════════════════════
def render_league(df, lmeta):
    st.markdown('<div class="sh">📊 League & Stadium</div>',unsafe_allow_html=True)
    st.info(f"📋 **{lmeta['label']} benchmarks** · {lmeta['context']}")
    tab_l1,tab_l2=st.tabs(["📈 League Averages","🏟️ Stadium Comparison"])
    with tab_l1:
        c1,c2=st.columns(2)
        with c1:
            st.markdown('<div class="sh">⚾ Pitching</div>',unsafe_allow_html=True)
            lp=build_league_pitching_avg(df)
            if lp.empty: st.info("Insufficient data.")
            else:
                st.dataframe(lp,use_container_width=True,hide_index=True)
                csv_dl(lp,"league_pitching.csv")
        with c2:
            st.markdown('<div class="sh">🏏 Hitting</div>',unsafe_allow_html=True)
            lh=build_league_hitting_avg(df,lmeta)
            if lh.empty: st.info("Insufficient data.")
            else:
                st.dataframe(lh,use_container_width=True,hide_index=True)
                csv_dl(lh,"league_hitting.csv")
    with tab_l2:
        if "Stadium" not in df.columns:
            st.info("No 'Stadium' column found.")
        else:
            st.info("Stadium comparison coming soon.")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown("""
    <div class="hero">
      <div class="hero-icon">⚾</div>
      <div>
        <div class="hero-title">Trackman <span class="hl">Analytics</span>
          <span style="font-size:.9rem;opacity:.35;font-weight:400"> v4.2 (Savant)</span></div>
        <div class="hero-sub">
          Professional baseball analytics with Baseball Savant–inspired design
        </div>
        <div class="hero-pills">
          <span class="pill">🔍 Player Search</span><span class="pill">📊 League Avg</span>
          <span class="pill">🔄 RHP / LHP</span><span class="pill">🎯 Play Results</span>
          <span class="pill">📈 Hit Quality</span><span class="pill">PDF Export</span>
          <span class="pill">🔥 Top Plays</span><span class="pill">🏆 Torneos en vivo</span>
        </div>
      </div>
    </div>
    """,unsafe_allow_html=True)

    st.sidebar.markdown('<span class="sb-label">📂 Data</span>',unsafe_allow_html=True)
    import hashlib, os, glob
    source=st.sidebar.radio("src",["⬆️ Upload CSVs","🏆 Tournament Folder"],
                            horizontal=True,key="data_source",label_visibility="collapsed")
    tournament=""
    if source=="⬆️ Upload CSVs":
        uploaded=st.sidebar.file_uploader("Upload Trackman CSV",type=["csv"],
                                          accept_multiple_files=True)
        if not uploaded:
            st.markdown("""
            <div style="border:2px dashed #d0d0d0;border-radius:8px;padding:60px 36px;
              text-align:center;margin-top:24px">
              <div style="font-size:2.8rem;margin-bottom:10px">📂</div>
              <div style="font-size:1.2rem;font-weight:700;margin-bottom:8px">
                Upload your Trackman CSVs to begin</div>
              <div style="font-size:.88rem;opacity:.55;line-height:1.6">
                Supports one or multiple files · Pro and amateur data welcome<br>
                Or switch to 🏆 Tournament Folder to watch a live folder
              </div>
            </div>""",unsafe_allow_html=True)
            return
        # ── Cache-busting: hash actual file contents so swapping a file always re-parses ──
        file_bytes=[f.read() for f in uploaded]
        file_names=[f.name for f in uploaded]
        cache_key=hashlib.md5(b"".join(file_bytes)).hexdigest()
        n_files=len(uploaded)
    else:
        # ── v4.2 Tournament folders: point the app at a folder on this computer.
        #    Each subfolder = a tournament. The cache key includes each file's
        #    modification time, so editing/adding a CSV updates the app on the
        #    next interaction — no manual cache clearing needed.
        base=st.sidebar.text_input("Carpeta base de torneos",
                                   placeholder="/Users/tu-usuario/Torneos",
                                   key="tm_base_path")
        if not base or not os.path.isdir(os.path.expanduser(base)):
            st.markdown("""
            <div style="border:2px dashed #d0d0d0;border-radius:8px;padding:60px 36px;
              text-align:center;margin-top:24px">
              <div style="font-size:2.8rem;margin-bottom:10px">🏆</div>
              <div style="font-size:1.2rem;font-weight:700;margin-bottom:8px">
                Escribe la ruta de tu carpeta de torneos</div>
              <div style="font-size:.88rem;opacity:.55;line-height:1.6">
                Cada subcarpeta es un torneo con sus CSVs de Trackman<br>
                Si actualizas un archivo, el app se refresca automáticamente
              </div>
            </div>""",unsafe_allow_html=True)
            return
        base=os.path.expanduser(base)
        subdirs=sorted(d for d in os.listdir(base)
                       if os.path.isdir(os.path.join(base,d)) and not d.startswith("."))
        options=["📂 Toda la carpeta"]+subdirs
        choice=st.sidebar.selectbox("🏆 Torneo",options,key="tm_tournament")
        folder=base if choice==options[0] else os.path.join(base,choice)
        tournament="" if choice==options[0] else choice
        paths=sorted(glob.glob(os.path.join(folder,"**","*.csv"),recursive=True))
        if not paths:
            st.warning(f"⚠️ No se encontraron CSVs en **{folder}**."); return
        sig="|".join(f"{p}:{os.path.getmtime(p)}:{os.path.getsize(p)}" for p in paths)
        cache_key=hashlib.md5(sig.encode()).hexdigest()
        file_bytes=[]; file_names=[]
        for p in paths:
            try:
                with open(p,"rb") as fh: file_bytes.append(fh.read())
                file_names.append(os.path.basename(p))
            except OSError as e:
                st.sidebar.warning(f"No pude leer {os.path.basename(p)}: {e}")
        n_files=len(file_names)
        st.sidebar.caption(f"🏆 **{choice}** · {n_files} CSV(s) · "
                           f"se actualiza solo al cambiar archivos")
        if st.sidebar.button("🔄 Re-escanear carpeta"): st.rerun()

    # ── Play level selector ───────────────────────────────────────────────────────────
    st.sidebar.markdown('<span class="sb-label">🏟️ Play Level</span>',unsafe_allow_html=True)
    level=st.sidebar.radio(
        "level_radio",
        ["⚾ Professional","🎓 Amateur / College","🏫 High School","🔀 Mixed"],
        key="play_level", label_visibility="collapsed"
    )
    LEVEL_META={
        "⚾ Professional":{
            "label":"Professional",
            "ev_elite":110, "ev_hard":95, "ev_avg":89, "barrel_ev":98,
            "velo_elite":97, "velo_avg":93,
            "barrel_note":"MLB barrel zone: ≥98 mph EV, 8°–32° LA",
            "zone_note":"MLB zone width ≈ 17 in (±0.71 ft)",
            "context":"Benchmarks calibrated to MLB / MiLB averages.",
        },
        "🎓 Amateur / College":{
            "label":"College / JUCO",
            "ev_elite":103, "ev_hard":90, "ev_avg":83, "barrel_ev":92,
            "velo_elite":92, "velo_avg":86,
            "barrel_note":"College barrel zone: ≥92 mph EV, 8°–32° LA",
            "zone_note":"NCAA zone similar to MLB",
            "context":"Benchmarks calibrated to NCAA D1/D2/JUCO averages.",
        },
        "🏫 High School":{
            "label":"High School",
            "ev_elite":95,  "ev_hard":83, "ev_avg":75, "barrel_ev":85,
            "velo_elite":85,"velo_avg":77,
            "barrel_note":"HS barrel zone: ≥85 mph EV, 8°–32° LA",
            "zone_note":"Same strike zone dimensions",
            "context":"Benchmarks calibrated to high-school averages.",
        },
        "🔀 Mixed":{
            "label":"Mixed levels",
            "ev_elite":105, "ev_hard":92, "ev_avg":85, "barrel_ev":95,
            "velo_elite":93,"velo_avg":87,
            "barrel_note":"Barrel zone: ≥95 mph EV, 8°–32° LA (blended)",
            "zone_note":"Standard strike zone",
            "context":"Dataset contains multiple levels — use stadium context to compare.",
        },
    }
    lmeta=LEVEL_META[level]
    # Show a small context badge in sidebar
    st.sidebar.markdown(
        f'<div style="border:1px solid #e0e0e0;border-left:3px solid #1f77b4;'
        f'border-radius:4px;padding:7px 10px;font-size:.74rem;margin-top:4px;line-height:1.5">'
        f'<b>{lmeta["label"]}</b><br>'
        f'<span style="opacity:.65">{lmeta["context"]}</span><br>'
        f'<span style="opacity:.55;font-size:.68rem">{lmeta["barrel_note"]}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    with st.spinner("Loading and parsing data…"):
        master,pa,ba=load_and_clean(tuple(file_bytes),tuple(file_names),cache_key)

    if master.empty:
        st.error("❌ No valid data could be read from the uploaded files."); return

    # Stamp level metadata onto master so downstream functions can use it
    master.attrs["level_meta"]=lmeta

    st.sidebar.success(f"✅ **{len(master):,}** pitches · {n_files} file(s)")
    if pa+ba>0:
        st.sidebar.caption(f"🔗 Merged **{pa+ba}** name variants ({pa} P · {ba} B)")

    # Clear cache button — lets analyst swap files without stale data
    if st.sidebar.button("🔄 Clear Cache & Reload", help="Force re-parse all uploaded files"):
        st.cache_data.clear()
        st.rerun()

    filtered=sidebar_date_filter(master)
    if filtered.empty: st.warning("⚠️ No data for selected dates."); return
    filtered=advanced_filters(filtered)
    if filtered.empty: st.warning("⚠️ No data after filters."); return

    st.sidebar.markdown('<span class="sb-label">🎯 Mode</span>',unsafe_allow_html=True)
    mode=st.sidebar.radio("m",["⚾ Pitching","🏏 Hitting","📊 League","🔥 Top Plays"],
                          key="dash_mode",label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("v4.2 (Savant Edition) · Streamlit · Pandas · Matplotlib")

    if mode=="⚾ Pitching": render_pitching(filtered,master,lmeta)
    elif mode=="🏏 Hitting": render_hitting(filtered,master,lmeta)
    elif mode=="🔥 Top Plays": render_top_plays(filtered,lmeta,tournament)
    else: render_league(filtered,lmeta)

if __name__=="__main__":
    main()