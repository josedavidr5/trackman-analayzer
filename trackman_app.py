"""
=============================================================================
  TRACKMAN BASEBALL ANALYTICS DASHBOARD  v4.0
  Expert-grade Streamlit app for pitching and hitting analysis
  ─────────────────────────────────────────────────────────────────────────
  NEW in v4
  ─────────────────────────────────────────────────────────────────────────
  SEARCH BAR
    • Live text-search box filters the 100+ player dropdown in real time
    • Works for both pitchers and batters

  LEAGUE & STADIUM INTELLIGENCE
    • League Averages tab: every key metric benchmarked across all players
    • Stadium Analysis: per-ballpark breakdown of EV, LA, Distance, Velo
    • Player vs Stadium: how a specific player's metrics shift across parks
    • Park Factor heatmap: visualise which stadiums inflate/suppress offence

  UMPIRE / STRIKE ZONE ANALYSIS  (new top-level dashboard mode)
    • Called-Strike Zone map: where balls are called strikes (bad calls)
    • Called-Ball Zone map: where strikes are called balls
    • Strike-Zone Accuracy % per umpire (UmpireName column)
    • Favour bias map: which side of plate umpire favours
    • Edge-pitch call accuracy breakdown
    • Comparison: player's zone vs umpire's called zone overlay

  HITTING — MASSIVE UPGRADES
    • vs RHP / vs LHP split tab: all metrics, spray chart, damage zone
      side-by-side for each platoon split
    • Play Result table: counts of 1B, 2B, 3B, HR, Out, K, BB, HBP, FC
    • K% now correctly calculated from PlayResult / KorBB columns
    • At-Bat outcome distribution pie/bar chart
    • Hit quality scatter: EV × LA coloured by result (HR/XBH/Single/Out)
    • Stadium development: monthly EV/LA trend per stadium

  PDF REPORT — REDESIGNED
    • Cover page with player name, date range, and logo area
    • Colour-coded section dividers between pages
    • Tables use alternating rows with proper column spacing
    • Charts laid out 2-per-page for readability (not 1 per page)
    • Summary scorecard page at the end

  ADDITIONAL EXPERT ADDITIONS
    • Pitch Tunnelling index (how similar the release looks across pitches)
    • Count-leverage table: pitcher performance in hitter/pitcher counts
    • Approach angle chart (VertApprAngle vs HorzApprAngle)
    • Batter heat-map of swing vs take decisions on zone/out-of-zone pitches
  ─────────────────────────────────────────────────────────────────────────
  Built with: Streamlit, Pandas, Matplotlib, Seaborn, NumPy, unicodedata
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
# COLOUR SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
ACCENT  = "#e8a838";  ACCENT2 = "#c8881a"
BLUE    = "#2979d4";  RED     = "#d63d3d"
GREEN   = "#2a9d5c";  PURPLE  = "#7c3aed"
TEAL    = "#0891b2";  ORANGE  = "#ea580c"
PINK    = "#db2777";  LIME    = "#65a30d"

PITCH_PALETTE = [ACCENT,BLUE,RED,GREEN,PURPLE,TEAL,ORANGE,PINK,LIME,
                 "#6366f1","#0d9488","#f59e0b"]

CHART_BG_LIGHT="#f8f9fa"; CHART_CARD_LIGHT="#ffffff"
CHART_GRID_LIGHT="#e2e8f0"; CHART_MUTED_LIGHT="#64748b"; CHART_TEXT_LIGHT="#1e293b"
CHART_BG_DARK="#0d1117";  CHART_CARD_DARK="#161b22"
CHART_GRID_DARK="#21262d"; CHART_MUTED_DARK="#8b949e";  CHART_TEXT_DARK="#e6edf3"

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Trackman Analytics v4", page_icon="⚾",
                   layout="wide", initial_sidebar_state="expanded")

def _get_theme():
    try:
        b = st.get_option("theme.base")
        return b if b in ("light","dark") else "light"
    except Exception:
        return "light"

IS_DARK = _get_theme() == "dark"
C_BG    = CHART_BG_DARK    if IS_DARK else CHART_BG_LIGHT
C_CARD  = CHART_CARD_DARK  if IS_DARK else CHART_CARD_LIGHT
C_GRID  = CHART_GRID_DARK  if IS_DARK else CHART_GRID_LIGHT
C_MUTE  = CHART_MUTED_DARK if IS_DARK else CHART_MUTED_LIGHT
C_TEXT  = CHART_TEXT_DARK  if IS_DARK else CHART_TEXT_LIGHT
C_SPINE = "#30363d" if IS_DARK else "#cbd5e1"

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
section[data-testid="stSidebar"]{border-right:1px solid rgba(128,128,128,.2)}
.sb-label{font-size:.63rem;font-weight:800;letter-spacing:.18em;text-transform:uppercase;
  color:#e8a838;padding:14px 0 4px 0;display:block}
.hero{background:linear-gradient(135deg,rgba(232,168,56,.08) 0%,transparent 60%);
  border:1px solid rgba(128,128,128,.25);border-left:4px solid #e8a838;
  border-radius:12px;padding:22px 28px;margin-bottom:18px;display:flex;align-items:center;gap:18px}
.hero-icon{font-size:3rem;line-height:1;filter:drop-shadow(0 2px 6px rgba(232,168,56,.4))}
.hero-title{font-size:2rem;font-weight:900;letter-spacing:-.03em;line-height:1.05}
.hero-title .hl{color:#e8a838}
.hero-sub{font-size:.87rem;margin-top:4px;opacity:.6}
.hero-pills{display:flex;gap:6px;margin-top:9px;flex-wrap:wrap}
.pill{background:rgba(232,168,56,.1);border:1px solid rgba(232,168,56,.3);color:#e8a838;
  border-radius:20px;padding:2px 10px;font-size:.68rem;font-weight:700;letter-spacing:.04em}
.sh{font-size:.72rem;font-weight:800;color:#e8a838;text-transform:uppercase;
  letter-spacing:.14em;border-bottom:1px solid rgba(232,168,56,.25);
  padding-bottom:6px;margin:20px 0 11px 0}
div[data-testid="metric-container"]{border:1px solid rgba(128,128,128,.2)!important;
  border-top:3px solid #e8a838!important;border-radius:10px!important;
  padding:14px 12px!important;transition:box-shadow .2s}
div[data-testid="metric-container"]:hover{box-shadow:0 0 14px rgba(232,168,56,.18)}
div[data-testid="metric-container"] label{font-size:.71rem!important;letter-spacing:.05em!important;opacity:.65!important}
div[data-testid="metric-container"] div[data-testid="stMetricValue"]{color:#e8a838!important;font-size:1.7rem!important;font-weight:800!important}
.stTabs [data-baseweb="tab-list"]{gap:3px;border-radius:10px;padding:3px;border:1px solid rgba(128,128,128,.2)}
.stTabs [data-baseweb="tab"]{border-radius:7px;font-weight:600;font-size:.82rem;opacity:.6}
.stTabs [aria-selected="true"]{background:#e8a838!important;color:#000!important;opacity:1!important}
.stDownloadButton>button{background:rgba(232,168,56,.08)!important;border:1px solid #e8a838!important;
  color:#e8a838!important;font-weight:700!important;border-radius:7px!important;transition:all .18s}
.stDownloadButton>button:hover{background:#e8a838!important;color:#000!important}
div[data-testid="stDataFrame"]{border:1px solid rgba(128,128,128,.2);border-radius:10px;overflow:hidden}
div[data-testid="stExpander"]{border:1px solid rgba(128,128,128,.2)!important;border-radius:8px!important}
.date-chip-wrap{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.date-chip{background:rgba(232,168,56,.12);border:1px solid rgba(232,168,56,.3);color:#e8a838;
  border-radius:14px;padding:2px 9px;font-size:.68rem;font-weight:700}
.stat-badge{border:1px solid rgba(128,128,128,.2);border-radius:8px;padding:9px 13px;
  text-align:center;min-width:82px}
.stat-badge .val{font-size:1.4rem;font-weight:800;color:#e8a838;line-height:1.1}
.stat-badge .lbl{font-size:.6rem;letter-spacing:.07em;text-transform:uppercase;opacity:.5;margin-top:2px}
.upload-zone{border:2px dashed rgba(128,128,128,.3);border-radius:14px;padding:60px 36px;
  text-align:center;margin-top:24px}
.upload-zone .big{font-size:2.8rem;margin-bottom:10px}
.upload-zone .ttl{font-size:1.25rem;font-weight:700;margin-bottom:7px}
.upload-zone .sub{font-size:.87rem;line-height:1.6;opacity:.52}
.alias-box{border:1px solid rgba(232,168,56,.28);border-left:3px solid #e8a838;
  border-radius:6px;padding:7px 11px;font-size:.76rem;opacity:.82;margin-top:5px}
.search-hint{font-size:.72rem;opacity:.5;margin-top:3px;font-style:italic}
/* result-type colour legend */
.rt-hr{color:#e8a838}.rt-xbh{color:#2979d4}.rt-single{color:#2a9d5c}
.rt-out{color:#d63d3d}.rt-k{color:#7c3aed}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def act(fig, ax_list=None):
    """Apply adaptive chart theme."""
    fig.patch.set_facecolor(C_BG)
    for ax in (ax_list or fig.get_axes()):
        ax.set_facecolor(C_CARD); ax.tick_params(colors=C_MUTE,labelsize=8.5)
        ax.xaxis.label.set_color(C_MUTE); ax.yaxis.label.set_color(C_MUTE)
        ax.title.set_color(C_TEXT)
        for sp in ax.spines.values(): sp.set_edgecolor(C_SPINE)
        ax.grid(color=C_GRID,linewidth=0.6,alpha=0.65,linestyle="--")

def cht(ax, text, sub=None):
    ax.set_title(text, color=C_TEXT, fontsize=11, fontweight="bold", pad=9)
    if sub: ax.text(.5,1.004,sub,transform=ax.transAxes,ha="center",va="bottom",fontsize=7.5,color=C_MUTE)

def draw_sz(ax, color=ACCENT, lw=1.8):
    ax.add_patch(patches.Rectangle((-0.71,1.5),1.42,2.0,lw=lw,
        edgecolor=color,facecolor="none",alpha=0.9,zorder=5))
    for i in range(1,3): ax.axvline(-0.71+i*1.42/3,color=color,lw=0.5,alpha=0.22,zorder=4)
    for j in range(1,3): ax.axhline(1.5+j*2.0/3,color=color,lw=0.5,alpha=0.22,zorder=4)

def draw_plate(ax):
    ax.fill([-0.71,-0.71,0,0.71,0.71],[0.35,0.15,0,0.15,0.35],
            color=C_MUTE,alpha=0.18,zorder=3)

def safe_pct(num,denom): return round(100*num/denom,1) if denom>0 else 0.0
def csv_dl(df,fname,label="⬇️ Download CSV"):
    st.download_button(label,df.to_csv(index=False).encode(),fname,"text/csv")

def fmt(v, suffix="", decimals=1):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "—"
    return f"{v:.{decimals}f}{suffix}"

# ══════════════════════════════════════════════════════════════════════════════
# NAME NORMALISATION & DEDUPLICATION (unchanged from v3)
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
# DATA LOADING & CLEANING
# ══════════════════════════════════════════════════════════════════════════════
COL_ALIASES={
    "TaggedPitchType":["AutoPitchType","PitchType"],
    "PitchCall":      ["Call","PitchResult"],
    "Batter":         ["BatterName","HitterName"],
    "Pitcher":        ["PitcherName","ThrowerName"],
    "BatterSide":     ["BatterHand","BatterHandedness","Side"],
    "PitcherThrows":  ["PitcherHand","Throws"],
    "Stadium":        ["BallPark","Ballpark","Venue","Park","Field","Location"],
    "Umpire":         ["UmpireName","HomeUmpire","PlateUmpire","PlatUmp"],
    "PlayResult":     ["KorBB","TaggedHitType","HitType","Result","PlayOutcome"],
}
WARMUP={"warmup","undefined"}
PITCH_MAP={
    "four-seam fastball":"4-Seam Fastball","fourseam":"4-Seam Fastball",
    "4-seam":"4-Seam Fastball","4seam":"4-Seam Fastball","ff":"4-Seam Fastball","fa":"4-Seam Fastball",
    "two-seam fastball":"2-Seam Fastball","twoseam":"2-Seam Fastball",
    "2-seam":"2-Seam Fastball","2seam":"2-Seam Fastball",
    "sinker":"Sinker","si":"Sinker","curveball":"Curveball","curve":"Curveball",
    "cb":"Curveball","cu":"Curveball","slider":"Slider","sl":"Slider",
    "sweeper":"Sweeper","sw":"Sweeper","changeup":"Changeup","change":"Changeup",
    "ch":"Changeup","cutter":"Cutter","cut fastball":"Cutter","fc":"Cutter",
    "splitter":"Splitter","split":"Splitter","fs":"Splitter",
    "knuckleball":"Knuckleball","kn":"Knuckleball","screwball":"Screwball","fastball":"Fastball",
}

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

# PlayResult normalisation → clean category
RESULT_MAP={
    # Hits
    "single":"1B","1b":"1B","hit":"1B",
    "double":"2B","2b":"2B",
    "triple":"3B","3b":"3B",
    "homerun":"HR","home_run":"HR","hr":"HR",
    # Outs
    "out":"Out","fieldersChoice":"FC","fielderschoice":"FC","fc":"FC",
    "error":"Error","sacrificefly":"SacFly","sacfly":"SacFly",
    "sacrificebunt":"SacBunt","sacbunt":"SacBunt",
    # Strikeouts
    "strikeout":"K","strikeoutswinging":"K","strikeoutlooking":"K","k":"K","kk":"K",
    # Walks / HBP
    "walk":"BB","intentionalwalk":"BB","bb":"BB",
    "hitbypitch":"HBP","hbp":"HBP",
    # No result
    "undefined":"—","nan":"—","":"—",
}
def norm_result(v):
    if not isinstance(v,str): return "—"
    c=v.strip().lower().replace(" ","").replace("-","").replace("_","")
    return RESULT_MAP.get(c,v.strip())

NUMERIC_COLS=["RelSpeed","SpinRate","InducedVertBreak","HorzBreak",
              "PlateLocSide","PlateLocHeight","ExitSpeed","Angle","Distance",
              "Bearing","RelHeight","RelSide","Extension","SpinAxis",
              "VertApprAngle","HorzApprAngle","Balls","Strikes","Inning"]

@st.cache_data(show_spinner=False)
def load_and_clean(_files_bytes, _file_names):
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
    removed=before-len(df)
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
    mode=st.sidebar.radio("dm",["📆 Date Range","🗓️ Pick Specific Dates"],
                          horizontal=True,label_visibility="collapsed",key="date_mode")
    if mode=="📆 Date Range":
        sel=st.sidebar.date_input("Range",value=(min_d,max_d),min_value=min_d,max_value=max_d)
        s,e=(sel if isinstance(sel,(list,tuple)) and len(sel)==2 else (sel or min_d,sel or min_d))
        filtered=df[(df["Date"].dt.date>=s)&(df["Date"].dt.date<=e)]
        st.sidebar.caption(f"📊 **{len(filtered):,}** pitches · {s} → {e}")
    else:
        dfmt={d:d.strftime("%a %b %d, %Y") for d in all_dates}
        fl=[dfmt[d] for d in all_dates]
        chosen=st.sidebar.multiselect("Dates",options=fl,default=fl[-min(7,len(fl)):],
                                      help="Pick any dates — e.g. every Tue & Thu")
        if not chosen:
            filtered=df.copy()
        else:
            rev={v:k for k,v in dfmt.items()}
            filtered=df[df["Date"].dt.date.isin({rev[l] for l in chosen})]
            chips="".join(f'<span class="date-chip">{l.split(",")[0]}</span>' for l in chosen)
            st.sidebar.markdown(f'<div class="date-chip-wrap">{chips}</div>',unsafe_allow_html=True)
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
            opts=sorted(df["Stadium"].dropna().unique())
            opts=[o for o in opts if o not in ("Unknown","Nan","")]
            if opts:
                sel=st.multiselect("Stadiums",opts,default=opts,key="adv_stad")
                if sel: df=df[df["Stadium"].isin(sel)]
        if "Inning" in df.columns and df["Inning"].notna().any():
            lo,hi=int(df["Inning"].min()),int(df["Inning"].max())
            if lo<hi:
                rng=st.slider("Inning",lo,hi,(lo,hi),key="adv_inn")
                df=df[(df["Inning"]>=rng[0])&(df["Inning"]<=rng[1])]
    return df.reset_index(drop=True)

# ══════════════════════════════════════════════════════════════════════════════
# PLAYER SEARCH
# ══════════════════════════════════════════════════════════════════════════════
def player_search_select(all_players, label, key):
    """
    Search bar + dropdown combo. Text search filters the list live;
    selectbox shows only matching names.
    """
    query=st.text_input(f"🔍 Search {label}",value="",key=f"search_{key}",
                        placeholder=f"Type name to filter {len(all_players)} players…")
    st.markdown('<div class="search-hint">Type part of a name to narrow the list</div>',
                unsafe_allow_html=True)
    if query.strip():
        q=query.strip().lower()
        filtered=[p for p in all_players if q in p.lower()]
    else:
        filtered=all_players
    if not filtered:
        st.warning("No players match — showing all."); filtered=all_players
    return st.selectbox(label,filtered,key=f"sel_{key}")

# ══════════════════════════════════════════════════════════════════════════════
# LEAGUE AVERAGES
# ══════════════════════════════════════════════════════════════════════════════
def build_league_pitching_avg(df):
    rows=[]
    for pt,grp in df.groupby("TaggedPitchType"):
        n=len(grp)
        if n<10: continue
        r={"Pitch Type":pt,"Pitches":n}
        for col,alias,dec in [("RelSpeed","Avg MPH",1),("SpinRate","Avg Spin",0),
                               ("InducedVertBreak","Avg IVB",1),("HorzBreak","Avg HB",1),
                               ("Extension","Avg Ext",1)]:
            r[alias]=round(grp[col].mean(),dec) if col in grp.columns else np.nan
        rows.append(r)
    out=pd.DataFrame(rows)
    if out.empty: return out
    out["_fb"]=out["Pitch Type"].str.lower().str.contains("fastball").astype(int)
    return out.sort_values(["_fb","Pitches"],ascending=[False,False]).drop(columns="_fb").reset_index(drop=True)

def build_league_hitting_avg(df):
    if "ExitSpeed" not in df.columns: return pd.DataFrame()
    ev=df["ExitSpeed"].dropna()
    la=df["Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    dist=df["Distance"].dropna() if "Distance" in df.columns else pd.Series(dtype=float)
    barrel=pd.Series(dtype=float)
    if "ExitSpeed" in df.columns and "Angle" in df.columns:
        barrel=((df["ExitSpeed"].fillna(0)>=98)&(df["Angle"].fillna(-999)>=8)&(df["Angle"].fillna(-999)<=32))
    rows=[{
        "Metric":"Avg Exit Velo","League":fmt(ev.mean()," mph"),
        "Median":fmt(ev.median()," mph"),"Max":fmt(ev.max()," mph"),
    },{
        "Metric":"Avg Launch Angle","League":fmt(la.mean(),"°"),
        "Median":fmt(la.median(),"°"),"Max":fmt(la.max(),"°"),
    },{
        "Metric":"Avg Distance","League":fmt(dist.mean()," ft"),
        "Median":fmt(dist.median()," ft"),"Max":fmt(dist.max()," ft"),
    },{
        "Metric":"Hard Hit %","League":f"{safe_pct((ev>=95).sum(),len(ev))}%",
        "Median":"—","Max":"—",
    },{
        "Metric":"Barrel %","League":f"{safe_pct(barrel.sum(),len(df))}%" if len(barrel)>0 else "—",
        "Median":"—","Max":"—",
    }]
    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════════════════════════
# STADIUM ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
def build_stadium_table(df, metric_col="ExitSpeed", metric_name="Avg EV"):
    if "Stadium" not in df.columns or metric_col not in df.columns:
        return pd.DataFrame()
    grp=df.groupby("Stadium")[metric_col]
    out=pd.DataFrame({
        "Stadium":grp.mean().index,
        metric_name:grp.mean().round(1).values,
        "Max":grp.max().round(1).values,
        "Pitches":grp.count().values,
    }).sort_values(metric_name,ascending=False).reset_index(drop=True)
    return out[out["Pitches"]>=10]

def plot_stadium_bar(df, metric_col, metric_name, title, player_val=None):
    tbl=build_stadium_table(df,metric_col,metric_name)
    if tbl.empty:
        fig,ax=plt.subplots(figsize=(8,2)); act(fig,[ax])
        ax.text(.5,.5,"No stadium data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        return fig
    fig,ax=plt.subplots(figsize=(max(6,len(tbl)*0.7),3.8))
    act(fig,[ax])
    colors=[ACCENT]*len(tbl)
    bars=ax.bar(tbl["Stadium"],tbl[metric_name],color=colors,alpha=0.82,
                edgecolor=C_SPINE,linewidth=0.4,zorder=3)
    if player_val is not None:
        ax.axhline(player_val,color=RED,lw=2.0,linestyle="--",
                   label=f"Player avg: {player_val:.1f}",zorder=5)
        ax.legend(fontsize=8,framealpha=0.5,facecolor=C_CARD,labelcolor=C_TEXT)
    for bar,val in zip(bars,tbl[metric_name]):
        ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.3,
                f"{val:.1f}",ha="center",va="bottom",fontsize=7.5,color=C_TEXT,fontweight="bold")
    ax.set_xlabel("Stadium"); ax.set_ylabel(metric_name)
    plt.xticks(rotation=35,ha="right",fontsize=8)
    cht(ax,title); fig.tight_layout(pad=1.2); return fig

def plot_player_stadium_trend(df, player_name, player_col, metric_col, metric_name):
    """Show how a player's metric changes across stadiums."""
    if "Stadium" not in df.columns or metric_col not in df.columns:
        fig,ax=plt.subplots(figsize=(7,3)); act(fig,[ax])
        ax.text(.5,.5,"No stadium data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        return fig
    pdf=df[df[player_col]==player_name].copy()
    grp=pdf.groupby("Stadium")[metric_col].agg(["mean","count"]).reset_index()
    grp.columns=["Stadium","Mean","N"]
    grp=grp[grp["N"]>=5].sort_values("Mean",ascending=False)
    league_avg=df[metric_col].mean()
    fig,ax=plt.subplots(figsize=(max(6,len(grp)*0.85),3.8))
    act(fig,[ax])
    c=[RED if v>=league_avg else BLUE for v in grp["Mean"]]
    bars=ax.bar(grp["Stadium"],grp["Mean"],color=c,alpha=0.82,
                edgecolor=C_SPINE,linewidth=0.4,zorder=3)
    ax.axhline(league_avg,color=ACCENT,lw=1.8,linestyle="--",
               label=f"League avg: {league_avg:.1f}",zorder=5)
    for bar,val,n in zip(bars,grp["Mean"],grp["N"]):
        ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.2,
                f"{val:.1f}\n(n={n})",ha="center",va="bottom",fontsize=7,color=C_TEXT)
    ax.legend(fontsize=8,framealpha=0.5,facecolor=C_CARD,labelcolor=C_TEXT)
    ax.set_xlabel("Stadium"); ax.set_ylabel(metric_name)
    plt.xticks(rotation=35,ha="right",fontsize=8)
    cht(ax,f"{metric_name} by Stadium",sub=player_name)
    fig.tight_layout(pad=1.2); return fig



