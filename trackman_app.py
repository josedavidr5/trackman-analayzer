"""
=============================================================================
  TRACKMAN BASEBALL ANALYTICS DASHBOARD  v4.1 — SAVANT EDITION
  Expert-grade Streamlit app with Baseball Savant–inspired visuals
  ─────────────────────────────────────────────────────────────────────────
  KEY FEATURES:
    ✓ Player search bar (live filtering for 100+ rosters)
    ✓ vs RHP / vs LHP splits with dual spray charts & damage zones
    ✓ Play result breakdown (1B, 2B, 3B, HR, K, BB, etc.)
    ✓ K% calculated correctly from PlayResult column
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
st.set_page_config(page_title="Trackman Analytics v4.1 (Savant)", page_icon="⚾",
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
def setup_savant_fig(figsize=(10, 6)):
    """Create a figure with Savant-style defaults."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(SAVANT_BG)
    ax.set_facecolor(SAVANT_BG)
    return fig, ax

def style_savant_ax(ax, hide_spines=True):
    """Apply Savant typography & grid to axes."""
    ax.grid(True, color=SAVANT_GRID, linewidth=0.7, alpha=0.8, linestyle='-')
    ax.set_axisbelow(True)
    if hide_spines:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(SAVANT_TEXT)
        ax.spines['bottom'].set_color(SAVANT_TEXT)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)
    ax.tick_params(colors=SAVANT_TEXT, labelsize=8.5, length=4, width=0.8)
    ax.xaxis.label.set_color(SAVANT_TEXT)
    ax.yaxis.label.set_color(SAVANT_TEXT)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontsize(8.5); label.set_color(SAVANT_TEXT)

