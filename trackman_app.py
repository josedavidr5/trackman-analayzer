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

from core.metrics import (
    STATCAST_PITCH_COLORS, PITCH_PALETTE, pitch_color, safe_pct,
    TERMINAL_RESULTS, SWING_CALLS, CONTACT_CALLS,
    ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP, WOBA_W,
    count_pa, in_zone_mask, batted_ball_mask, barrel_mask, count_k_bb, compute_woba,
)
from core.pitching import (build_usage_by_count, arsenal_stuff, movement_points,
                           whiff_csw_zone_grid)
from core.pitching import pitch_summary as build_pitch_summary
from core.pitching import pitch_discipline as compute_pitch_discipline
from viz import pitching as vpitch

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

# Gradiente de percentiles Savant: azul (bajo) → gris (50) → rojo (alto)
_PCT_CMAP=matplotlib.colors.LinearSegmentedColormap.from_list(
    "savant_pct", ["#325AA1","#9E9E9E","#D82129"])
def pct_color(p): return _PCT_CMAP(max(0.0, min(float(p), 100.0))/100.0)

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
    # v4.4 aliases del módulo de trayectorias (schema del spec → nombres TrackMan)
    "RelHeight":      ["ReleaseHeight","RelZ"],
    "RelSide":        ["ReleaseSide","RelX"],
    "RelSpeed":       ["ReleaseSpeed","PitchSpeed"],
    "PitchUID":       ["PitchUid","PitchID","GUID"],
    "PitcherId":      ["pitcher_id","PitcherID"],
    "BatterId":       ["batter_id","BatterID"],
    "x0":["X0"],"y0":["Y0"],"z0":["Z0"],
    "vx0":["Vx0","VX0"],"vy0":["Vy0","VY0"],"vz0":["Vz0","VZ0"],
    "ax0":["ax","Ax0","AX0"],"ay0":["ay","Ay0","AY0"],"az0":["az","Az0","AZ0"],
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
NUMERIC_COLS=["RelSpeed","SpinRate","InducedVertBreak","HorzBreak","VertBreak",
              "PlateLocSide","PlateLocHeight","ExitSpeed","Angle","Distance",
              "Bearing","RelHeight","RelSide","Extension","SpinAxis",
              "VertApprAngle","HorzApprAngle","Balls","Strikes","Inning",
              # v4.4 paquete kinemático 9P para el módulo de trayectorias
              "x0","y0","z0","vx0","vy0","vz0","ax0","ay0","az0"]

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

def draw_savant_zone(ax, alpha=0.8, shadow=True):
    """Zona de strike estilo Savant: rectángulo oscuro fino + zona de sombra."""
    zone = patches.Rectangle((-0.71, 1.5), 1.42, 2.0,
        lw=1.8, edgecolor="#333333", facecolor='none', alpha=alpha, zorder=5)
    ax.add_patch(zone)
    for i in range(1, 3):
        ax.plot([-0.71+i*0.4733]*2, [1.5, 3.5], color="#333333",
                lw=0.6, alpha=alpha*0.35, zorder=4)
    for j in range(1, 3):
        ax.plot([-0.71, 0.71], [1.5+j*2.0/3]*2, color="#333333",
                lw=0.6, alpha=alpha*0.35, zorder=4)
    if shadow:  # zona de sombra (una pelota alrededor del borde)
        ax.add_patch(patches.Rectangle((-0.95, 1.26), 1.9, 2.48,
            lw=1.0, edgecolor="#aaaaaa", facecolor="none",
            linestyle=(0,(4,3)), alpha=alpha*0.7, zorder=4))


def _smooth_hist2d(x, y, xlim=(-2.0,2.0), zlim=(0.4,4.6), bins=46, sigma=2.6):
    """Histograma 2D suavizado con kernel gaussiano (sin dependencias extra)."""
    H,_,_=np.histogram2d(np.asarray(x),np.asarray(y),bins=bins,
                         range=[list(xlim),list(zlim)])
    k=np.exp(-0.5*(np.arange(-8,9)/sigma)**2); k/=k.sum()
    H=np.apply_along_axis(lambda m: np.convolve(m,k,mode="same"),0,H)
    H=np.apply_along_axis(lambda m: np.convolve(m,k,mode="same"),1,H)
    return H/H.max() if H.max()>0 else H


def zone_heatmap_ax(ax, x, y, base_color="#D22D49", thresh=0.07,
                    xlim=(-2.0,2.0), zlim=(0.4,4.6), show_dots=True):
    """
    Heatmap de ubicación estilo Savant: blanco → color solo donde hay pitches
    (nada de arcoíris que inunda el fondo), con puntos discretos encima.
    """
    br,bg,bb,_=matplotlib.colors.to_rgba(base_color)
    cmap=matplotlib.colors.LinearSegmentedColormap.from_list("zh",
        [(1,1,1,0.0),(br,bg,bb,0.28),(br,bg,bb,0.62),(br,bg,bb,0.92)])
    H=_smooth_hist2d(x,y,xlim=xlim,zlim=zlim)
    masked=np.ma.masked_less(H.T,thresh)
    ax.imshow(masked,origin="lower",extent=[xlim[0],xlim[1],zlim[0],zlim[1]],
              cmap=cmap,vmin=thresh,vmax=1.0,interpolation="bilinear",
              aspect="auto",zorder=2)
    if show_dots:
        ax.scatter(x,y,s=13,color="#333333",alpha=0.45,
                   edgecolors="white",linewidths=0.3,zorder=6)


def style_zone_ax(ax, xlim=(-2.0,2.0), zlim=(0.4,4.6)):
    """Ejes minimalistas para gráficas de zona: sin ticks, sin grid, con plato."""
    ax.grid(False)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_xlim(*xlim); ax.set_ylim(*zlim)
    ax.set_aspect("equal",adjustable="box")

def draw_plate(ax):
    """Draw home plate."""
    ax.fill([-0.71,-0.71,0,0.71,0.71],[0.35,0.15,0,0.15,0.35],
            color=SAVANT_GREY, alpha=0.15, zorder=2)

def csv_dl(df, fname, label="⬇️ Download CSV"):
    st.download_button(label, df.to_csv(index=False).encode(), fname, "text/csv")