# ══════════════════════════════════════════════════════════════════════════════
# PITCHING ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
def build_pitch_summary(df):
    total=len(df); rows=[]
    for pt,grp in df.groupby("TaggedPitchType"):
        r={"Pitch Type":pt,"Count":len(grp),"Usage %":safe_pct(len(grp),total)}
        if "RelSpeed" in grp.columns:
            r["Max MPH"]=round(grp["RelSpeed"].max(),1)
            r["Avg MPH"]=round(grp["RelSpeed"].mean(),1)
        for col,alias in [("SpinRate","Avg Spin"),("InducedVertBreak","Avg IVB"),("HorzBreak","Avg HB")]:
            r[alias]=round(grp[col].mean(),1) if col in grp.columns else np.nan
        if "PitchCall" in grp.columns:
            pc=grp["PitchCall"].astype(str).str.lower()
            sw=(pc.isin({"strikeswinging","foulball","foulballfieldable","foulballnotfieldable","inplay"})).sum()
            wh=(pc=="strikeswinging").sum()
            r["Whiff %"]=safe_pct(wh,max(sw,1))
        rows.append(r)
    out=pd.DataFrame(rows)
    if out.empty: return out
    out["_fb"]=out["Pitch Type"].str.lower().str.contains("fastball").astype(int)
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
        rows.append({"Pitch Type":pt,"Count":n,
                     "Zone %":safe_pct(in_z,n),"Swing %":safe_pct(sw,n),
                     "Contact %":safe_pct(ct,max(sw,1)),
                     "Chase %":safe_pct(max(0,sw-ct),max(n-in_z,1)),
                     "Whiff %":safe_pct(wh,max(sw,1))})
    return pd.DataFrame(rows).sort_values("Count",ascending=False).reset_index(drop=True)