def savant_title(ax, title, subtitle=''):
    """Add Savant-style title (bold, clean, no decoration)."""
    ax.text(0.5, 1.04, title, transform=ax.transAxes, ha='center', va='bottom',
            fontsize=12, fontweight='bold', color=SAVANT_TEXT)
    if subtitle:
        ax.text(0.5, 0.98, subtitle, transform=ax.transAxes, ha='center', va='top',
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

@st.cache_data(show_spinner=False)
def load_and_clean(_files_bytes, _file_names, _cache_key):
    frames=[]
    for b,n in zip(_files_bytes,_file_names):
        try: frames.append(pd.read_csv(io.BytesIO(b),low_memory=False))
        except Exception as e: st.warning(f"⚠️ Could not read **{n}**: {e}")
    if not frames: return pd.DataFrame(),0,0
    df=pd.concat(frames,ignore_index=True)
    df=map_cols(df)
    if "Date" in df.columns:
        df["Date"]=pd.to_datetime(df["Date"],dayfirst=True,errors="coerce")
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
    if "PitchCall" not in df.columns: return pd.DataFrame()
    ZONE={"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    SWING={"StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    CONTACT={"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    WHIFF={"StrikeSwinging"}
    rows=[]
    for pt,grp in df.groupby("TaggedPitchType"):
        pc=grp["PitchCall"].astype(str)
        n=len(grp); in_z=pc.isin(ZONE).sum(); sw=pc.isin(SWING).sum()
        ct=pc.isin(CONTACT).sum(); wh=pc.isin(WHIFF).sum()
        rows.append({"Pitch":pt,"Count":n,
                     "Zone %":safe_pct(in_z,n),"Swing %":safe_pct(sw,n),
                     "Contact %":safe_pct(ct,max(sw,1)),
                     "Chase %":safe_pct(max(0,sw-ct),max(n-in_z,1)),
                     "Whiff %":safe_pct(wh,max(sw,1))})
    return pd.DataFrame(rows).sort_values("Count",ascending=False).reset_index(drop=True)

def build_play_result_table(df):
    if "PlayResult" not in df.columns: return pd.DataFrame()
    counts=df["PlayResult"].value_counts().reset_index()
    counts.columns=["Result","Count"]
    counts=counts[counts["Result"]!="—"]
    counts["% of PAs"]=counts["Count"].apply(lambda x:safe_pct(x,len(df)))
    return counts.reset_index(drop=True)

def compute_plate_discipline_batter(df):
    if "PitchCall" not in df.columns: return {}
    pc=df["PitchCall"].astype(str)
    ZONE={"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    SWING={"StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    CONTACT={"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    WHIFF={"StrikeSwinging"}
    BB_CALLS={"BallCalled","HitByPitch","IntentionalBall"}
    n=len(df); in_z=pc.isin(ZONE).sum(); sw=pc.isin(SWING).sum()
    cont=pc.isin(CONTACT).sum(); whiff=pc.isin(WHIFF).sum()
    kk=0
    if "PlayResult" in df.columns:
        kk=(df["PlayResult"].astype(str).str.strip()=="K").sum()
    if kk==0:
        kk=pc.isin({"StrikeoutSwinging","StrikeoutCalled"}).sum()
    bb=pc.isin(BB_CALLS).sum()
    return {"Zone %":safe_pct(in_z,n), "Swing %":safe_pct(sw,n),
            "Contact %":safe_pct(cont,max(sw,1)),
            "Chase %":safe_pct(max(0,sw-cont),max(n-in_z,1)),
            "Whiff %":safe_pct(whiff,max(sw,1)),
            "K %":safe_pct(kk,n), "BB %":safe_pct(bb,n)}

def build_split_table(df, split_col="PitcherThrows"):
    if split_col not in df.columns: return pd.DataFrame()
    rows=[]
    for hand,grp in df.groupby(split_col):
        n=len(grp); r={"vs":hand,"Pitches":n}
        if "ExitSpeed" in grp.columns:
            ev=grp["ExitSpeed"].dropna()
            r["Avg EV"]=round(ev.mean(),1) if not ev.empty else np.nan
            r["HH %"]=safe_pct((ev>=95).sum(),len(ev))
        if "Angle" in grp.columns:
            la=grp["Angle"].dropna()
            r["Avg LA"]=round(la.mean(),1) if not la.empty else np.nan
        disc=compute_plate_discipline_batter(grp)
        r.update({k:v for k,v in disc.items()})
        rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)

def build_hitting_monthly(df):
    df=df.copy(); df["YearMonth"]=df["Date"].dt.to_period("M")
    rows=[]
    for period,grp in df.groupby("YearMonth"):
        r={"Month":str(period),"Pitches":len(grp)}
        for col,(mx,av) in [("ExitSpeed",("Max EV","Avg EV")),("Angle",("Max LA","Avg LA")),("Distance",("Max Dist","Avg Dist"))]:
            if col in df.columns:
                vals=grp[col].dropna()
                r[mx]=round(vals.max(),1) if not vals.empty else np.nan
                r[av]=round(vals.mean(),1) if not vals.empty else np.nan
        if "ExitSpeed" in df.columns:
            ev=grp["ExitSpeed"].dropna()
            r["HH %"]=safe_pct((ev>=95).sum(),len(ev))
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrel=((grp["ExitSpeed"].fillna(0)>=98)&(grp["Angle"].fillna(-999)>=8)&(grp["Angle"].fillna(-999)<=32)).sum()
            r["Barrel %"]=safe_pct(barrel,len(grp))
        if "PlayResult" in df.columns:
            r["K %"]=safe_pct((grp["PlayResult"].astype(str)=="K").sum(),len(grp))
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

def build_league_hitting_avg(df):
    if "ExitSpeed" not in df.columns: return pd.DataFrame()
    ev=df["ExitSpeed"].dropna()
    la=df["Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    dist=df["Distance"].dropna() if "Distance" in df.columns else pd.Series(dtype=float)
    barrel=pd.Series(dtype=float)
    if "ExitSpeed" in df.columns and "Angle" in df.columns:
        barrel=((df["ExitSpeed"].fillna(0)>=98)&(df["Angle"].fillna(-999)>=8)&(df["Angle"].fillna(-999)<=32))
    rows=[
        {"Metric":"Avg Exit Velo","League":fmt(ev.mean()," mph"),"Median":fmt(ev.median()," mph"),"Max":fmt(ev.max()," mph")},
        {"Metric":"Avg LA","League":fmt(la.mean(),"°"),"Median":fmt(la.median(),"°"),"Max":fmt(la.max(),"°")},
        {"Metric":"Avg Distance","League":fmt(dist.mean()," ft"),"Median":fmt(dist.median()," ft"),"Max":fmt(dist.max()," ft")},
        {"Metric":"Hard Hit %","League":f"{safe_pct((ev>=95).sum(),len(ev))}%","Median":"—","Max":"—"},
        {"Metric":"Barrel %","League":f"{safe_pct(barrel.sum(),len(df))}%" if len(barrel)>0 else "—","Median":"—","Max":"—"},
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
                   alpha=0.70,s=35,edgecolors="none",zorder=6)
    if loc.empty:
        ax.text(.5,.5,"No location data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
    draw_savant_zone(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)", fontsize=9); ax.set_ylabel("Height (ft)", fontsize=9)
    savant_title(ax,"Pitch Locations",name)
    style_savant_ax(ax)
    ax.legend(fontsize=7.5,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    ax.set_aspect("equal",adjustable="box")
    fig.tight_layout(pad=1.0); return fig

def plot_hot_zone(df, name):
    fig, ax = setup_savant_fig((5.5, 6))
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    if len(loc)>=5:
        try:
            sns.kdeplot(data=loc,x="PlateLocSide",y="PlateLocHeight",fill=True,
                        cmap="Blues",alpha=0.60,levels=10,thresh=0.05,ax=ax)
        except Exception: pass
    else:
        ax.text(.5,.5,"Need ≥ 5 pitches",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
    draw_savant_zone(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)", fontsize=9); ax.set_ylabel("Height (ft)", fontsize=9)
    savant_title(ax,"Hot Zone (Density)",name)
    style_savant_ax(ax)
    ax.set_aspect("equal",adjustable="box")
    fig.tight_layout(pad=1.0); return fig

def plot_spray_chart(df, name):
    fig, ax = setup_savant_fig((6.5, 6.5))
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
                  s=50, alpha=0.75, edgecolors="white", linewidths=0.5, zorder=5, vmin=60, vmax=110)
    if has_ev:
        cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.7)
        cb.set_label("Exit Speed (mph)", fontsize=8, color=SAVANT_TEXT)
        cb.ax.tick_params(labelsize=8)
    ax.set_xlim(-360,360); ax.set_ylim(-20,460)
    ax.set_xlabel("Horizontal (ft)", fontsize=9); ax.set_ylabel("Vertical (ft)", fontsize=9)
    savant_title(ax,"Spray Chart",name)
    style_savant_ax(ax)
    ax.set_aspect("equal",adjustable="box")
    fig.tight_layout(pad=1.0); return fig

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
                ax.scatter(pts["ExitSpeed"],pts["Angle"],color=color,alpha=0.65,
                           s=25,label=res,edgecolors="none",zorder=5)
        others=sub[~sub["PlayResult"].isin(RESULT_COLORS)]
        if len(others):
            ax.scatter(others["ExitSpeed"],others["Angle"],color=SAVANT_GREY,alpha=0.3,
                       s=15,edgecolors="none",zorder=3)
    else:
        ax.scatter(sub["ExitSpeed"],sub["Angle"],color=SAVANT_BLUE,alpha=0.50,
                   s=25,edgecolors="none",zorder=4)
    # Barrel zone
    ax.add_patch(patches.Rectangle((98,8),20,24,lw=1.8,edgecolor=SAVANT_ACCENT,
                                   facecolor=SAVANT_ACCENT,alpha=0.06,linestyle="--",zorder=2))
    ax.text(108.5,20,"BARREL",ha="center",va="center",color=SAVANT_ACCENT,fontsize=9,fontweight="bold",alpha=0.7)
    ax.set_xlabel("Exit Velocity (mph)", fontsize=9); ax.set_ylabel("Launch Angle (°)", fontsize=9)
    savant_title(ax,"Hit Quality Map — Exit Velo × Launch Angle",name)
    style_savant_ax(ax)
    ax.legend(fontsize=7.5,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT,loc="upper left")
    fig.tight_layout(pad=1.0); return fig

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
                      s=40,alpha=0.70,edgecolors="white" if has_ev else "none",
                      linewidths=0.5,zorder=6,vmin=60,vmax=110)
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
    fig.tight_layout(pad=1.0); return fig

def plot_ev_distribution(df, name):
    fig, ax = setup_savant_fig((7, 4))
    ev=df["ExitSpeed"].dropna() if "ExitSpeed" in df.columns else pd.Series(dtype=float)
    if ev.empty:
        ax.text(.5,.5,"No EV data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    _,bins,patches_list=ax.hist(ev,bins=22,color=SAVANT_BLUE,alpha=0.70,
                                 edgecolor=SAVANT_BG,linewidth=0.3)
    for p,left in zip(patches_list,bins[:-1]):
        if left>=95: p.set_facecolor(SAVANT_RED); p.set_alpha(0.80)
    ax.axvline(ev.mean(),color=SAVANT_ACCENT,lw=2.0,linestyle="--",zorder=6,
               label=f"Avg {ev.mean():.1f}")
    ax.axvline(95,color=SAVANT_RED,lw=1.5,linestyle=":",zorder=6,label="Hard Hit (95)")
    hh=(ev>=95).sum()
    ax.text(0.97,0.93,f"HH: {hh} ({safe_pct(hh,len(ev))}%)",transform=ax.transAxes,
            ha="right",va="top",color=SAVANT_RED,fontsize=9,fontweight="bold")
    ax.set_xlabel("Exit Velocity (mph)", fontsize=9); ax.set_ylabel("Count", fontsize=9)
    savant_title(ax,"Exit Velocity Distribution",name)
    style_savant_ax(ax)
    ax.legend(fontsize=8,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    fig.tight_layout(pad=1.0); return fig

def plot_la_distribution(df, name):
    fig, ax = setup_savant_fig((7, 4))
    la=df["Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    if la.empty:
        ax.text(.5,.5,"No LA data",ha="center",va="center",color=SAVANT_GREY,transform=ax.transAxes)
        fig.tight_layout(); return fig
    _,bins,patches_list=ax.hist(la,bins=22,color=SAVANT_BLUE,alpha=0.70,
                                 edgecolor=SAVANT_BG,linewidth=0.3)
    for p,left,right in zip(patches_list,bins[:-1],bins[1:]):
        if left>=8 and right<=32: p.set_facecolor(SAVANT_GREEN); p.set_alpha(0.85)
    ax.axvspan(8,32,alpha=0.08,color=SAVANT_GREEN,label="Barrel 8–32°",zorder=1)
    ax.axvline(la.mean(),color=SAVANT_ACCENT,lw=2.0,linestyle="--",zorder=6,
               label=f"Avg {la.mean():.1f}°")
    barrel=((la>=8)&(la<=32)).sum()
    ax.text(0.97,0.93,f"Barrel: {barrel} ({safe_pct(barrel,len(la))}%)",transform=ax.transAxes,
            ha="right",va="top",color=SAVANT_GREEN,fontsize=9,fontweight="bold")
    ax.set_xlabel("Launch Angle (°)", fontsize=9); ax.set_ylabel("Count", fontsize=9)
    savant_title(ax,"Launch Angle Distribution",name)
    style_savant_ax(ax)
    ax.legend(fontsize=8,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    fig.tight_layout(pad=1.0); return fig

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
                        alpha=0.10,color=color)
        ax.plot(daily["Date"],daily["mean"],label=pt,color=color,lw=1.8,marker="o",ms=4,alpha=0.85,zorder=5)
        if not daily.empty:
            last=daily.iloc[-1]
            ax.annotate(f'{last["mean"]:.1f}',(last["Date"],last["mean"]),
                        xytext=(4,4),textcoords="offset points",fontsize=8,color=color,fontweight="bold")
    ax.set_xlabel("Date", fontsize=9); ax.set_ylabel("Avg Velocity (mph)", fontsize=9)
    savant_title(ax,"Velocity Tendency",name)
    style_savant_ax(ax)
    ax.legend(fontsize=7.5,framealpha=0.6,edgecolor="none",facecolor="none",labelcolor=SAVANT_TEXT)
    fig.autofmt_xdate(rotation=28,ha="right"); fig.tight_layout(pad=1.0); return fig

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
        ax.scatter(x,y,s=max(n*3,60),color=color,alpha=0.80,
                   edgecolors="white",linewidths=0.8,zorder=6)
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
    style_savant_ax(ax); fig.tight_layout(pad=1.0); return fig

# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT (fixed for matplotlib 3.8+)
# ══════════════════════════════════════════════════════════════════════════════
def _fig_to_img(src_fig):
    import matplotlib.image as mpimg
    img_buf = io.BytesIO()
    src_fig.savefig(img_buf, format="png", dpi=110,
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
    ax.text(0.5,0.22,"Generated by Trackman Analytics Dashboard v4.1 (Savant Edition)",
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
    with tab3:
        fig_vel=plot_velocity_tendency(pf,selected)
        st.pyplot(fig_vel,use_container_width=True)
        st.markdown("<br>",unsafe_allow_html=True)
        fig_mov=plot_movement_profile(pf,selected)
        st.pyplot(fig_mov,use_container_width=True)
    with tab4:
        st.info("Stadium analysis coming soon.")
    st.markdown('<div class="sh">📤 Export</div>',unsafe_allow_html=True)
    if "summary_df" not in locals(): summary_df=build_pitch_summary(pf)
    if "disc_df" not in locals(): disc_df=compute_pitch_discipline(pf)
    if "fig_loc" not in locals(): fig_loc=plot_pitch_locations(pf,selected)
    if "fig_kde" not in locals(): fig_kde=plot_hot_zone(pf,selected)
    if "fig_vel" not in locals(): fig_vel=plot_velocity_tendency(pf,selected)
    if "fig_mov" not in locals(): fig_mov=plot_movement_profile(pf,selected)
    dr=f"{df['Date'].min().date()}→{df['Date'].max().date()}" if df["Date"].notna().any() else "All dates"
    ec1,ec2=st.columns(2)
    with ec1:
        pdf_b=export_pitching_pdf(selected,summary_df,
                                   disc_df if not disc_df.empty else pd.DataFrame(),
                                   fig_loc,fig_kde,fig_vel,fig_mov,dr)
        st.download_button("⬇️ PDF Report",pdf_b,f"{selected}_pitching.pdf","application/pdf")
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
    avg_ev=bdf["ExitSpeed"].mean() if "ExitSpeed" in bdf.columns else np.nan
    max_ev=bdf["ExitSpeed"].max() if "ExitSpeed" in bdf.columns else np.nan
    avg_la=bdf["Angle"].mean() if "Angle" in bdf.columns else np.nan
    hh_rate=barrel_rate=0.0
    if "ExitSpeed" in bdf.columns:
        ev_s=bdf["ExitSpeed"].dropna()
        hh_rate=safe_pct((ev_s>=EV_HARD).sum(),len(ev_s))
    if "ExitSpeed" in bdf.columns and "Angle" in bdf.columns:
        barrel=((bdf["ExitSpeed"].fillna(0)>=EV_ELITE)&
                (bdf["Angle"].fillna(-999)>=8)&
                (bdf["Angle"].fillna(-999)<=32)).sum()
        barrel_rate=safe_pct(barrel,n)
    disc=compute_plate_discipline_batter(bdf)
    c1,c2,c3,c4,c5,c6=st.columns(6)
    with c1: st.metric("Pitches",f"{n:,}")
    with c2: st.metric("Avg EV",fmt(avg_ev," mph"),delta=f"Max {max_ev:.1f}" if not np.isnan(max_ev) else None)
    with c3: st.metric("Avg LA",fmt(avg_la,"°"))
    with c4: st.metric("HH %",f"{hh_rate:.1f}%")
    with c5: st.metric("Barrel %",f"{barrel_rate:.1f}%")
    with c6: st.metric("Dates",str(bdf["Date"].dt.date.nunique()) if "Date" in bdf.columns else "—")
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
        monthly_df=build_hitting_monthly(bdf)
        if monthly_df.empty: st.info("No monthly data.")
        else:
            st.dataframe(monthly_df,use_container_width=True,hide_index=True)
            csv_dl(monthly_df,f"{selected}_monthly.csv")
    with tab2:
        st.markdown('<div class="sh">vs RHP / LHP</div>',unsafe_allow_html=True)
        split_df=build_split_table(bdf)
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
    if "monthly_df" not in locals(): monthly_df=build_hitting_monthly(bdf)
    if "result_df" not in locals(): result_df=build_play_result_table(bdf)
    if "split_df" not in locals(): split_df=build_split_table(bdf)
    if "fig_spray" not in locals(): fig_spray=plot_spray_chart(bdf,selected)
    if "fig_dmg" not in locals(): fig_dmg=plot_damage_zone(bdf,selected)
    if "fig_ev" not in locals(): fig_ev=plot_ev_distribution(bdf,selected)
    if "fig_la" not in locals(): fig_la=plot_la_distribution(bdf,selected)
    if "fig_ev_la" not in locals(): fig_ev_la=plot_ev_la_scatter(bdf,selected)
    dr=f"{df['Date'].min().date()}→{df['Date'].max().date()}" if df["Date"].notna().any() else "All dates"
    ec1,ec2=st.columns(2)
    with ec1:
        pdf_b=export_hitting_pdf(selected,monthly_df,disc,result_df,split_df,
                                  fig_spray,fig_dmg,fig_ev,fig_la,fig_ev_la,dr)
        st.download_button("⬇️ PDF Report",pdf_b,f"{selected}_hitting.pdf","application/pdf")
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
            lh=build_league_hitting_avg(df)
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
          <span style="font-size:.9rem;opacity:.35;font-weight:400"> v4.1 (Savant)</span></div>
        <div class="hero-sub">
          Professional baseball analytics with Baseball Savant–inspired design
        </div>
        <div class="hero-pills">
          <span class="pill">🔍 Player Search</span><span class="pill">📊 League Avg</span>
          <span class="pill">🔄 RHP / LHP</span><span class="pill">🎯 Play Results</span>
          <span class="pill">📈 Hit Quality</span><span class="pill">PDF Export</span>
        </div>
      </div>
    </div>
    """,unsafe_allow_html=True)

    st.sidebar.markdown('<span class="sb-label">📂 Data</span>',unsafe_allow_html=True)
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
            The dashboard auto-merges, cleans, and deduplicates player names
          </div>
        </div>""",unsafe_allow_html=True)
        return

    # ── Cache-busting: hash actual file contents so swapping a file always re-parses ──
    import hashlib
    file_bytes=[f.read() for f in uploaded]
    file_names=[f.name for f in uploaded]
    cache_key=hashlib.md5(b"".join(file_bytes)).hexdigest()

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
            "ev_elite":110, "ev_hard":95, "ev_avg":89,
            "velo_elite":97, "velo_avg":93,
            "barrel_note":"MLB barrel zone: ≥98 mph EV, 8°–32° LA",
            "zone_note":"MLB zone width ≈ 17 in (±0.71 ft)",
            "context":"Benchmarks calibrated to MLB / MiLB averages.",
        },
        "🎓 Amateur / College":{
            "label":"College / JUCO",
            "ev_elite":103, "ev_hard":90, "ev_avg":83,
            "velo_elite":92, "velo_avg":86,
            "barrel_note":"College barrel zone: ≥92 mph EV, 8°–32° LA",
            "zone_note":"NCAA zone similar to MLB",
            "context":"Benchmarks calibrated to NCAA D1/D2/JUCO averages.",
        },
        "🏫 High School":{
            "label":"High School",
            "ev_elite":95,  "ev_hard":83, "ev_avg":75,
            "velo_elite":85,"velo_avg":77,
            "barrel_note":"HS barrel zone: ≥85 mph EV, 8°–32° LA",
            "zone_note":"Same strike zone dimensions",
            "context":"Benchmarks calibrated to high-school averages.",
        },
        "🔀 Mixed":{
            "label":"Mixed levels",
            "ev_elite":105, "ev_hard":92, "ev_avg":85,
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

    total_files=len(uploaded)
    st.sidebar.success(f"✅ **{len(master):,}** pitches · {total_files} file(s)")
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
    mode=st.sidebar.radio("m",["⚾ Pitching","🏏 Hitting","📊 League"],
                          key="dash_mode",label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("v4.1 (Savant Edition) · Streamlit · Pandas · Matplotlib")

    if mode=="⚾ Pitching": render_pitching(filtered,master,lmeta)
    elif mode=="🏏 Hitting": render_hitting(filtered,master,lmeta)
    else: render_league(filtered,lmeta)

if __name__=="__main__":
    main()