def fmt(v, suffix="", decimals=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    return f"{v:.{decimals}f}{suffix}"

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

def _tokens(n): return frozenset(t for t in n.lower().split() if len(t)>=1)

from difflib import SequenceMatcher
def _sim(a,b): return SequenceMatcher(None,a,b).ratio()

def _token_match(tk, others):
    """Un token empata si: inicial→prefijo; corto→exacto; largo→ratio ≥0.78."""
    if len(tk)==1:
        return any(o.startswith(tk) for o in others)
    if len(tk)<=3:
        return tk in others
    return max((_sim(tk,o) for o in others),default=0.0)>=0.78

def _names_similar(n1,n2,t1,t2):
    """
    v4.7 — matching difuso para variantes del mismo jugador:
      · solapamiento de tokens (Jaccard ≥0.60): 'Jose Perez' ~ 'Perez Jose'
      · similitud global ≥0.87: 'Jose Peres' ~ 'Jose Perez' (typos)
      · todos los tokens del nombre corto empatan difuso en el largo:
        'J Perez' ~ 'Jose Perez' (iniciales), 'Jose Peres' ~ 'Jose Perez Jr'
    Los acentos ya vienen normalizados desde normalize_name().
    """
    big1={t for t in t1 if len(t)>=2}; big2={t for t in t2 if len(t)>=2}
    if big1 and big2 and len(big1&big2)/len(big1|big2)>=0.60: return True
    if _sim(n1.lower(),n2.lower())>=0.87: return True
    if not t1 or not t2: return False
    # simétrico: basta con que TODOS los tokens de un nombre empaten en el otro
    # (la dirección corta→larga es la que captura 'J Perez' → 'Jose Perez')
    return (all(_token_match(tk,t2) for tk in t1)
            or all(_token_match(tk,t1) for tk in t2))

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
            if _names_similar(unique[i],unique[j],tsets[i],tsets[j]): union(i,j)
    clusters=defaultdict(list)
    for idx,name in enumerate(unique): clusters[find(idx)].append(name)
    mapping={}
    for members in clusters.values():
        # canónico: el más frecuente; empate → el más largo; empate → alfabético
        canonical=max(members,key=lambda nm:(counts[nm],len(nm),nm))
        for m in members: mapping[m]=canonical
    return mapping

def dedup_col(df,col):
    """Normaliza + unifica variantes. Devuelve (df, n_alias, mapping).
    Conserva el nombre normalizado original en {col}Orig para poder revisar
    y corregir unificaciones manualmente sin recargar los archivos."""
    if col not in df.columns: return df,0,{}
    df[col]=df[col].astype(str).apply(normalize_name)
    df[f"{col}Orig"]=df[col]
    valid=df[col].dropna(); valid=valid[valid!="nan"]
    if valid.empty: return df,0,{}
    mapping=find_clusters(valid.tolist())
    aliases=sum(1 for k,v in mapping.items() if k!=v)
    df[col]=df[col].map(mapping).fillna(df[col])
    return df,aliases,{k:v for k,v in mapping.items() if k!=v}

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
    df,pa,pmap=dedup_col(df,"Pitcher")
    df,ba,bmap=dedup_col(df,"Batter")
    return df,pa,ba,{"Pitcher":pmap,"Batter":bmap}

# ══════════════════════════════════════════════════════════════════════════════
# PERCENTILE RANKINGS estilo Savant — v4.5
#   Barras azul→gris→rojo con el percentil del jugador vs la liga cargada,
#   más un tick de benchmark editable por el usuario.
# ══════════════════════════════════════════════════════════════════════════════
def _pctl_of(series, v, invert=False):
    s=pd.Series(series).dropna().astype(float)
    if len(s)<2 or v is None: return None
    try: v=float(v)
    except (TypeError,ValueError): return None
    if np.isnan(v): return None
    p=100.0*((s<v).sum()+0.5*(s==v).sum())/len(s)
    return round(100.0-p if invert else p)

def league_batter_table(df, lmeta, min_pitches=15):
    """Una fila por bateador con las métricas clave (distribución de la liga)."""
    rows={}
    for b,g in df.groupby("Batter"):
        if len(g)<min_pitches: continue
        bip=batted_ball_mask(g)
        ev=g.loc[bip,"ExitSpeed"].dropna() if "ExitSpeed" in g.columns else pd.Series(dtype=float)
        disc=compute_plate_discipline_batter(g)
        n_bip=max(int(bip.sum()),1)
        rows[b]={
            "Avg EV":round(ev.mean(),1) if len(ev) else np.nan,
            "Max EV":round(ev.max(),1) if len(ev) else np.nan,
            "Hard Hit %":safe_pct(int((ev>=lmeta.get("ev_hard",95)).sum()),max(len(ev),1)),
            "Barrel %":safe_pct(int(barrel_mask(g[bip],lmeta.get("barrel_ev",98)).sum()),n_bip),
            "K %":disc.get("K %",np.nan),"BB %":disc.get("BB %",np.nan),
            "Chase %":disc.get("Chase %",np.nan),"Whiff %":disc.get("Whiff %",np.nan),
            "wOBA":compute_woba(g)}
    return pd.DataFrame(rows).T

def league_pitcher_table(df, min_pitches=15):
    rows={}
    for p,g in df.groupby("Pitcher"):
        if len(g)<min_pitches: continue
        velo=g["RelSpeed"].dropna() if "RelSpeed" in g.columns else pd.Series(dtype=float)
        spin=g["SpinRate"].dropna() if "SpinRate" in g.columns else pd.Series(dtype=float)
        disc=compute_plate_discipline_batter(g)   # mismas fórmulas, lectura de pitcher
        rows[p]={
            "Avg Velo":round(velo.mean(),1) if len(velo) else np.nan,
            "Max Velo":round(velo.max(),1) if len(velo) else np.nan,
            "Avg Spin":round(spin.mean(),0) if len(spin) else np.nan,
            "Zone %":disc.get("Zone %",np.nan),
            "Whiff %":disc.get("Whiff %",np.nan),"Chase %":disc.get("Chase %",np.nan),
            "K %":disc.get("K %",np.nan),"BB %":disc.get("BB %",np.nan)}
    return pd.DataFrame(rows).T

# métricas donde MENOS es MEJOR (se invierte el percentil, como hace Savant)
HITTER_INVERT={"K %","Chase %","Whiff %"}
PITCHER_INVERT={"BB %"}

def savant_percentile_fig(rows, title, subtitle=""):
    """rows: [(label, value_str, pct 0..100 | None, bench_pct | None)]"""
    n=len(rows)
    fig,ax=setup_savant_fig((8.4, 0.56*n+1.3))
    ax.axis("off"); ax.grid(False)
    x0,x1=3.55,9.55
    for i,(lbl,val,pct,bp) in enumerate(rows):
        y=n-1-i
        ax.text(0.02,y,lbl,ha="left",va="center",fontsize=10.5,
                fontweight="bold",color=SAVANT_TEXT)
        ax.text(3.25,y,val,ha="right",va="center",fontsize=10,color="#777")
        ax.plot([x0,x1],[y,y],color="#e6e6e6",lw=8,solid_capstyle="round",zorder=2)
        if bp is not None:
            xb=x0+(x1-x0)*bp/100.0
            ax.plot([xb,xb],[y-0.30,y+0.30],color="#444",lw=1.6,zorder=3)
            ax.plot([xb],[y+0.36],marker="v",ms=4,color="#444",zorder=3)
        if pct is not None:
            xp=x0+(x1-x0)*pct/100.0
            ax.scatter([xp],[y],s=470,color=pct_color(pct),zorder=4,
                       edgecolors="white",linewidths=1.6)
            ax.text(xp,y,f"{pct:.0f}",ha="center",va="center",fontsize=10,
                    fontweight="bold",color="white",zorder=5)
        else:
            ax.text((x0+x1)/2,y,"sin datos suficientes",ha="center",va="center",
                    fontsize=8,color="#bbb",zorder=3)
    ax.text(x0,n+0.05,"◀ Percentil 0",fontsize=7.5,color="#999")
    ax.text(x1,n+0.05,"100 ▶",fontsize=7.5,color="#999",ha="right")
    ax.set_xlim(-0.1,9.9); ax.set_ylim(-0.7,n+0.55)
    savant_title(ax,title,subtitle)
    return fig

def benchmark_editor(defaults, key, note=""):
    """Benchmarks editables por el usuario, persistentes en la sesión."""
    saved=st.session_state.get(f"bmk_{key}",{})
    base={k:saved.get(k,v) for k,v in defaults.items()}
    with st.expander("⚙️ Benchmarks editables (marca ▼ en las barras)"):
        st.caption(note or "Define el valor objetivo de cada métrica — por ejemplo, "
                   "los estándares de reclutamiento college que ustedes manejen.")
        ed=st.data_editor(pd.DataFrame({"Métrica":list(base.keys()),
                                        "Benchmark":list(base.values())}),
                          hide_index=True,use_container_width=True,
                          key=f"bmked_{key}",disabled=["Métrica"])
        out={}
        for rec in ed.to_dict("records"):
            try:
                v=float(rec["Benchmark"])
                if not np.isnan(v): out[rec["Métrica"]]=v
            except (TypeError,ValueError): continue
        st.session_state[f"bmk_{key}"]=out
    return out

def render_percentile_section(player, league_df, invert_set, defaults, key, min_players=5):
    st.markdown('<div class="sh">📊 Percentile Rankings · estilo Savant</div>',
                unsafe_allow_html=True)
    if league_df.empty or player not in league_df.index or len(league_df)<min_players:
        st.info(f"Se necesitan ≥{min_players} jugadores con muestra suficiente en el "
                "dataset cargado para calcular percentiles de liga.")
        return
    bmk=benchmark_editor(defaults,key)
    rows=[]
    for m in league_df.columns:
        col=league_df[m]; v=league_df.loc[player,m]
        inv=m in invert_set
        pct=_pctl_of(col,v,invert=inv)
        bp=_pctl_of(col,bmk.get(m),invert=inv) if m in bmk else None
        val="—" if (v is None or (isinstance(v,float) and np.isnan(v))) else (
            f"{v:.3f}" if m=="wOBA" else f"{v:.1f}")
        rows.append((m,val,pct,bp))
    fig=savant_percentile_fig(rows,f"{player}",
        f"percentil vs {len(league_df)} jugadores del dataset · ▼ = benchmark")
    st.pyplot(fig,use_container_width=True); plt.close(fig)
    st.caption("🔴 alto = mejor · 🔵 bajo = peor · en K%, Chase% y Whiff% el percentil "
               "ya está invertido (percentil alto = menos strikeouts/chases).")

# ══════════════════════════════════════════════════════════════════════════════
# CLOUD PROFILES (Supabase Storage) — v4.3
#   Shared profiles: any app user can open a profile, see everyone's uploads,
#   and add their own CSVs. Works on Streamlit Cloud and locally.
#   The publishable key below is safe to embed (client-side key, RLS enforced:
#   read + CSV-upload only, no deletes/overwrites).
# ══════════════════════════════════════════════════════════════════════════════
SB_URL_DEFAULT="https://wnhqghlnmnoefdxgserl.supabase.co"
SB_KEY_DEFAULT="sb_publishable_0xJjnG1x8Qyw7JCyA0mAEw_5SWfIVXI"
SB_BUCKET="perfiles"

def get_supabase():
    try:
        from supabase import create_client
    except ImportError:
        st.error("Falta el paquete **supabase**. Agrega `supabase` a requirements.txt "
                 "(o `pip install supabase`).")
        return None
    try: url=st.secrets.get("SUPABASE_URL",SB_URL_DEFAULT)
    except Exception: url=SB_URL_DEFAULT
    try: key=st.secrets.get("SUPABASE_KEY",SB_KEY_DEFAULT)
    except Exception: key=SB_KEY_DEFAULT
    try:
        return create_client(url,key)
    except Exception as e:
        st.error(f"No pude conectar a Supabase: {e}")
        return None

def sb_list(sb, path=""):
    try:
        return sb.storage.from_(SB_BUCKET).list(path,{"limit":1000}) or []
    except Exception as e:
        st.warning(f"Error listando '{path}': {e}"); return []

def sb_list_profiles(sb):
    return sorted(e["name"] for e in sb_list(sb,"")
                  if e.get("id") is None and not e["name"].startswith("."))

def sb_walk_csvs(sb, prefix, _depth=0):
    """Recursively list CSVs under a profile: [(path, updated_at, size), …]."""
    if _depth>4: return []
    out=[]
    for e in sb_list(sb,prefix):
        name=e.get("name","")
        full=f"{prefix}/{name}" if prefix else name
        if e.get("id") is None:
            out+=sb_walk_csvs(sb,full,_depth+1)
        elif name.lower().endswith(".csv"):
            meta=e.get("metadata") or {}
            out.append((full,str(e.get("updated_at") or ""),int(meta.get("size") or 0)))
    return out

@st.cache_data(show_spinner=False)
def sb_download_all(_sb, _paths, cache_sig):
    """Download all CSVs of a profile; re-runs only when cache_sig changes
    (any added/updated file changes the signature → instant refresh)."""
    blobs=[]; names=[]
    for p in _paths:
        try:
            blobs.append(_sb.storage.from_(SB_BUCKET).download(p))
            names.append(p.split("/")[-1])
        except Exception as e:
            st.warning(f"No pude descargar {p}: {e}")
    return blobs,names

def sb_upload_files(sb, profile, files, existing_paths):
    """Upload user CSVs into a profile. Never overwrites: auto-suffixes duplicates."""
    ok=0
    existing={p.split("/")[-1] for p in existing_paths}
    for f in files:
        fname=re.sub(r"[^A-Za-z0-9 ._()-]","",f.name).strip() or "archivo.csv"
        if fname in existing:
            stem,ext=fname.rsplit(".",1)
            fname=f"{stem}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        try:
            sb.storage.from_(SB_BUCKET).upload(f"{profile}/{fname}",f.getvalue(),
                                               {"content-type":"text/csv"})
            ok+=1
        except Exception as e:
            st.sidebar.error(f"Error subiendo {fname}: {e}")
    return ok

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
    # ── v4.6 Campo minimalista estilo Savant: línea fina, fondo blanco ────
    ax.grid(False)
    LINE="#c9c9c9"
    fence_t=np.linspace(-45,45,200)
    fence_r=330+70*np.cos(np.deg2rad(fence_t*2))          # 330 líneas · 400 center
    fx=fence_r*np.sin(np.deg2rad(fence_t)); fy=fence_r*np.cos(np.deg2rad(fence_t))
    # tinte de pasto casi imperceptible
    ax.fill(np.concatenate([[0],fx,[0]]),np.concatenate([[0],fy,[0]]),
            color="#f4f8f2",zorder=0)
    # barda + líneas de foul (trazo fino gris)
    ax.plot(fx,fy,color=LINE,lw=1.8,zorder=1,solid_capstyle="round")
    for sgn in (1,-1):
        ax.plot([0,sgn*330*np.sin(np.deg2rad(45))],[0,330*np.cos(np.deg2rad(45))],
                color=LINE,lw=1.4,zorder=1)
    # diamante del infield + arco de tierra (solo contorno)
    d=63.64
    ax.plot([0,d,0,-d,0],[0,d,2*d,d,0],color=LINE,lw=1.2,zorder=1)
    inf_t=np.linspace(-45,45,80)
    ax.plot(95*np.sin(np.deg2rad(inf_t)),95*np.cos(np.deg2rad(inf_t)),
            color="#e2e2e2",lw=1.0,zorder=1)
    for bx,by in [(d,d),(0,2*d),(-d,d)]:
        ax.add_patch(patches.Rectangle((bx-3,by-3),6,6,angle=45,
                     facecolor="white",edgecolor=LINE,lw=0.9,zorder=2))
    ax.add_patch(patches.Circle((0,60.5),9,facecolor="white",
                 edgecolor="#e2e2e2",lw=1.0,zorder=1))
    ax.add_patch(patches.Polygon([(-3.5,0),(3.5,0),(3.5,-3.5),(0,-7),(-3.5,-3.5)],
                 closed=True,facecolor="white",ec=LINE,lw=0.9,zorder=2))
    # referencia única de distancia al CF
    ax.text(0,404,"400 ft",fontsize=7.5,color="#b5b5b5",ha="center",zorder=1)
    has_ev="ExitSpeed" in spray.columns and spray["ExitSpeed"].notna().any()
    sc=ax.scatter(spray["Hit_X"],spray["Hit_Y"],
                  c=spray["ExitSpeed"] if has_ev else SAVANT_BLUE,
                  cmap="coolwarm" if has_ev else None,
                  s=48, alpha=0.85, edgecolors="white", linewidths=0.6,
                  zorder=6, vmin=65, vmax=112, rasterized=True)
    if has_ev:
        cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.62)
        cb.set_label("Exit Velocity (mph)", fontsize=8, color=SAVANT_TEXT)
        cb.ax.tick_params(labelsize=8); cb.outline.set_visible(False)
    ax.set_xlim(-340,340); ax.set_ylim(-25,430)
    ax.axis("off")
    savant_title(ax,"Spray Chart",name)
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
        sc=ax.scatter(loc["PlateLocSide"],loc["PlateLocHeight"],
                      c=loc["ExitSpeed"] if has_ev else SAVANT_ACCENT,
                      cmap="coolwarm" if has_ev else None,
                      s=52,alpha=0.85,edgecolors="white",
                      linewidths=0.7,zorder=6,vmin=65,vmax=112)
        if has_ev:
            cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.62)
            cb.set_label("Exit Velocity (mph)", fontsize=8, color=SAVANT_TEXT)
            cb.ax.tick_params(labelsize=8); cb.outline.set_visible(False)
    else:
        ax.text(.5,.5,"No location data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
    draw_savant_zone(ax); draw_plate(ax)
    style_zone_ax(ax)
    savant_title(ax,"Damage Zone",f"{name} · dónde le pegan más duro")
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

# ══════════════════════════════════════════════════════════════════════════════
# NEW ANALYTICS v4.2 — usage by count, rolling EV, per-pitch heatmaps
# ══════════════════════════════════════════════════════════════════════════════
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

METRIC_META={
    "ev":    {"fn":top_hardest_hits,"player_col":"Batter","value_col":"ExitSpeed",
              "unit":"mph","title":"BATAZOS MÁS FUERTES","accent":"#ff4d4d"},
    "hr":    {"fn":top_longest_hrs,"player_col":"Batter","value_col":"Distance",
              "unit":"ft","title":"HOME RUNS MÁS LARGOS","accent":"#ffb347"},
    "velo":  {"fn":top_fastest_pitches,"player_col":"Pitcher","value_col":"RelSpeed",
              "unit":"mph","title":"LANZAMIENTOS MÁS RÁPIDOS","accent":"#4da6ff"},
    "spin":  {"fn":top_spin_pitches,"player_col":"Pitcher","value_col":"SpinRate",
              "unit":"rpm","title":"MAYOR SPIN RATE","accent":"#b98aff"},
    "barrel":{"fn":top_barrels_lb,"player_col":"Batter","value_col":"ExitSpeed",
              "unit":"mph","title":"MEJORES BARRELS","accent":"#3ddc84"},
}
QUICK_QUESTIONS={
    "🔥 ¿Cuáles fueron los batazos más fuertes?":"ev",
    "🚀 ¿Cuáles fueron los HRs más largos?":"hr",
    "⚡ ¿Cuáles fueron los lanzamientos más rápidos?":"velo",
    "🌪️ ¿Quién generó más spin?":"spin",
    "🎯 ¿Cuáles fueron los mejores barrels?":"barrel",
}

def parse_question(q, stadiums=(), regions=(), players=()):
    """
    Lightweight ES/EN natural-language parser for free-text questions.
    Understands: metric, 'top N', period (hoy/semana/mes/N días), 'en cada
    región/estadio', a specific stadium/region name, and a player name.
    Returns dict or None if no metric was recognized.
    """
    s=" "+_strip_accents(str(q).lower())+" "
    toks=set(re.findall(r"[a-z0-9]+",s))
    intent=None
    if toks&{"jonron","jonrones","cuadrangular","cuadrangulares","hr","hrs","homerun","homeruns"} or "home run" in s:
        intent="hr"
    elif toks&{"barrel","barrels","barril","barriles"}: intent="barrel"
    elif toks&{"spin","rotacion","giro","rpm"}: intent="spin"
    elif toks&{"lanzamiento","lanzamientos","pitcheo","pitcheos","pitch","pitches",
               "velocidad","rapido","rapidos","rapidas","recta","rectas","mph","tiro","tiros"}:
        intent="velo"
    elif toks&{"batazo","batazos","hit","hits","exit","fuerte","fuertes","duro","duros",
               "contacto","contactos","ev","golpe","golpes"}:
        intent="ev"
    if intent is None: return None
    n=10
    m=(re.search(r"top\s*(\d+)",s) or re.search(r"(\d+)\s+mejores",s)
       or re.search(r"mejores\s+(\d+)",s) or re.search(r"primeros\s+(\d+)",s))
    if m: n=max(1,min(25,int(m.group(1))))
    days=None
    m=re.search(r"(\d+)\s*(dias|days)",s)
    if m: days=int(m.group(1))
    elif toks&{"hoy","today"}: days=1
    elif toks&{"ayer","yesterday"}: days=2
    elif toks&{"semana","semanal","week","weekly"}: days=7
    elif toks&{"quincena","fortnight"}: days=14
    elif toks&{"mes","mensual","month","monthly"}: days=30
    per_group=bool(("cada" in toks or "por" in toks)
                   and toks&{"region","regiones","estadio","estadios","zona","zonas"})
    # Most-specific match wins (e.g. "Estadio Norte" beats region "Norte")
    candidates=[]
    for stx in stadiums:
        nm=_strip_accents(str(stx).lower())
        if stx and nm in s: candidates.append((len(nm),"Stadium",stx))
    for r in regions:
        nm=_strip_accents(str(r).lower())
        if r and f" {nm} " in s.replace(",", " ").replace("?"," "):
            candidates.append((len(nm),"Region",r))
    area=None
    if candidates:
        _,col,val=max(candidates)
        area=(col,val)
    player=None
    for p in players:
        if p and _strip_accents(str(p).lower()) in s:
            player=p; break
    return {"intent":intent,"n":n,"days":days,"per_group":per_group,
            "area":area,"player":player}

def region_editor(df):
    """Stadium→Region mapping: regions.csv from tournament folder + in-app editor."""
    if "Stadium" not in df.columns: return {}
    stadiums=sorted(x for x in df["Stadium"].dropna().unique()
                    if x not in ("Unknown","Nan",""))
    if not stadiums: return {}
    csv_map=st.session_state.get("region_csv_map",{})
    saved=st.session_state.get("region_map_saved",{})
    base={s:saved.get(s,csv_map.get(s,"")) for s in stadiums}
    with st.expander("🗺️ Configurar regiones (agrupa estadios)",expanded=False):
        st.caption("Asigna una región a cada estadio para poder preguntar y filtrar por región. "
                   "También puedes poner un **regions.csv** (columnas: Stadium,Region) "
                   "en la carpeta del torneo y se carga solo.")
        edit_df=pd.DataFrame({"Stadium":stadiums,"Region":[base[s] for s in stadiums]})
        edited=st.data_editor(edit_df,hide_index=True,use_container_width=True,
                              key="region_editor",disabled=["Stadium"])
        mapping={r.Stadium:str(r.Region).strip() for r in edited.itertuples()
                 if str(r.Region).strip() not in ("","nan","None")}
        st.session_state["region_map_saved"]=mapping
        if mapping:
            csv_dl(pd.DataFrame({"Stadium":list(mapping),"Region":list(mapping.values())}),
                   "regions.csv","⬇️ Guardar regions.csv")
    return mapping

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
    # ── Regions: map stadiums → regions (regions.csv or in-app editor) ──
    region_map=region_editor(df)
    df=df.copy()
    if region_map and "Stadium" in df.columns:
        df["Region"]=df["Stadium"].map(region_map).fillna("Sin región")
    regions=sorted(df["Region"].dropna().unique()) if "Region" in df.columns else []
    stadiums=(sorted(x for x in df["Stadium"].dropna().unique() if x not in ("Unknown","Nan",""))
              if "Stadium" in df.columns else [])
    players=list(pd.unique(pd.concat([
        df["Batter"].dropna() if "Batter" in df.columns else pd.Series(dtype=str),
        df["Pitcher"].dropna() if "Pitcher" in df.columns else pd.Series(dtype=str)])))
    # ── Free-text question OR quick question ──
    free_q=st.text_input("✍️ Escribe tu pregunta",key="tp_free",
        placeholder="Ej: top 5 batazos más fuertes de la semana en Estadio Norte · "
                    "lanzamientos más rápidos en cada región")
    q_preset=st.selectbox("…o elige una pregunta rápida",list(QUICK_QUESTIONS.keys()),key="tp_q")
    parsed=None
    if free_q.strip():
        parsed=parse_question(free_q,stadiums=stadiums,regions=regions,players=players)
        if parsed is None:
            st.warning("No entendí la pregunta. Menciona una métrica: **batazos/fuertes**, "
                       "**HRs/jonrones**, **lanzamientos/velocidad**, **spin** o **barrels**. "
                       "Puedes agregar periodo (semana, mes, 10 días), 'top N', un jugador, "
                       "un estadio o una región.")
    intent=parsed["intent"] if parsed else QUICK_QUESTIONS[q_preset]
    meta=METRIC_META[intent]
    # ── Period ──
    if df["Date"].notna().any():
        max_d=df["Date"].max()
        if parsed and parsed["days"]:
            days=parsed["days"]
            dr_note=f"últimos {days} días"
        else:
            period=st.radio("Periodo",["Última semana","Últimos 14 días","Últimos 30 días","Todo"],
                            horizontal=True,key="tp_period")
            days={"Última semana":7,"Últimos 14 días":14,"Últimos 30 días":30}.get(period)
            dr_note=None
        sub=df[df["Date"]>=max_d-pd.Timedelta(days=days)] if days else df
        dr=(f"{sub['Date'].min().strftime('%b %d')} – {sub['Date'].max().strftime('%b %d, %Y')}"
            if sub["Date"].notna().any() else "Todas las fechas")
        if dr_note: st.caption(f"📆 Periodo detectado en tu pregunta: **{dr_note}** ({dr})")
    else:
        sub=df; dr="Todas las fechas"
        st.caption("Sin columna de fecha válida — mostrando todo el dataset.")
    # ── Area filter (stadium/region) — from question or manual selector ──
    area_label=""
    if parsed and parsed["area"]:
        col,val=parsed["area"]
        if col in sub.columns:
            sub=sub[sub[col]==val]; area_label=str(val)
            st.caption(f"📍 Filtrado por {('región' if col=='Region' else 'estadio')}: **{val}**")
    else:
        fc1,fc2=st.columns(2)
        with fc1:
            if regions:
                sel_r=st.multiselect("Filtrar por región",regions,key="tp_freg")
                if sel_r:
                    sub=sub[sub["Region"].isin(sel_r)]; area_label=", ".join(sel_r)
        with fc2:
            if stadiums:
                sel_s=st.multiselect("Filtrar por estadio",stadiums,key="tp_fstad")
                if sel_s:
                    sub=sub[sub["Stadium"].isin(sel_s)]
                    area_label=area_label or ", ".join(sel_s)
    # ── Player filter from question ──
    if parsed and parsed["player"]:
        pcol=meta["player_col"]
        if pcol in sub.columns:
            sub=sub[sub[pcol]==parsed["player"]]
            st.caption(f"👤 Solo jugadas de **{parsed['player']}**")
    # ── Options ──
    c2,c3=st.columns(2)
    with c2:
        topn=st.number_input("Top N",1,25,parsed["n"] if parsed else 10,key="tp_n")
    with c3:
        uniq=st.checkbox("1 por jugador",value=not (parsed and parsed["player"]),key="tp_uniq",
                         help="Muestra solo la mejor jugada de cada jugador")
    kw={"n":int(topn),"unique_player":uniq}
    if meta["fn"] is top_barrels_lb: kw["barrel_base"]=lmeta.get("barrel_ev",98)
    lb=meta["fn"](sub,**kw)
    if lb.empty:
        st.warning("No hay datos suficientes para esta pregunta con los filtros actuales.")
        return
    st.markdown(f'<div class="sh">{meta["title"]}{" · "+area_label if area_label else ""} · {dr}</div>',
                unsafe_allow_html=True)
    st.dataframe(lb,use_container_width=True)
    csv_dl(lb,"top_plays.csv")
    # ── Breakdown per region/stadium ──
    group_col="Region" if regions else "Stadium"
    if regions and stadiums:
        choice_g=st.radio("Desglosar por",["Región","Estadio"],horizontal=True,key="tp_grp")
        group_col="Region" if choice_g=="Región" else "Stadium"
    auto_open=bool(parsed and parsed["per_group"])
    if group_col in sub.columns and sub[group_col].nunique()>1:
        with st.expander(f"🏟️ Ver top en cada {'región' if group_col=='Region' else 'estadio'}",
                         expanded=auto_open):
            for area,grp in sub.groupby(group_col):
                if str(area) in ("Unknown","Nan","","Sin región"): continue
                kw_s=dict(kw); kw_s["n"]=min(int(topn),5)
                lb_s=meta["fn"](grp,**kw_s)
                if lb_s.empty: continue
                st.markdown(f"**{area}**")
                st.dataframe(lb_s,use_container_width=True)
                bc=io.BytesIO()
                fig_a=make_social_card(lb_s,meta,dr,f"{tournament+' · ' if tournament else ''}{area}")
                fig_a.savefig(bc,format="png",dpi=100,facecolor=fig_a.get_facecolor())
                plt.close(fig_a); bc.seek(0)
                st.download_button(f"⬇️ Tarjeta PNG — {area}",bc.read(),
                                   f"top_{intent}_{str(area).replace(' ','_')}.png","image/png",
                                   key=f"dl_area_{intent}_{area}")
    # ── Social card ──
    st.markdown('<div class="sh">📱 Tarjeta para redes sociales</div>',unsafe_allow_html=True)
    card_sub=dr+(f" · {area_label}" if area_label else "")
    fig_card=make_social_card(lb,meta,card_sub,tournament)
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
    # Figura Plotly → ruta por kaleido (viz.export). Si falla, se propaga la excepción
    # y el llamador (_pdf_two_charts/_pdf_single_chart) dibuja "Chart unavailable".
    try:
        import plotly.graph_objects as _go
        if isinstance(src_fig, _go.Figure):
            from viz.export import plotly_png_array
            arr = plotly_png_array(src_fig)
            if arr is None:
                raise RuntimeError("kaleido no disponible")
            return arr
    except ImportError:
        pass
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
    st.markdown('<div class="sh">⚾ Pitching Dashboard</div>', unsafe_allow_html=True)
    st.info(f"📋 **{lmeta['label']} benchmarks** · "
            f"Elite velo: {lmeta['velo_elite']}+ mph · Avg: {lmeta['velo_avg']} mph · "
            f"{lmeta['context']}")
    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column."); return
    pitchers = sorted(df["Pitcher"].dropna().unique())
    selected = player_search_select(pitchers, "Select Pitcher", "pitcher")
    pf = df[df["Pitcher"] == selected].copy(); n = len(pf)
    if n < 15:
        st.warning(f"⚠️ **{selected}** — only **{n}** pitches (min: 15).")
    avg_v = pf["RelSpeed"].mean() if "RelSpeed" in pf.columns else np.nan
    max_v = pf["RelSpeed"].max() if "RelSpeed" in pf.columns else np.nan
    avg_sp = pf["SpinRate"].mean() if "SpinRate" in pf.columns else np.nan
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Pitches", f"{n:,}")
    with c2: st.metric("Avg Velo", fmt(avg_v, " mph"),
                       delta=f"Max {max_v:.1f}" if not np.isnan(max_v) else None)
    with c3: st.metric("Avg Spin", fmt(avg_sp, " rpm", 0))
    with c4: st.metric("Pitches Types", str(pf["TaggedPitchType"].nunique()))
    with c5: st.metric("Distinct Dates",
                       str(pf["Date"].dt.date.nunique()) if "Date" in pf.columns else "—")
    st.markdown("<br>", unsafe_allow_html=True)
    render_percentile_section(
        selected, league_pitcher_table(df), PITCHER_INVERT,
        defaults={"Avg Velo": float(lmeta.get("velo_avg", 88)),
                  "Max Velo": float(lmeta.get("velo_elite", 93)),
                  "Avg Spin": 2200.0, "Zone %": 48.0, "Whiff %": 24.0,
                  "Chase %": 28.0, "K %": 22.0, "BB %": 8.5},
        key="pit")

    # Figuras Plotly (una sola fuente; también alimentan el PDF)
    # El checkbox "arsenal_show_ind" se define abajo en el tab Summary por layout,
    # pero su valor se necesita aquí antes; Streamlit ya aplicó el valor nuevo del
    # widget a session_state antes de este rerun, así que el .get() lee el valor actual.
    fig_mov = vpitch.movement_bubble(movement_points(pf), selected,
                                     show_individual=st.session_state.get("arsenal_show_ind", True))
    fig_loc = vpitch.location_scatter(pf, selected)
    fig_kde = vpitch.hot_zone(pf, selected)
    fig_vel = vpitch.velo_trend(pf, selected)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 Summary", "📍 Location", "📊 Trends", "🎯 Whiff/CSW", "🏟️ Stadium"])
    with tab1:
        st.markdown('<div class="sh">🎯 Arsenal — Stuff</div>', unsafe_allow_html=True)
        st.checkbox("Mostrar pitcheos individuales", value=True, key="arsenal_show_ind")
        st.plotly_chart(fig_mov, use_container_width=True)
        summary_df = arsenal_stuff(pf)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        csv_dl(summary_df, f"{selected}_arsenal.csv")
        st.markdown('<div class="sh">Discipline</div>', unsafe_allow_html=True)
        disc_df = compute_pitch_discipline(pf)
        if disc_df.empty:
            st.info("PitchCall column required.")
        else:
            st.dataframe(disc_df, use_container_width=True, hide_index=True)
            csv_dl(disc_df, f"{selected}_discipline.csv")
    with tab2:
        cl, cr = st.columns(2)
        with cl: st.plotly_chart(fig_loc, use_container_width=True)
        with cr: st.plotly_chart(fig_kde, use_container_width=True)
        st.markdown('<div class="sh">Location by Pitch Type</div>', unsafe_allow_html=True)
        st.plotly_chart(vpitch.location_by_pitch(pf, selected), use_container_width=True)
    with tab3:
        st.plotly_chart(fig_vel, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.plotly_chart(vpitch.usage_heatmap(build_usage_by_count(pf), selected),
                        use_container_width=True)
    with tab4:
        st.markdown('<div class="sh">🎯 Whiff% / CSW% por zona</div>', unsafe_allow_html=True)
        ptypes = ["Todos"] + sorted(pf["TaggedPitchType"].dropna().unique().tolist())
        cq1, cq2 = st.columns([2, 3])
        with cq1:
            sel_pt = st.selectbox("Tipo de pitcheo", ptypes, key="whiffcsw_ptype")
        with cq2:
            sel_metric = st.radio("Métrica", ["Whiff %", "CSW %"], key="whiffcsw_metric",
                                  horizontal=True)
        sub = pf if sel_pt == "Todos" else pf[pf["TaggedPitchType"] == sel_pt]
        grid = whiff_csw_zone_grid(sub)
        metric = "whiff" if sel_metric == "Whiff %" else "csw"
        st.plotly_chart(vpitch.zone_rate_heatmap(grid, metric, f"{selected} · {sel_pt}"),
                        use_container_width=True)
        st.caption(f"{grid['total_pitches']} pitcheos con ubicación · "
                   "celdas con muestra baja (Whiff <4 swings / CSW <5 pitcheos) en gris con solo el conteo.")
    with tab5:
        st.info("Stadium analysis coming soon.")
    st.markdown('<div class="sh">📤 Export</div>', unsafe_allow_html=True)
    dr = (f"{df['Date'].min().date()}→{df['Date'].max().date()}"
          if df["Date"].notna().any() else "All dates")
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("📄 Build PDF Report", key="btn_pdf_pitch"):
            with st.spinner("Building PDF…"):
                pdf_b = export_pitching_pdf(selected, summary_df,
                                            disc_df if not disc_df.empty else pd.DataFrame(),
                                            fig_loc, fig_kde, fig_vel, fig_mov, dr)
            st.download_button("⬇️ Download PDF", pdf_b, f"{selected}_pitching.pdf",
                               "application/pdf", key="dl_pdf_pitch")
    with ec2:
        csv_dl(pf, f"{selected}_raw.csv", "⬇️ Raw CSV")

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
    # v4.5 — Percentile rankings estilo Savant vs la liga cargada
    render_percentile_section(
        selected, league_batter_table(df,lmeta), HITTER_INVERT,
        defaults={"Avg EV":float(lmeta.get("ev_avg",88)),
                  "Max EV":float(lmeta.get("ev_elite",105)),
                  "Hard Hit %":35.0,"Barrel %":6.0,"K %":22.0,"BB %":8.5,
                  "Chase %":28.0,"Whiff %":24.0,"wOBA":0.320},
        key="hit")
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
    source=st.sidebar.radio("src",["☁️ Perfiles","⬆️ Upload CSVs","🏆 Carpeta local"],
                            key="data_source",label_visibility="collapsed")
    tournament=""
    if source=="☁️ Perfiles":
        # ── v4.3 Cloud profiles: shared storage — everyone sees each profile's
        #    uploads and can add their own. Auto-refreshes when files change.
        sb=get_supabase()
        if sb is None: return
        profiles=sb_list_profiles(sb)
        NEW="➕ Crear perfil nuevo…"
        choice=st.sidebar.selectbox("👤 Perfil",[NEW]+profiles if profiles else [NEW],
                                    index=1 if profiles else 0,key="sb_profile")
        if choice==NEW:
            raw=st.sidebar.text_input("Nombre del perfil nuevo",key="sb_newprof",
                                      placeholder="Ej: Liga Norte 2026")
            profile=re.sub(r"[^A-Za-z0-9 _-]","",raw).strip()
            if not profile:
                st.markdown("""
                <div style="border:2px dashed #d0d0d0;border-radius:8px;padding:60px 36px;
                  text-align:center;margin-top:24px">
                  <div style="font-size:2.8rem;margin-bottom:10px">☁️</div>
                  <div style="font-size:1.2rem;font-weight:700;margin-bottom:8px">
                    Elige un perfil o crea uno nuevo</div>
                  <div style="font-size:.88rem;opacity:.55;line-height:1.6">
                    Todos los usuarios del app pueden ver los archivos de cada perfil<br>
                    y subir los suyos. El perfil se crea al subir su primer CSV.
                  </div>
                </div>""",unsafe_allow_html=True)
                return
        else:
            profile=choice
        tournament=profile
        # Upload panel — any user can add their own CSVs to the profile
        st.sidebar.markdown('<span class="sb-label">⬆️ Subir a este perfil</span>',
                            unsafe_allow_html=True)
        up_files=st.sidebar.file_uploader("Subir CSVs al perfil",type=["csv"],
                                          accept_multiple_files=True,key="sb_up",
                                          label_visibility="collapsed")
        csvs=sb_walk_csvs(sb,profile)
        if up_files and st.sidebar.button(f"⬆️ Subir {len(up_files)} archivo(s)",key="sb_upbtn"):
            done=sb_upload_files(sb,profile,up_files,[c[0] for c in csvs])
            if done:
                st.sidebar.success(f"✅ {done} archivo(s) subido(s) a **{profile}**")
                st.cache_data.clear(); st.rerun()
        if not csvs:
            st.info(f"El perfil **{profile}** aún no tiene archivos. "
                    "Sube el primer CSV desde la barra lateral para crearlo.")
            return
        # regions.csv / names.csv dentro del perfil → mapas; excluidos de la data
        AUX_FILES={"regions.csv","names.csv"}
        data_csvs=[c for c in csvs if c[0].split("/")[-1].lower() not in AUX_FILES]
        for fname,skey,cols,label in [
                ("regions.csv","region_csv_map",("Stadium","Region"),"🗺️ regions.csv"),
                ("names.csv","names_csv_map",("Variant","Canonical"),"🔗 names.csv")]:
            entry=[c for c in csvs if c[0].split("/")[-1].lower()==fname]
            if not entry: continue
            try:
                rb,_=sb_download_all(sb,tuple(c[0] for c in entry),str(entry))
                rm=pd.read_csv(io.BytesIO(rb[0]))
                if set(cols).issubset(rm.columns):
                    if skey=="region_csv_map":
                        st.session_state[skey]=dict(zip(
                            rm[cols[0]].astype(str).str.strip().str.title(),
                            rm[cols[1]].astype(str).str.strip()))
                    else:
                        st.session_state[skey]={normalize_name(str(v)):normalize_name(str(c))
                                                for v,c in zip(rm[cols[0]],rm[cols[1]])}
                    st.sidebar.caption(f"{label} del perfil cargado ({len(rm)})")
            except Exception: pass
        if not data_csvs:
            st.info(f"El perfil **{profile}** solo tiene archivos auxiliares — sube CSVs de Trackman."); return
        sig="|".join(f"{p}:{u}:{s}" for p,u,s in data_csvs)
        cache_key=hashlib.md5(sig.encode()).hexdigest()
        with st.spinner(f"Descargando {len(data_csvs)} archivo(s) del perfil…"):
            file_bytes,file_names=sb_download_all(sb,tuple(c[0] for c in data_csvs),cache_key)
        if not file_bytes:
            st.error("No pude descargar los archivos del perfil."); return
        n_files=len(file_names)
        st.sidebar.caption(f"👤 **{profile}** · {n_files} CSV(s) · compartido — "
                           "se actualiza al subir archivos")
        if st.sidebar.button("🔄 Actualizar perfil",key="sb_refresh"):
            st.cache_data.clear(); st.rerun()
    elif source=="⬆️ Upload CSVs":
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
        AUX_FILES={"regions.csv","names.csv"}
        paths=sorted(p for p in glob.glob(os.path.join(folder,"**","*.csv"),recursive=True)
                     if os.path.basename(p).lower() not in AUX_FILES)
        if not paths:
            st.warning(f"⚠️ No se encontraron CSVs en **{folder}**."); return
        # v4.2: optional regions.csv (Stadium,Region) in tournament or base folder
        for cand in (os.path.join(folder,"regions.csv"),os.path.join(base,"regions.csv")):
            if os.path.isfile(cand):
                try:
                    rm=pd.read_csv(cand)
                    if {"Stadium","Region"}.issubset(rm.columns):
                        st.session_state["region_csv_map"]=dict(zip(
                            rm["Stadium"].astype(str).str.strip().str.title(),
                            rm["Region"].astype(str).str.strip()))
                        st.sidebar.caption(f"🗺️ regions.csv cargado ({len(rm)} estadios)")
                except Exception as e:
                    st.sidebar.warning(f"regions.csv inválido: {e}")
                break
        # v4.7: optional names.csv (Variant,Canonical) — asignaciones fijas de nombres
        for cand in (os.path.join(folder,"names.csv"),os.path.join(base,"names.csv")):
            if os.path.isfile(cand):
                try:
                    nm=pd.read_csv(cand)
                    if {"Variant","Canonical"}.issubset(nm.columns):
                        st.session_state["names_csv_map"]={
                            normalize_name(str(v)):normalize_name(str(c))
                            for v,c in zip(nm["Variant"],nm["Canonical"])}
                        st.sidebar.caption(f"🔗 names.csv cargado ({len(nm)} nombres)")
                except Exception as e:
                    st.sidebar.warning(f"names.csv inválido: {e}")
                break
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
        master,pa,ba,auto_merges=load_and_clean(tuple(file_bytes),tuple(file_names),cache_key)

    if master.empty:
        st.error("❌ No valid data could be read from the uploaded files."); return

    # Stamp level metadata onto master so downstream functions can use it
    master.attrs["level_meta"]=lmeta

    st.sidebar.success(f"✅ **{len(master):,}** pitches · {n_files} file(s)")

    # ── v4.7 Limpieza de nombres: revisión + correcciones + names.csv ─────
    # names.csv (Variant,Canonical) cargado de carpeta/perfil manda sobre todo
    names_csv=st.session_state.get("names_csv_map",{})
    total_auto=pa+ba
    if total_auto>0 or names_csv:
        master=master.copy()
        with st.sidebar.expander(f"🔗 Nombres unificados ({total_auto})",expanded=False):
            st.caption("Variantes detectadas automáticamente (typos, acentos, "
                       "iniciales, orden). **Edita 'Unificado a'** para corregir: "
                       "escribe otro nombre para re-asignar, o repite la variante "
                       "para separarla.")
            rows=[{"Rol":rol,"Variante":k,"Unificado a":v}
                  for rol,mp in auto_merges.items() for k,v in sorted(mp.items())]
            edited_ov={}
            if rows:
                ed=st.data_editor(pd.DataFrame(rows),hide_index=True,
                                  use_container_width=True,key="names_editor",
                                  disabled=["Rol","Variante"])
                for rec in ed.to_dict("records"):
                    tgt=str(rec["Unificado a"]).strip()
                    if tgt and tgt!=auto_merges.get(rec["Rol"],{}).get(rec["Variante"]):
                        edited_ov.setdefault(rec["Rol"],{})[rec["Variante"]]=normalize_name(tgt)
            if names_csv:
                st.caption(f"📋 names.csv activo: {len(names_csv)} asignaciones fijas")
            all_maps=pd.DataFrame([{"Variant":k,"Canonical":v}
                                   for mp in auto_merges.values() for k,v in mp.items()])
            if not all_maps.empty:
                csv_dl(all_maps,"names.csv","⬇️ Guardar names.csv")
        # aplicar: names.csv > correcciones manuales > automático
        for col in ("Pitcher","Batter"):
            if f"{col}Orig" not in master.columns: continue
            auto=auto_merges.get(col,{}); ov=edited_ov.get(col,{}) if rows else {}
            if names_csv or ov:
                master[col]=master[f"{col}Orig"].map(
                    lambda nm: names_csv.get(nm, ov.get(nm, auto.get(nm, nm))))
        st.sidebar.caption(f"🔗 **{total_auto}** variantes unificadas ({pa} P · {ba} B)")

    # Clear cache button — lets analyst swap files without stale data
    if st.sidebar.button("🔄 Clear Cache & Reload", help="Force re-parse all uploaded files"):
        st.cache_data.clear()
        st.rerun()

    filtered=sidebar_date_filter(master)
    if filtered.empty: st.warning("⚠️ No data for selected dates."); return
    filtered=advanced_filters(filtered)
    if filtered.empty: st.warning("⚠️ No data after filters."); return

    st.sidebar.markdown('<span class="sb-label">🎯 Mode</span>',unsafe_allow_html=True)
    mode=st.sidebar.radio("m",["⚾ Pitching","🏏 Hitting","📊 League","🔥 Top Plays",
                               "🎯 Trayectorias 3D"],
                          key="dash_mode",label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("v4.8 (Savant Edition) · Streamlit · Pandas · Plotly")

    if mode=="⚾ Pitching": render_pitching(filtered,master,lmeta)
    elif mode=="🏏 Hitting": render_hitting(filtered,master,lmeta)
    elif mode=="🔥 Top Plays": render_top_plays(filtered,lmeta,tournament)
    elif mode=="🎯 Trayectorias 3D":
        try:
            from trajectory.streamlit_view import render_trajectory_mode
        except ImportError as e:
            st.error(f"Módulo de trayectorias no disponible: {e}. "
                     "Verifica que la carpeta trajectory/ esté en el repo y "
                     "que requirements.txt incluya plotly.")
        else:
            render_trajectory_mode(filtered,lmeta)
    else: render_league(filtered,lmeta)

if __name__=="__main__":
    main()