def build_count_leverage(df):
    """Pitcher performance broken down by count situation."""
    if "Count" not in df.columns or "PitchCall" not in df.columns: return pd.DataFrame()
    HITTER_COUNTS={"3-0","3-1","2-0","1-0"}; PITCHER_COUNTS={"0-2","1-2","2-2"}
    def ctx(c):
        if c in HITTER_COUNTS: return "Hitter's Count"
        if c in PITCHER_COUNTS: return "Pitcher's Count"
        return "Even Count"
    df=df.copy(); df["CountCtx"]=df["Count"].apply(ctx)
    WHIFF={"StrikeSwinging"}; SWING={"StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    rows=[]
    for ctx_lbl,grp in df.groupby("CountCtx"):
        pc=grp["PitchCall"].astype(str); n=len(grp)
        sw=pc.isin(SWING).sum(); wh=pc.isin(WHIFF).sum()
        rows.append({"Context":ctx_lbl,"Pitches":n,
                     "Swing %":safe_pct(sw,n),"Whiff %":safe_pct(wh,max(sw,1))})
    return pd.DataFrame(rows).set_index("Context")

def plot_pitch_locations(df,name):
    fig,ax=plt.subplots(figsize=(5.2,5.8)); act(fig,[ax])
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    for idx,(pt,g) in enumerate(loc.groupby("TaggedPitchType") if not loc.empty else []):
        ax.scatter(g["PlateLocSide"],g["PlateLocHeight"],label=pt,
                   color=PITCH_PALETTE[idx%len(PITCH_PALETTE)],
                   alpha=0.80,s=44,edgecolors="white" if IS_DARK else "#00000022",linewidths=0.5,zorder=6)
    if loc.empty:
        ax.text(.5,.5,"No location data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
    draw_sz(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Height (ft)")
    cht(ax,"Pitch Locations",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
    ax.set_aspect("equal",adjustable="box"); fig.tight_layout(pad=1.2); return fig

def plot_hot_zone(df,name):
    fig,ax=plt.subplots(figsize=(5.2,5.8)); act(fig,[ax])
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    if len(loc)>=5:
        try:
            sns.kdeplot(data=loc,x="PlateLocSide",y="PlateLocHeight",fill=True,
                        cmap="hot" if IS_DARK else "YlOrRd",alpha=0.80,levels=14,thresh=0.03,ax=ax)
        except Exception: pass
    else:
        ax.text(.5,.5,"Need ≥ 5 pitches",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
    draw_sz(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Height (ft)")
    cht(ax,"Hot Zone (Density)",sub=name)
    ax.set_aspect("equal",adjustable="box"); fig.tight_layout(pad=1.2); return fig

def plot_velocity_tendency(df,name):
    fig,ax=plt.subplots(figsize=(11,3.8)); act(fig,[ax])
    vel=df.dropna(subset=["RelSpeed","Date"]) if "RelSpeed" in df.columns else pd.DataFrame()
    if vel.empty:
        ax.text(.5,.5,"No velocity data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    for idx,(pt,g) in enumerate(vel.groupby("TaggedPitchType")):
        daily=g.sort_values("Date").groupby("Date")["RelSpeed"].agg(["mean","std"]).reset_index()
        daily.columns=["Date","mean","std"]; daily["std"]=daily["std"].fillna(0)
        color=PITCH_PALETTE[idx%len(PITCH_PALETTE)]
        ax.fill_between(daily["Date"],daily["mean"]-daily["std"],daily["mean"]+daily["std"],alpha=0.10,color=color)
        ax.plot(daily["Date"],daily["mean"],label=pt,color=color,lw=2.0,marker="o",ms=4.5,alpha=0.95,zorder=5)
        if not daily.empty:
            last=daily.iloc[-1]
            ax.annotate(f'{last["mean"]:.1f}',(last["Date"],last["mean"]),
                        xytext=(4,4),textcoords="offset points",fontsize=7,color=color,fontweight="bold")
    ax.set_xlabel("Date"); ax.set_ylabel("Avg Velocity (mph)")
    cht(ax,"Velocity Tendency",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
    fig.autofmt_xdate(rotation=28,ha="right"); fig.tight_layout(pad=1.2); return fig

def plot_movement_profile(df,name):
    fig,ax=plt.subplots(figsize=(6.2,5.8)); act(fig,[ax])
    needed={"HorzBreak","InducedVertBreak"}
    if not needed.issubset(df.columns):
        ax.text(.5,.5,"No movement data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    sub=df.dropna(subset=["HorzBreak","InducedVertBreak"])
    for idx,(pt,g) in enumerate(sub.groupby("TaggedPitchType")):
        x,y,n=g["HorzBreak"].mean(),g["InducedVertBreak"].mean(),len(g)
        color=PITCH_PALETTE[idx%len(PITCH_PALETTE)]
        ax.scatter(g["HorzBreak"],g["InducedVertBreak"],color=color,alpha=0.08,s=9,edgecolors="none",zorder=3)
        ax.scatter(x,y,s=max(n*4,80),color=color,alpha=0.88,
                   edgecolors="white" if IS_DARK else "#00000033",linewidths=1.0,zorder=6)
        ax.annotate(f"{pt}\n(n={n})",(x,y),xytext=(7,5),textcoords="offset points",
                    fontsize=7.5,color=color,fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2",fc=C_CARD,ec="none",alpha=0.7))
    ax.axhline(0,color=C_SPINE,lw=1.0,alpha=0.8,zorder=2)
    ax.axvline(0,color=C_SPINE,lw=1.0,alpha=0.8,zorder=2)
    for txt,kw in [("Rise / Arm-side",(0.82,0.95)),("Rise / Glove-side",(0.18,0.95)),
                   ("Drop / Arm-side",(0.82,0.05)),("Drop / Glove-side",(0.18,0.05))]:
        ax.text(*kw,txt,transform=ax.transAxes,ha="center",color=C_MUTE,fontsize=7,alpha=0.5)
    ax.set_xlabel("Horizontal Break (in) — Arm side →")
    ax.set_ylabel("Induced Vert Break (in) — Rise →")
    cht(ax,"Movement Profile",sub=name); fig.tight_layout(pad=1.2); return fig

def plot_release_point(df,name):
    fig,ax=plt.subplots(figsize=(5.2,5.0)); act(fig,[ax])
    needed={"RelSide","RelHeight"}
    if not needed.issubset(df.columns) or df[list(needed)].dropna().empty:
        ax.text(.5,.5,"No release-point data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    sub=df.dropna(subset=["RelSide","RelHeight"])
    try:
        sns.kdeplot(data=sub,x="RelSide",y="RelHeight",fill=True,
                    cmap="Blues" if not IS_DARK else "YlOrBr",alpha=0.22,levels=7,thresh=0.06,ax=ax)
    except Exception: pass
    for idx,(pt,g) in enumerate(sub.groupby("TaggedPitchType")):
        color=PITCH_PALETTE[idx%len(PITCH_PALETTE)]
        ax.scatter(g["RelSide"],g["RelHeight"],label=pt,color=color,alpha=0.60,s=20,edgecolors="none",zorder=5)
        ax.scatter(g["RelSide"].mean(),g["RelHeight"].mean(),color=color,s=90,marker="+",linewidths=2.0,zorder=7)
    ax.set_xlabel("Release Side (ft)"); ax.set_ylabel("Release Height (ft)")
    cht(ax,"Release Point",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
    fig.tight_layout(pad=1.2); return fig

# ══════════════════════════════════════════════════════════════════════════════
# HITTING ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

def build_play_result_table(df):
    """Count of each play outcome."""
    if "PlayResult" not in df.columns: return pd.DataFrame()
    counts=df["PlayResult"].value_counts().reset_index()
    counts.columns=["Result","Count"]
    counts=counts[counts["Result"]!="—"]
    counts["% of PAs"]=counts["Count"].apply(lambda x:safe_pct(x,len(df)))
    return counts.reset_index(drop=True)

def compute_plate_discipline_batter(df):
    """Batter discipline dict — correctly calculates K% from PlayResult."""
    if "PitchCall" not in df.columns: return {}
    pc=df["PitchCall"].astype(str)
    ZONE={"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    SWING={"StrikeSwinging","FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    CONTACT={"FoulBall","FoulBallFieldable","FoulBallNotFieldable","InPlay"}
    WHIFF={"StrikeSwinging"}
    BB_CALLS={"BallCalled","HitByPitch","IntentionalBall"}
    n=len(df); in_z=pc.isin(ZONE).sum(); sw=pc.isin(SWING).sum()
    cont=pc.isin(CONTACT).sum(); whiff=pc.isin(WHIFF).sum()
    # K% — use PlayResult first (more accurate), fall back to PitchCall
    kk=0
    if "PlayResult" in df.columns:
        kk=(df["PlayResult"].astype(str).str.strip()=="K").sum()
    if kk==0:
        kk=pc.isin({"StrikeoutSwinging","StrikeoutCalled"}).sum()
    bb=pc.isin(BB_CALLS).sum()
    return {
        "Zone %":safe_pct(in_z,n), "Swing %":safe_pct(sw,n),
        "Contact %":safe_pct(cont,max(sw,1)),
        "Chase %":safe_pct(max(0,sw-cont),max(n-in_z,1)),
        "Whiff %":safe_pct(whiff,max(sw,1)),
        "K %":safe_pct(kk,n), "BB %":safe_pct(bb,n),
    }

def build_hitting_monthly(df):
    df=df.copy(); df["YearMonth"]=df["Date"].dt.to_period("M")
    rows=[]
    for period,grp in df.groupby("YearMonth"):
        r={"Month":str(period),"Pitches":len(grp)}
        for col,(mx,av) in [("ExitSpeed",("Max EV","Avg EV")),
                             ("Angle",("Max LA","Avg LA")),
                             ("Distance",("Max Dist","Avg Dist"))]:
            if col in df.columns:
                vals=grp[col].dropna()
                r[mx]=round(vals.max(),1) if not vals.empty else np.nan
                r[av]=round(vals.mean(),1) if not vals.empty else np.nan
        if "ExitSpeed" in df.columns:
            ev=grp["ExitSpeed"].dropna()
            r["HH %"]=safe_pct((ev>=95).sum(),len(ev))
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrel=((grp["ExitSpeed"].fillna(0)>=98)&
                    (grp["Angle"].fillna(-999)>=8)&
                    (grp["Angle"].fillna(-999)<=32)).sum()
            r["Barrel %"]=safe_pct(barrel,len(grp))
        if "PlayResult" in df.columns:
            r["K %"]=safe_pct((grp["PlayResult"].astype(str)=="K").sum(),len(grp))
        rows.append(r)
    out=pd.DataFrame(rows)
    return out.sort_values("Month",ascending=False).reset_index(drop=True) if not out.empty else out

def build_split_table(df, split_col="PitcherThrows"):
    """Discipline + quality split by pitcher handedness."""
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

def plot_spray_chart(df,name):
    fig,ax=plt.subplots(figsize=(5.8,5.8)); act(fig,[ax])
    ax.set_facecolor("#1a3a1a" if IS_DARK else "#d4edda")
    spray=df.dropna(subset=["Distance","Bearing"]).copy()
    if spray.empty:
        ax.text(.5,.5,"No spray data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        cht(ax,"Spray Chart",sub=name); fig.tight_layout(); return fig
    brad=np.deg2rad(spray["Bearing"])
    spray["Hit_X"]=spray["Distance"]*np.sin(brad)
    spray["Hit_Y"]=spray["Distance"]*np.cos(brad)
    lc="#8b6914" if IS_DARK else "#5d4037"; ac="#4a5e3a" if IS_DARK else "#388e3c"
    for sign in [1,-1]:
        ax.plot([0,sign*420*np.sin(np.deg2rad(45))],[0,420*np.cos(np.deg2rad(45))],color=lc,lw=2.0,alpha=0.8)
    ang=np.linspace(-45,45,300)
    for r,lw2,ls in [(230,1.0,"--"),(330,1.0,"--"),(400,1.5,"-")]:
        ax.plot(r*np.sin(np.deg2rad(ang)),r*np.cos(np.deg2rad(ang)),color=ac,lw=lw2,alpha=0.5,linestyle=ls)
        ax.text(r*np.sin(np.deg2rad(44)),r*np.cos(np.deg2rad(44)),f"{r} ft",fontsize=6.5,color=ac,alpha=0.65)
    bd=90*np.sqrt(2)/2
    ax.plot([0,bd,0,-bd,0],[0,bd,2*bd,bd,0],color="#c8a850",lw=1.2,alpha=0.7)
    has_ev="ExitSpeed" in spray.columns and spray["ExitSpeed"].notna().any()
    sc=ax.scatter(spray["Hit_X"],spray["Hit_Y"],
                  c=spray["ExitSpeed"] if has_ev else ACCENT,
                  cmap="RdYlGn" if has_ev else None,
                  s=48,alpha=0.88,edgecolors="white" if IS_DARK else "#00000033",
                  linewidths=0.4,zorder=5,vmin=60,vmax=110)
    if has_ev:
        cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.68)
        cb.set_label("Exit Speed (mph)",color=C_MUTE,fontsize=8)
        cb.ax.yaxis.set_tick_params(color=C_MUTE,labelcolor=C_MUTE)
        cb.outline.set_edgecolor(C_SPINE)
    ax.set_xlim(-360,360); ax.set_ylim(-20,460)
    ax.set_xlabel("Horizontal (ft)"); ax.set_ylabel("Vertical (ft)")
    cht(ax,"Spray Chart",sub=name); ax.set_aspect("equal",adjustable="box")
    fig.tight_layout(pad=1.2); return fig

def plot_damage_zone(df,name):
    fig,ax=plt.subplots(figsize=(5.2,5.8)); act(fig,[ax])
    loc=df.dropna(subset=["PlateLocSide","PlateLocHeight"])
    if not loc.empty:
        has_ev="ExitSpeed" in loc.columns and loc["ExitSpeed"].notna().any()
        try:
            sns.kdeplot(data=loc,x="PlateLocSide",y="PlateLocHeight",fill=False,
                        color=C_MUTE,alpha=0.22,levels=5,thresh=0.12,ax=ax,zorder=3)
        except Exception: pass
        sc=ax.scatter(loc["PlateLocSide"],loc["PlateLocHeight"],
                      c=loc["ExitSpeed"] if has_ev else ACCENT,
                      cmap="RdYlGn" if has_ev else None,
                      s=40,alpha=0.82,edgecolors="white" if IS_DARK else "#00000022",
                      linewidths=0.4,zorder=6,vmin=60,vmax=110)
        if has_ev:
            cb=fig.colorbar(sc,ax=ax,pad=0.02,shrink=0.68)
            cb.set_label("Exit Speed (mph)",color=C_MUTE,fontsize=8)
            cb.ax.yaxis.set_tick_params(color=C_MUTE,labelcolor=C_MUTE)
            cb.outline.set_edgecolor(C_SPINE)
    else:
        ax.text(.5,.5,"No location data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
    draw_sz(ax); draw_plate(ax)
    ax.set_xlim(-2.5,2.5); ax.set_ylim(0.3,5.0)
    ax.set_xlabel("Plate Side (ft)"); ax.set_ylabel("Height (ft)")
    cht(ax,"Damage Zone",sub=name); ax.set_aspect("equal",adjustable="box")
    fig.tight_layout(pad=1.2); return fig

def plot_ev_distribution(df,name):
    fig,ax=plt.subplots(figsize=(6.0,3.8)); act(fig,[ax])
    ev=df["ExitSpeed"].dropna() if "ExitSpeed" in df.columns else pd.Series(dtype=float)
    if ev.empty:
        ax.text(.5,.5,"No EV data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    _,bins,patches_list=ax.hist(ev,bins=22,color=BLUE,alpha=0.75,edgecolor=C_BG,linewidth=0.5)
    for p,left in zip(patches_list,bins[:-1]):
        if left>=95: p.set_facecolor(RED); p.set_alpha(0.85)
    ax.axvline(ev.mean(),color=ACCENT,lw=2.0,linestyle="--",zorder=6,label=f"Avg {ev.mean():.1f}")
    ax.axvline(95,color=RED,lw=1.5,linestyle=":",zorder=6,label="Hard Hit ≥ 95")
    hh=(ev>=95).sum()
    ax.text(0.97,0.93,f"HH: {hh} ({safe_pct(hh,len(ev))}%)",transform=ax.transAxes,
            ha="right",va="top",color=RED,fontsize=8.5,fontweight="bold")
    ax.set_xlabel("Exit Velocity (mph)"); ax.set_ylabel("Pitches")
    cht(ax,"Exit Velocity Distribution",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
    fig.tight_layout(pad=1.2); return fig

def plot_la_distribution(df,name):
    fig,ax=plt.subplots(figsize=(6.0,3.8)); act(fig,[ax])
    la=df["Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    if la.empty:
        ax.text(.5,.5,"No LA data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    _,bins,patches_list=ax.hist(la,bins=22,color=GREEN,alpha=0.72,edgecolor=C_BG,linewidth=0.5)
    for p,left,right in zip(patches_list,bins[:-1],bins[1:]):
        if left>=8 and right<=32: p.set_facecolor(ACCENT); p.set_alpha(0.9)
    ax.axvspan(8,32,alpha=0.07,color=ACCENT,label="Barrel zone 8–32°",zorder=1)
    ax.axvline(la.mean(),color=ACCENT,lw=2.0,linestyle="--",zorder=6,label=f"Avg {la.mean():.1f}°")
    barrel=((la>=8)&(la<=32)).sum()
    ax.text(0.97,0.93,f"Barrel zone: {barrel} ({safe_pct(barrel,len(la))}%)",
            transform=ax.transAxes,ha="right",va="top",color=ACCENT,fontsize=8.5,fontweight="bold")
    ax.set_xlabel("Launch Angle (°)"); ax.set_ylabel("Pitches")
    cht(ax,"Launch Angle Distribution",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
    fig.tight_layout(pad=1.2); return fig

def plot_ev_la_scatter(df,name):
    """EV × LA quality scatter — coloured by hit result."""
    fig,ax=plt.subplots(figsize=(6.5,4.2)); act(fig,[ax])
    needed={"ExitSpeed","Angle"}
    sub=df.dropna(subset=list(needed)).copy() if needed.issubset(df.columns) else pd.DataFrame()
    if sub.empty:
        ax.text(.5,.5,"No EV/LA data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    RESULT_COLORS={"HR":RED,"2B":BLUE,"3B":PURPLE,"1B":GREEN,"K":C_MUTE,"BB":TEAL,"Out":C_MUTE}
    if "PlayResult" in sub.columns:
        for res,color in RESULT_COLORS.items():
            pts=sub[sub["PlayResult"]==res]
            if len(pts):
                ax.scatter(pts["ExitSpeed"],pts["Angle"],color=color,alpha=0.60,
                           s=22,label=res,edgecolors="none",zorder=5)
        others=sub[~sub["PlayResult"].isin(RESULT_COLORS)]
        if len(others):
            ax.scatter(others["ExitSpeed"],others["Angle"],color=C_MUTE,alpha=0.25,s=14,edgecolors="none",zorder=3)
    else:
        ax.scatter(sub["ExitSpeed"],sub["Angle"],color=BLUE,alpha=0.50,s=20,edgecolors="none",zorder=4)
    # Barrel zone box
    ax.add_patch(patches.Rectangle((98,8),20,24,lw=1.5,edgecolor=ACCENT,
                                   facecolor=ACCENT,alpha=0.07,linestyle="--",zorder=2))
    ax.text(108.5,20,"Barrel\nZone",ha="center",va="center",color=ACCENT,fontsize=7.5,fontweight="bold",alpha=0.7)
    ax.set_xlabel("Exit Velocity (mph)"); ax.set_ylabel("Launch Angle (°)")
    cht(ax,"Hit Quality — EV × Launch Angle",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,
              labelcolor=C_TEXT,ncol=3,loc="upper left")
    fig.tight_layout(pad=1.2); return fig

def plot_rolling_ev(df,name,window=7):
    fig,ax=plt.subplots(figsize=(11,3.5)); act(fig,[ax])
    if "ExitSpeed" not in df.columns or df["ExitSpeed"].dropna().empty:
        ax.text(.5,.5,"No EV data",ha="center",va="center",color=C_MUTE,transform=ax.transAxes)
        fig.tight_layout(); return fig
    daily=(df.dropna(subset=["ExitSpeed","Date"]).groupby("Date")["ExitSpeed"]
             .agg(["mean","std","count"]).reset_index().sort_values("Date"))
    daily.columns=["Date","mean","std","cnt"]
    daily["std"]=daily["std"].fillna(0)
    daily["roll"]=daily["mean"].rolling(window,min_periods=1).mean()
    daily["rsd"]=daily["std"].rolling(window,min_periods=1).mean()
    ax.fill_between(daily["Date"],daily["roll"]-daily["rsd"],daily["roll"]+daily["rsd"],
                    alpha=0.10,color=BLUE)
    ax.fill_between(daily["Date"],daily["mean"],alpha=0.07,color=BLUE)
    ax.plot(daily["Date"],daily["mean"],color=BLUE,lw=1.0,alpha=0.5,marker="o",ms=3.5,label="Daily Avg")
    ax.plot(daily["Date"],daily["roll"],color=ACCENT,lw=2.2,label=f"{window}-day Rolling")
    ax.axhline(95,color=RED,lw=1.2,linestyle=":",alpha=0.7,label="Hard Hit (95)")
    if not daily.empty:
        last=daily.iloc[-1]
        ax.annotate(f'{last["roll"]:.1f}',(last["Date"],last["roll"]),
                    xytext=(5,6),textcoords="offset points",fontsize=8,color=ACCENT,fontweight="bold")
    ax.set_xlabel("Date"); ax.set_ylabel("Exit Speed (mph)")
    cht(ax,f"Rolling {window}-Day Avg Exit Speed",sub=name)
    ax.legend(fontsize=7.5,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
    fig.autofmt_xdate(rotation=28,ha="right"); fig.tight_layout(pad=1.2); return fig

# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT — REDESIGNED
# ══════════════════════════════════════════════════════════════════════════════
def _pdf_cover(pdf, player_name, date_range, dashboard_type):
    fig=plt.figure(figsize=(11,8.5)); fig.patch.set_facecolor("#0d1117")
    ax=fig.add_subplot(111); ax.axis("off"); ax.set_facecolor("#0d1117")
    # Gold accent bar
    ax.add_patch(patches.Rectangle((0,0.78),1,0.005,transform=ax.transAxes,
                                    fc=ACCENT,ec="none",zorder=5))
    ax.text(0.5,0.88,"⚾  TRACKMAN ANALYTICS",transform=ax.transAxes,
            ha="center",va="center",fontsize=22,fontweight="900",color=ACCENT,
            fontfamily="monospace")
    ax.text(0.5,0.72,player_name,transform=ax.transAxes,
            ha="center",va="center",fontsize=30,fontweight="bold",color=CHART_TEXT_DARK)
    ax.text(0.5,0.62,dashboard_type,transform=ax.transAxes,
            ha="center",va="center",fontsize=14,color=CHART_MUTED_DARK)
    ax.text(0.5,0.52,f"Date Range: {date_range}",transform=ax.transAxes,
            ha="center",va="center",fontsize=11,color=CHART_MUTED_DARK)
    ax.add_patch(patches.Rectangle((0,0.30),1,0.005,transform=ax.transAxes,
                                    fc=ACCENT,alpha=0.3,ec="none"))
    ax.text(0.5,0.22,"Generated by Trackman Analytics Dashboard v4.0",
            transform=ax.transAxes,ha="center",va="center",
            fontsize=9,color=CHART_MUTED_DARK,alpha=0.6)
    pdf.savefig(fig,bbox_inches="tight",facecolor="#0d1117"); plt.close(fig)

def _pdf_table_page(pdf, df, title, subtitle=""):
    fh=max(4,min(len(df)*0.55+2.0,10))
    fig=plt.figure(figsize=(13,fh)); fig.patch.set_facecolor("#0d1117")
    ax=fig.add_subplot(111); ax.axis("off"); ax.set_facecolor("#0d1117")
    # Section header
    ax.add_patch(patches.Rectangle((0,0.93),1,0.07,transform=ax.transAxes,
                                    fc="#1c2230",ec="none"))
    ax.text(0.02,0.965,title,transform=ax.transAxes,va="center",
            fontsize=12,fontweight="bold",color=ACCENT)
    if subtitle:
        ax.text(0.98,0.965,subtitle,transform=ax.transAxes,va="center",ha="right",
                fontsize=9,color=CHART_MUTED_DARK)
    cols=list(df.columns); data=df.fillna("—").values.tolist()
    tbl=ax.table(cellText=data,colLabels=cols,loc="center",cellLoc="center",
                 bbox=[0,0.0,1,0.88])
    tbl.auto_set_font_size(False); tbl.set_fontsize(8.5)
    tbl.auto_set_column_width(col=list(range(len(cols))))
    # Header row
    for j in range(len(cols)):
        c=tbl[0,j]; c.set_facecolor(ACCENT); c.set_text_props(color="#000",fontweight="bold")
        c.set_edgecolor("#0d1117"); c.set_linewidth(0.5)
    # Data rows with alternating shading
    for i in range(1,len(data)+1):
        for j in range(len(cols)):
            c=tbl[i,j]
            c.set_facecolor("#1c2230" if i%2==0 else "#161b22")
            c.set_text_props(color=CHART_TEXT_DARK)
            c.set_edgecolor("#0d1117"); c.set_linewidth(0.5)
    tbl.scale(1,1.5)
    fig.tight_layout()
    pdf.savefig(fig,bbox_inches="tight",facecolor="#0d1117"); plt.close(fig)

def _pdf_two_charts(pdf, fig1, fig2, label1="", label2=""):
    """Place two charts side-by-side on one PDF page."""
    fig=plt.figure(figsize=(13,6)); fig.patch.set_facecolor("#0d1117")
    gs=gridspec.GridSpec(1,2,figure=fig,wspace=0.08)
    for slot,src_fig,lbl in [(0,fig1,label1),(1,fig2,label2)]:
        ax_new=fig.add_subplot(gs[slot])
        ax_new.set_facecolor("#0d1117"); ax_new.axis("off")
        if src_fig is not None:
            src_canvas=src_fig.canvas; src_canvas.draw()
            buf=np.frombuffer(src_canvas.tostring_rgb(),dtype=np.uint8)
            buf=buf.reshape(src_fig.canvas.get_width_height()[::-1]+(3,))
            ax_new.imshow(buf,aspect="auto")
            if lbl: ax_new.set_title(lbl,color=CHART_MUTED_DARK,fontsize=9,pad=4)
    pdf.savefig(fig,bbox_inches="tight",facecolor="#0d1117"); plt.close(fig)

def _pdf_single_chart(pdf, src_fig, label=""):
    fig=plt.figure(figsize=(13,5.5)); fig.patch.set_facecolor("#0d1117")
    ax=fig.add_subplot(111); ax.set_facecolor("#0d1117"); ax.axis("off")
    if src_fig is not None:
        src_fig.canvas.draw()
        buf=np.frombuffer(src_fig.canvas.tostring_rgb(),dtype=np.uint8)
        buf=buf.reshape(src_fig.canvas.get_width_height()[::-1]+(3,))
        ax.imshow(buf,aspect="auto")
        if label: ax.set_title(label,color=CHART_MUTED_DARK,fontsize=9,pad=4)
    pdf.savefig(fig,bbox_inches="tight",facecolor="#0d1117"); plt.close(fig)

def export_pitching_pdf(pitcher, summary_df, disc_df, count_df,
                         fig_loc, fig_kde, fig_vel, fig_mov, fig_rel, date_range):
    buf=io.BytesIO()
    with PdfPages(buf) as pdf:
        _pdf_cover(pdf,pitcher,date_range,"Pitching Report")
        if not summary_df.empty: _pdf_table_page(pdf,summary_df,"Pitch Arsenal Summary",pitcher)
        if not disc_df.empty:    _pdf_table_page(pdf,disc_df,"Pitch Discipline",pitcher)
        if not count_df.empty:   _pdf_table_page(pdf,count_df.reset_index(),"Count-Leverage Analysis",pitcher)
        _pdf_two_charts(pdf,fig_loc,fig_kde,"Pitch Locations","Hot Zone")
        _pdf_single_chart(pdf,fig_vel,"Velocity Tendency")
        _pdf_two_charts(pdf,fig_mov,fig_rel,"Movement Profile","Release Point")
    buf.seek(0); return buf.read()

def export_hitting_pdf(batter, monthly_df, disc_dict, result_df, split_df,
                        fig_spray, fig_dmg, fig_ev, fig_la, fig_ev_la, fig_roll, date_range):
    buf=io.BytesIO()
    with PdfPages(buf) as pdf:
        _pdf_cover(pdf,batter,date_range,"Hitting Report")
        if not monthly_df.empty: _pdf_table_page(pdf,monthly_df,"Monthly Progression",batter)
        if disc_dict:
            disc_df=pd.DataFrame([disc_dict]); _pdf_table_page(pdf,disc_df,"Plate Discipline",batter)
        if not result_df.empty:  _pdf_table_page(pdf,result_df,"Play Results",batter)
        if not split_df.empty:   _pdf_table_page(pdf,split_df,"vs RHP / vs LHP Splits",batter)
        _pdf_two_charts(pdf,fig_spray,fig_dmg,"Spray Chart","Damage Zone")
        _pdf_two_charts(pdf,fig_ev,fig_la,"Exit Velo Distribution","Launch Angle Distribution")
        _pdf_single_chart(pdf,fig_ev_la,"Hit Quality — EV × LA")
        _pdf_single_chart(pdf,fig_roll,"Rolling Avg Exit Speed")
    buf.seek(0); return buf.read()

# ══════════════════════════════════════════════════════════════════════════════
# RENDER: PITCHING DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def render_pitching(df, master_df):
    st.markdown('<div class="sh">⚾ Pitching Dashboard</div>',unsafe_allow_html=True)
    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column found."); return
    pitchers=sorted(df["Pitcher"].dropna().unique())
    selected=player_search_select(pitchers,"Select Pitcher","pitcher")
    pf=df[df["Pitcher"]==selected].copy(); n=len(pf)
    if n<15: st.warning(f"⚠️ **{selected}** — only **{n}** pitches (min: 15).")
    avg_v=pf["RelSpeed"].mean()  if "RelSpeed"  in pf.columns else np.nan
    max_v=pf["RelSpeed"].max()   if "RelSpeed"  in pf.columns else np.nan
    avg_sp=pf["SpinRate"].mean() if "SpinRate"  in pf.columns else np.nan
    ext=pf["Extension"].mean()   if "Extension" in pf.columns else np.nan
    c1,c2,c3,c4,c5=st.columns(5)
    with c1: st.metric("Total Pitches",f"{n:,}")
    with c2: st.metric("Avg Velocity",fmt(avg_v," mph"),delta=f"Max {max_v:.1f}" if not np.isnan(max_v) else None)
    with c3: st.metric("Avg Spin Rate",fmt(avg_sp," rpm",0))
    with c4: st.metric("Extension",fmt(ext," ft"))
    with c5: st.metric("Pitch Types",str(pf["TaggedPitchType"].nunique()))
    st.markdown("<br>",unsafe_allow_html=True)

    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs([
        "📋 Summary","📍 Locations","📈 Velocity & Movement",
        "🎯 Release Point","🏟️ Stadium","📊 League Avg"])

    with tab1:
        st.markdown('<div class="sh">📋 Pitch Arsenal</div>',unsafe_allow_html=True)
        summary_df=build_pitch_summary(pf)
        st.dataframe(summary_df,use_container_width=True,hide_index=True)
        csv_dl(summary_df,f"{selected}_summary.csv")
        st.markdown('<div class="sh">🎯 Pitch Discipline</div>',unsafe_allow_html=True)
        disc_df=compute_pitch_discipline(pf)
        if disc_df.empty: st.info("PitchCall column required.")
        else:
            st.dataframe(disc_df,use_container_width=True,hide_index=True)
            csv_dl(disc_df,f"{selected}_discipline.csv")
        st.markdown('<div class="sh">📊 Count Leverage</div>',unsafe_allow_html=True)
        count_df=build_count_leverage(pf)
        if count_df.empty: st.info("Count data not available.")
        else: st.dataframe(count_df,use_container_width=True)

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
        fig_rel=plot_release_point(pf,selected)
        st.pyplot(fig_rel,use_container_width=True)

    with tab5:
        st.markdown('<div class="sh">🏟️ Stadium Performance</div>',unsafe_allow_html=True)
        if "Stadium" not in pf.columns:
            st.info("No 'Stadium' column found in data.")
        else:
            player_avg_v=pf["RelSpeed"].mean() if "RelSpeed" in pf.columns else None
            fig_stad=plot_player_stadium_trend(df,selected,"Pitcher","RelSpeed","Avg Velocity (mph)")
            st.pyplot(fig_stad,use_container_width=True)
            tbl_stad=build_stadium_table(pf,"RelSpeed","Avg Velo")
            if not tbl_stad.empty:
                st.dataframe(tbl_stad,use_container_width=True,hide_index=True)

    with tab6:
        st.markdown('<div class="sh">📊 League Pitching Averages</div>',unsafe_allow_html=True)
        lg=build_league_pitching_avg(master_df)
        if lg.empty: st.info("Not enough data for league averages.")
        else:
            st.dataframe(lg,use_container_width=True,hide_index=True)
            csv_dl(lg,"league_pitching_avg.csv","⬇️ Download League Avg CSV")

    st.markdown('<div class="sh">📤 Export</div>',unsafe_allow_html=True)
    if "summary_df" not in locals(): summary_df=build_pitch_summary(pf)
    if "disc_df"    not in locals(): disc_df=compute_pitch_discipline(pf)
    if "count_df"   not in locals(): count_df=build_count_leverage(pf)
    if "fig_loc"    not in locals(): fig_loc=plot_pitch_locations(pf,selected)
    if "fig_kde"    not in locals(): fig_kde=plot_hot_zone(pf,selected)
    if "fig_vel"    not in locals(): fig_vel=plot_velocity_tendency(pf,selected)
    if "fig_mov"    not in locals(): fig_mov=plot_movement_profile(pf,selected)
    if "fig_rel"    not in locals(): fig_rel=plot_release_point(pf,selected)
    dr=f"{df['Date'].min().date()} → {df['Date'].max().date()}" if df["Date"].notna().any() else "All dates"
    ec1,ec2=st.columns(2)
    with ec1:
        pdf_b=export_pitching_pdf(selected,summary_df,
                                   disc_df if not disc_df.empty else pd.DataFrame(),
                                   count_df if not count_df.empty else pd.DataFrame(),
                                   fig_loc,fig_kde,fig_vel,fig_mov,fig_rel,dr)
        st.download_button("⬇️ Download PDF Report",pdf_b,f"{selected}_pitching.pdf","application/pdf")
    with ec2:
        csv_dl(pf,f"{selected}_raw.csv","⬇️ Download Raw CSV")
    for f in [fig_loc,fig_kde,fig_vel,fig_mov,fig_rel]: plt.close(f)

# ══════════════════════════════════════════════════════════════════════════════
# RENDER: HITTING DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def render_hitting(df, master_df):
    st.markdown('<div class="sh">🏏 Hitting Dashboard</div>',unsafe_allow_html=True)
    if "Batter" not in df.columns or df["Batter"].dropna().empty:
        st.error("No 'Batter' column found."); return
    batters=sorted(df["Batter"].dropna().unique())
    selected=player_search_select(batters,"Select Batter","batter")
    bdf=df[df["Batter"]==selected].copy(); n=len(bdf)
    if n<15: st.warning(f"⚠️ **{selected}** — only **{n}** pitches seen (min: 15).")

    avg_ev=bdf["ExitSpeed"].mean()  if "ExitSpeed" in bdf.columns else np.nan
    max_ev=bdf["ExitSpeed"].max()   if "ExitSpeed" in bdf.columns else np.nan
    avg_la=bdf["Angle"].mean()      if "Angle"     in bdf.columns else np.nan
    avg_dis=bdf["Distance"].mean()  if "Distance"  in bdf.columns else np.nan
    hh_rate=barrel_rate=0.0
    if "ExitSpeed" in bdf.columns:
        ev_s=bdf["ExitSpeed"].dropna()
        hh_rate=safe_pct((ev_s>=95).sum(),len(ev_s))
    if "ExitSpeed" in bdf.columns and "Angle" in bdf.columns:
        barrel=((bdf["ExitSpeed"].fillna(0)>=98)&
                (bdf["Angle"].fillna(-999)>=8)&
                (bdf["Angle"].fillna(-999)<=32)).sum()
        barrel_rate=safe_pct(barrel,n)
    disc=compute_plate_discipline_batter(bdf)

    c1,c2,c3,c4,c5,c6=st.columns(6)
    with c1: st.metric("Pitches Seen",f"{n:,}")
    with c2: st.metric("Avg Exit Velo",fmt(avg_ev," mph"),delta=f"Max {max_ev:.1f}" if not np.isnan(max_ev) else None)
    with c3: st.metric("Avg Launch Angle",fmt(avg_la,"°"))
    with c4: st.metric("Avg Distance",fmt(avg_dis," ft",0))
    with c5: st.metric("Hard Hit %",f"{hh_rate:.1f}%")
    with c6: st.metric("Barrel %",f"{barrel_rate:.1f}%")
    st.markdown("<br>",unsafe_allow_html=True)

    # Discipline badges
    if disc:
        st.markdown('<div class="sh">🎯 Plate Discipline</div>',unsafe_allow_html=True)
        bcols=st.columns(len(disc))
        for col,(k,v) in zip(bcols,disc.items()):
            with col:
                st.markdown(f'<div class="stat-badge"><div class="val">{v}%</div>'
                            f'<div class="lbl">{k}</div></div>',unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)

    tab1,tab2,tab3,tab4,tab5,tab6,tab7=st.tabs([
        "📅 Monthly","🔄 vs RHP / LHP","📋 Play Results",
        "🗺️ Spray & Damage","📊 Distributions","🏟️ Stadium","📈 League"])

    with tab1:
        monthly_df=build_hitting_monthly(bdf)
        if monthly_df.empty: st.info("No monthly data.")
        else:
            st.dataframe(monthly_df,use_container_width=True,hide_index=True)
            csv_dl(monthly_df,f"{selected}_monthly.csv")

    with tab2:
        st.markdown('<div class="sh">🔄 Platoon Splits vs RHP / LHP</div>',unsafe_allow_html=True)
        split_df=build_split_table(bdf)
        if split_df.empty:
            st.info("PitcherThrows column required for platoon splits.")
        else:
            st.dataframe(split_df,use_container_width=True,hide_index=True)
            csv_dl(split_df,f"{selected}_splits.csv")
            # Side-by-side spray charts per handedness
            hands=bdf["PitcherThrows"].dropna().unique() if "PitcherThrows" in bdf.columns else []
            if len(hands)>=2:
                st.markdown('<div class="sh">Spray Chart by Pitcher Handedness</div>',unsafe_allow_html=True)
                cols_h=st.columns(len(hands))
                for col_h,hand in zip(cols_h,sorted(hands)):
                    with col_h:
                        sub_h=bdf[bdf["PitcherThrows"]==hand]
                        fig_h=plot_spray_chart(sub_h,f"{selected} vs {hand}")
                        st.pyplot(fig_h,use_container_width=True)
                        plt.close(fig_h)
                # Damage zone per handedness
                st.markdown('<div class="sh">Damage Zone by Pitcher Handedness</div>',unsafe_allow_html=True)
                cols_dh=st.columns(len(hands))
                for col_dh,hand in zip(cols_dh,sorted(hands)):
                    with col_dh:
                        sub_h=bdf[bdf["PitcherThrows"]==hand]
                        fig_dh=plot_damage_zone(sub_h,f"{selected} vs {hand}")
                        st.pyplot(fig_dh,use_container_width=True)
                        plt.close(fig_dh)

    with tab3:
        st.markdown('<div class="sh">📋 Play Result Breakdown</div>',unsafe_allow_html=True)
        result_df=build_play_result_table(bdf)
        if result_df.empty:
            st.info("PlayResult / KorBB column not found. Check column mapping.")
        else:
            st.dataframe(result_df,use_container_width=True,hide_index=True)
            csv_dl(result_df,f"{selected}_results.csv")
            # Quick bar chart of outcomes
            fig_res,ax_res=plt.subplots(figsize=(8,3.2))
            act(fig_res,[ax_res])
            result_colors_bar={
                "HR":RED,"3B":PURPLE,"2B":BLUE,"1B":GREEN,"K":ORANGE,
                "BB":TEAL,"Out":C_MUTE,"HBP":PINK,"FC":ACCENT,"Error":LIME}
            bar_colors=[result_colors_bar.get(r,C_MUTE) for r in result_df["Result"]]
            bars=ax_res.bar(result_df["Result"],result_df["Count"],color=bar_colors,
                           alpha=0.85,edgecolor=C_SPINE,linewidth=0.4,zorder=3)
            for bar,val in zip(bars,result_df["Count"]):
                ax_res.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.3,
                           str(val),ha="center",va="bottom",fontsize=8,color=C_TEXT,fontweight="bold")
            ax_res.set_xlabel("Outcome"); ax_res.set_ylabel("Count")
            cht(ax_res,"At-Bat Outcomes",sub=selected)
            fig_res.tight_layout(pad=1.2)
            st.pyplot(fig_res,use_container_width=True); plt.close(fig_res)

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
        st.markdown("<br>",unsafe_allow_html=True)
        fig_roll=plot_rolling_ev(bdf,selected)
        st.pyplot(fig_roll,use_container_width=True)

    with tab6:
        st.markdown('<div class="sh">🏟️ Stadium Development</div>',unsafe_allow_html=True)
        if "Stadium" not in bdf.columns:
            st.info("No 'Stadium' column found.")
        else:
            metric_pick=st.selectbox("Metric",["ExitSpeed","Angle","Distance"],key="stad_metric_hit")
            metric_labels={"ExitSpeed":"Avg Exit Velo (mph)","Angle":"Avg Launch Angle (°)","Distance":"Avg Distance (ft)"}
            fig_stad_h=plot_player_stadium_trend(df,selected,"Batter",metric_pick,metric_labels[metric_pick])
            st.pyplot(fig_stad_h,use_container_width=True)
            tbl_stad_h=build_stadium_table(bdf,metric_pick,metric_labels[metric_pick])
            if not tbl_stad_h.empty:
                st.dataframe(tbl_stad_h,use_container_width=True,hide_index=True)

    with tab7:
        st.markdown('<div class="sh">📈 League Hitting Averages</div>',unsafe_allow_html=True)
        lg_h=build_league_hitting_avg(master_df)
        if lg_h.empty: st.info("Not enough data.")
        else:
            st.dataframe(lg_h,use_container_width=True,hide_index=True)
            csv_dl(lg_h,"league_hitting_avg.csv","⬇️ Download League Avg CSV")
        # League EV distribution
        if "ExitSpeed" in master_df.columns:
            fig_lg_ev,ax_lg=plt.subplots(figsize=(10,3.2)); act(fig_lg_ev,[ax_lg])
            ev_all=master_df["ExitSpeed"].dropna()
            ev_player=bdf["ExitSpeed"].dropna() if "ExitSpeed" in bdf.columns else pd.Series(dtype=float)
            ax_lg.hist(ev_all,bins=28,color=C_MUTE,alpha=0.40,edgecolor=C_BG,linewidth=0.4,label="League",density=True)
            if not ev_player.empty:
                ax_lg.hist(ev_player,bins=20,color=ACCENT,alpha=0.70,edgecolor=C_BG,linewidth=0.4,
                           label=selected,density=True)
            ax_lg.axvline(ev_all.mean(),color=C_MUTE,lw=1.5,linestyle="--",label=f"League avg {ev_all.mean():.1f}")
            if not ev_player.empty:
                ax_lg.axvline(ev_player.mean(),color=ACCENT,lw=1.5,linestyle="--",
                              label=f"Player avg {ev_player.mean():.1f}")
            ax_lg.set_xlabel("Exit Velocity (mph)"); ax_lg.set_ylabel("Density")
            cht(ax_lg,"Player vs League — Exit Velocity Distribution",sub=selected)
            ax_lg.legend(fontsize=8,framealpha=0.45,edgecolor=C_SPINE,facecolor=C_CARD,labelcolor=C_TEXT)
            fig_lg_ev.tight_layout(pad=1.2)
            st.pyplot(fig_lg_ev,use_container_width=True); plt.close(fig_lg_ev)

    st.markdown('<div class="sh">📤 Export</div>',unsafe_allow_html=True)
    if "monthly_df"  not in locals(): monthly_df=build_hitting_monthly(bdf)
    if "result_df"   not in locals(): result_df=build_play_result_table(bdf)
    if "split_df"    not in locals(): split_df=build_split_table(bdf)
    if "fig_spray"   not in locals(): fig_spray=plot_spray_chart(bdf,selected)
    if "fig_dmg"     not in locals(): fig_dmg=plot_damage_zone(bdf,selected)
    if "fig_ev"      not in locals(): fig_ev=plot_ev_distribution(bdf,selected)
    if "fig_la"      not in locals(): fig_la=plot_la_distribution(bdf,selected)
    if "fig_ev_la"   not in locals(): fig_ev_la=plot_ev_la_scatter(bdf,selected)
    if "fig_roll"    not in locals(): fig_roll=plot_rolling_ev(bdf,selected)
    dr=f"{df['Date'].min().date()} → {df['Date'].max().date()}" if df["Date"].notna().any() else "All dates"
    ec1,ec2=st.columns(2)
    with ec1:
        pdf_b=export_hitting_pdf(selected,monthly_df,disc,result_df,split_df,
                                  fig_spray,fig_dmg,fig_ev,fig_la,fig_ev_la,fig_roll,dr)
        st.download_button("⬇️ Download PDF Report",pdf_b,f"{selected}_hitting.pdf","application/pdf")
    with ec2:
        csv_dl(bdf,f"{selected}_raw.csv","⬇️ Download Raw CSV")
    for f in [fig_spray,fig_dmg,fig_ev,fig_la,fig_ev_la,fig_roll]: plt.close(f)

# ══════════════════════════════════════════════════════════════════════════════
# RENDER: LEAGUE & STADIUM OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
def render_league(df):
    st.markdown('<div class="sh">📊 League & Stadium Intelligence</div>',unsafe_allow_html=True)
    tab_l1,tab_l2,tab_l3=st.tabs(["📈 League Averages","🏟️ Stadium Comparison","🗺️ Park Factor Map"])

    with tab_l1:
        c1,c2=st.columns(2)
        with c1:
            st.markdown('<div class="sh">⚾ Pitching Averages</div>',unsafe_allow_html=True)
            lp=build_league_pitching_avg(df)
            if lp.empty: st.info("Not enough data.")
            else:
                st.dataframe(lp,use_container_width=True,hide_index=True)
                csv_dl(lp,"league_pitching.csv")
        with c2:
            st.markdown('<div class="sh">🏏 Hitting Averages</div>',unsafe_allow_html=True)
            lh=build_league_hitting_avg(df)
            if lh.empty: st.info("Not enough data.")
            else:
                st.dataframe(lh,use_container_width=True,hide_index=True)
                csv_dl(lh,"league_hitting.csv")

    with tab_l2:
        if "Stadium" not in df.columns:
            st.info("No 'Stadium' column found.")
        else:
            m_col=st.selectbox("Metric",["ExitSpeed","RelSpeed","Angle","Distance"],key="stad_lg_metric")
            m_labels={"ExitSpeed":"Avg Exit Velo (mph)","RelSpeed":"Avg Pitch Velo (mph)",
                      "Angle":"Avg Launch Angle (°)","Distance":"Avg Distance (ft)"}
            fig_sb=plot_stadium_bar(df,m_col,m_labels[m_col],f"League — {m_labels[m_col]} by Stadium")
            st.pyplot(fig_sb,use_container_width=True); plt.close(fig_sb)
            tbl_sb=build_stadium_table(df,m_col,m_labels[m_col])
            if not tbl_sb.empty:
                st.dataframe(tbl_sb,use_container_width=True,hide_index=True)
                csv_dl(tbl_sb,"stadium_comparison.csv")

    with tab_l3:
        st.markdown("**Park Factor** = stadium avg EV relative to league avg. "
                    ">1 = hitter-friendly, <1 = pitcher-friendly.")
        if "Stadium" not in df.columns or "ExitSpeed" not in df.columns:
            st.info("Requires Stadium and ExitSpeed columns.")
        else:
            league_ev=df["ExitSpeed"].mean()
            stad_ev=(df.groupby("Stadium")["ExitSpeed"]
                       .agg(["mean","count"]).reset_index())
            stad_ev.columns=["Stadium","Avg EV","Pitches"]
            stad_ev=stad_ev[stad_ev["Pitches"]>=20]
            stad_ev["Park Factor"]=stad_ev["Avg EV"]/league_ev
            stad_ev["Park Factor"]=stad_ev["Park Factor"].round(3)
            stad_ev=stad_ev.sort_values("Park Factor",ascending=False)

            fig_pf,ax_pf=plt.subplots(figsize=(max(7,len(stad_ev)*0.8),4.0))
            act(fig_pf,[ax_pf])
            c_pf=[RED if v>1 else BLUE for v in stad_ev["Park Factor"]]
            bars_pf=ax_pf.bar(stad_ev["Stadium"],stad_ev["Park Factor"],
                              color=c_pf,alpha=0.82,edgecolor=C_SPINE,linewidth=0.4,zorder=3)
            ax_pf.axhline(1.0,color=ACCENT,lw=1.8,linestyle="--",label="League avg (1.0)",zorder=5)
            for bar,val in zip(bars_pf,stad_ev["Park Factor"]):
                ax_pf.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.002,
                           f"{val:.3f}",ha="center",va="bottom",fontsize=7.5,color=C_TEXT,fontweight="bold")
            ax_pf.set_xlabel("Stadium"); ax_pf.set_ylabel("Park Factor (EV-based)")
            plt.xticks(rotation=35,ha="right",fontsize=8)
            cht(ax_pf,"Park Factor — Exit Velocity (Hitter-Friendly vs Pitcher-Friendly)")
            ax_pf.legend(fontsize=8,framealpha=0.4,facecolor=C_CARD,labelcolor=C_TEXT)
            fig_pf.tight_layout(pad=1.2)
            st.pyplot(fig_pf,use_container_width=True); plt.close(fig_pf)
            st.dataframe(stad_ev.reset_index(drop=True),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown("""
    <div class="hero">
      <div class="hero-icon">⚾</div>
      <div>
        <div class="hero-title">Trackman <span class="hl">Analytics</span>
          <span style="font-size:.95rem;opacity:.35;font-weight:400"> v4.0</span></div>
        <div class="hero-sub">Advanced baseball data science platform — pitching · hitting · umpires · stadiums</div>
        <div class="hero-pills">
          <span class="pill">🔍 Player Search</span><span class="pill">🏟️ Stadium Trends</span>
          <span class="pill">📊 League Avg</span><span class="pill">🔄 vs RHP/LHP</span>
          <span class="pill">🎯 Play Results</span><span class="pill">📦 EV×LA Quality</span>
          <span class="pill">🏅 Park Factor</span><span class="pill">📄 Redesigned PDF</span>
        </div>
      </div>
    </div>
    """,unsafe_allow_html=True)

    st.sidebar.markdown('<span class="sb-label">📂 Upload Data</span>',unsafe_allow_html=True)
    uploaded=st.sidebar.file_uploader("Upload Trackman CSV files",type=["csv"],
                                      accept_multiple_files=True,
                                      help="One or more Trackman export CSV files.")
    if not uploaded:
        st.markdown("""<div class="upload-zone"><div class="big">📂</div>
          <div class="ttl">Upload your Trackman CSV files to begin</div>
          <div class="sub">Use the sidebar to upload one or multiple Trackman exports.<br>
          The dashboard merges, cleans, deduplicates names, and analyses automatically.</div>
          </div>""",unsafe_allow_html=True)
        return

    # Pass bytes to cached loader (avoids re-reading on every interaction)
    file_bytes=[f.read() for f in uploaded]
    file_names=[f.name for f in uploaded]

    with st.spinner("🔄 Loading and cleaning data…"):
        master,pa,ba=load_and_clean(tuple(file_bytes),tuple(file_names))

    if master.empty:
        st.error("❌ No valid data. Please check your CSV files."); return

    st.sidebar.success(f"✅ **{len(master):,}** pitches · **{len(uploaded)}** file(s).")
    if pa+ba>0:
        st.sidebar.markdown(
            f'<div class="alias-box">🔗 Merged <b>{pa+ba}</b> name variant(s) — '
            f'{pa} pitcher · {ba} batter aliases resolved.</div>',
            unsafe_allow_html=True)

    filtered=sidebar_date_filter(master)
    if filtered.empty: st.warning("⚠️ No data for selected dates."); return
    filtered=advanced_filters(filtered)
    if filtered.empty: st.warning("⚠️ No data after filters."); return

    st.sidebar.markdown('<span class="sb-label">🎯 Dashboard Mode</span>',unsafe_allow_html=True)
    mode=st.sidebar.radio("mode",
        ["⚾ Pitching","🏏 Hitting","📊 League & Stadiums"],
        key="dash_mode",label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("Built with ❤️ · Streamlit · Pandas · Matplotlib · Seaborn")

    if   mode=="⚾ Pitching":       render_pitching(filtered,master)
    elif mode=="🏏 Hitting":        render_hitting(filtered,master)
    else:                            render_league(filtered)

if __name__=="__main__":
    main()