"""
=============================================================================
  TRACKMAN BASEBALL ANALYTICS DASHBOARD
  Expert-grade Streamlit app for pitching and hitting analysis
  Built with: Streamlit, Pandas, Matplotlib, Seaborn
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
from datetime import date
 
# Suppress noisy warnings from seaborn/matplotlib
warnings.filterwarnings("ignore")
matplotlib.use("Agg")  # Non-interactive backend for server environments
 
# =============================================================================
# PAGE CONFIG & GLOBAL STYLE
# =============================================================================
st.set_page_config(
    page_title="Trackman Baseball Analytics",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# Inject custom CSS for a polished dark-sports aesthetic
st.markdown("""
<style>
    /* ---- Root palette ---- */
    :root {
        --bg-primary:   #0d1117;
        --bg-card:      #161b22;
        --accent:       #e8a838;
        --accent-dim:   #b8832a;
        --text-primary: #e6edf3;
        --text-muted:   #8b949e;
        --border:       #30363d;
    }
 
    /* ---- App chrome ---- */
    .stApp { background-color: var(--bg-primary); color: var(--text-primary); }
    section[data-testid="stSidebar"] {
        background-color: var(--bg-card);
        border-right: 1px solid var(--border);
    }
 
    /* ---- Metric cards ---- */
    div[data-testid="metric-container"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px;
    }
    div[data-testid="metric-container"] label { color: var(--text-muted) !important; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: var(--accent) !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
 
    /* ---- Section headers ---- */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.12em;
        border-bottom: 1px solid var(--border);
        padding-bottom: 6px;
        margin-bottom: 14px;
    }
 
    /* ---- Hero banner ---- */
    .hero-banner {
        background: linear-gradient(135deg, #1a2332 0%, #0d1117 60%, #1a1200 100%);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 28px 32px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 18px;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--text-primary);
        line-height: 1.1;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        color: var(--text-muted);
        font-size: 0.95rem;
        margin-top: 4px;
    }
    .hero-accent { color: var(--accent); }
 
    /* ---- Dataframe styling ---- */
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 8px;
    }
 
    /* ---- Warning / info box ---- */
    div[data-testid="stAlert"] { border-radius: 8px; }
 
    /* ---- Tab bar ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: var(--bg-card);
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        color: var(--text-muted);
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: var(--accent) !important;
        color: #000 !important;
    }
 
    /* ---- Download buttons ---- */
    .stDownloadButton > button {
        background: transparent;
        border: 1px solid var(--accent);
        color: var(--accent);
        font-weight: 600;
        border-radius: 6px;
        transition: all 0.2s;
    }
    .stDownloadButton > button:hover {
        background: var(--accent);
        color: #000;
    }
</style>
""", unsafe_allow_html=True)
 
 
# =============================================================================
# HELPER: MATPLOTLIB DARK THEME
# =============================================================================
def apply_dark_theme(fig, ax_list=None):
    """Apply consistent dark theme to any matplotlib figure."""
    BG    = "#0d1117"
    CARD  = "#161b22"
    TEXT  = "#e6edf3"
    MUTED = "#8b949e"
    GRID  = "#21262d"
 
    fig.patch.set_facecolor(BG)
    axes = ax_list if ax_list else fig.get_axes()
    for ax in axes:
        ax.set_facecolor(CARD)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        ax.title.set_color(TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)
        ax.grid(color=GRID, linewidth=0.5, alpha=0.7)
 
 
# =============================================================================
# HELPER: STRIKE ZONE RECTANGLE
# =============================================================================
def draw_strike_zone(ax, color="#e8a838", lw=1.8, alpha=0.9):
    """
    Draw a standard MLB strike zone rectangle on the given Axes.
    Plate width: 17 in → ±0.71 ft from centre
    Typical zone height: 1.5 ft – 3.5 ft above ground
    """
    zone = patches.Rectangle(
        (-0.71, 1.5),       # (x_left, y_bottom)
        width=1.42,
        height=2.0,
        linewidth=lw,
        edgecolor=color,
        facecolor="none",
        alpha=alpha,
        zorder=5,
    )
    ax.add_patch(zone)
 
    # Draw inner quadrants (3×3 grid inside zone)
    col_w = 1.42 / 3
    row_h = 2.0  / 3
    for i in range(1, 3):
        ax.axvline(-0.71 + i * col_w, ymin=0, ymax=1, color=color,
                   linewidth=0.5, alpha=0.35, zorder=4)
    for j in range(1, 3):
        ax.axhline(1.5 + j * row_h, xmin=0, xmax=1, color=color,
                   linewidth=0.5, alpha=0.35, zorder=4)
 
 
# =============================================================================
# STEP 1 — SMART DATA LOADING & CLEANING
# =============================================================================
COLUMN_ALIASES = {
    # Standard name  : list of possible Trackman alternatives
    "TaggedPitchType": ["AutoPitchType", "PitchType"],
    "PitchCall":       ["Call", "PitchResult"],
    "Batter":          ["BatterName", "HitterName"],
    "Pitcher":         ["PitcherName", "ThrowerName"],
}
 
WARMUP_VALUES = {"warmup", "undefined", "", "nan"}
 
 
def smart_map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each standard column, if it is absent, look for known
    alternative names and rename the first match found.
    """
    for standard, alternatives in COLUMN_ALIASES.items():
        if standard not in df.columns:
            for alt in alternatives:
                # Case-insensitive match
                matched = [c for c in df.columns if c.lower() == alt.lower()]
                if matched:
                    df.rename(columns={matched[0]: standard}, inplace=True)
                    break
    return df
 
 
def load_and_clean(files) -> pd.DataFrame:
    """
    Read one or many CSV files, merge them, apply smart column mapping,
    parse dates, and filter out warmups / undefined rows.
    """
    frames = []
    for f in files:
        try:
            df_raw = pd.read_csv(f, low_memory=False)
            frames.append(df_raw)
        except Exception as e:
            st.warning(f"⚠️ Could not read **{f.name}**: {e}")
 
    if not frames:
        return pd.DataFrame()
 
    # Merge all uploaded files
    df = pd.concat(frames, ignore_index=True)
 
    # Apply smart column alias mapping
    df = smart_map_columns(df)
 
    # Parse date column (Latin American format: day first)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    else:
        st.warning("⚠️ No 'Date' column found — date filtering will be unavailable.")
        df["Date"] = pd.NaT
 
    # Normalise PitchCall and Batter for warmup filtering
    for col in ["PitchCall", "Batter"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
 
    # Remove warmup / undefined rows (check both PitchCall and Batter)
    def is_warmup_row(row):
        pc = str(row.get("PitchCall", "")).lower()
        ba = str(row.get("Batter", "")).lower()
        return pc in WARMUP_VALUES or ba in WARMUP_VALUES
 
    before = len(df)
    df = df[~df.apply(is_warmup_row, axis=1)].reset_index(drop=True)
    removed = before - len(df)
    if removed:
        st.sidebar.caption(f"🧹 Removed {removed:,} warmup / undefined rows.")
 
    # Fill missing pitch type labels
    if "TaggedPitchType" in df.columns:
        df["TaggedPitchType"] = (
            df["TaggedPitchType"]
            .astype(str)
            .str.strip()
            .replace({"nan": "Unknown", "": "Unknown"})
        )
    else:
        df["TaggedPitchType"] = "Unknown"
 
    # Ensure numeric columns are properly cast
    numeric_cols = [
        "RelSpeed", "SpinRate", "InducedVertBreak", "HorzBreak",
        "PlateLocSide", "PlateLocHeight", "ExitSpeed", "Angle",
        "Distance", "Bearing",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
 
    return df
 
 
# =============================================================================
# STEP 2 — DATE FILTER
# =============================================================================
def sidebar_date_filter(df: pd.DataFrame):
    """
    Show a date range input in the sidebar. Returns filtered DataFrame.
    """
    st.sidebar.markdown("### 📅 Date Range")
 
    valid_dates = df["Date"].dropna()
    if valid_dates.empty:
        st.sidebar.info("No valid dates found — showing all data.")
        return df
 
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()
 
    selected = st.sidebar.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
 
    # date_input may return a single date or a tuple
    if isinstance(selected, (list, tuple)) and len(selected) == 2:
        start, end = selected
    else:
        start = end = selected if selected else min_date
 
    mask = (df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)
    filtered = df[mask].reset_index(drop=True)
 
    st.sidebar.caption(
        f"📊 **{len(filtered):,}** pitches from "
        f"**{start}** → **{end}**"
    )
    return filtered
 
 
# =============================================================================
# HELPER: CSV DOWNLOAD BUTTON
# =============================================================================
def csv_download_button(df: pd.DataFrame, filename: str, label: str = "⬇️ Download CSV"):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(label=label, data=csv_bytes,
                       file_name=filename, mime="text/csv")
 
 
# =============================================================================
# STEP 3 — PITCHING DASHBOARD
# =============================================================================
 
# ---- 3a. Summary table with fastball-first sorting ----
def build_pitch_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by TaggedPitchType and compute:
    Count, Max MPH, Avg MPH, Avg Spin, Avg IVB, Avg HB
    Fastball pitches are forced to the top; remaining sorted by count desc.
    """
    agg_dict = {"RelSpeed": ["count", "max", "mean"]}
    col_rename = {
        ("RelSpeed", "count"): "Pitches",
        ("RelSpeed", "max"):   "Max MPH",
        ("RelSpeed", "mean"):  "Avg MPH",
    }
 
    optional = {
        "SpinRate":         ("Avg Spin",  "mean"),
        "InducedVertBreak": ("Avg IVB",   "mean"),
        "HorzBreak":        ("Avg HB",    "mean"),
    }
    for col, (alias, func) in optional.items():
        if col in df.columns:
            agg_dict[col] = [func]
            col_rename[(col, func)] = alias
 
    summary = df.groupby("TaggedPitchType", as_index=False).agg(agg_dict)
    summary.columns = [col_rename.get(c, c[0] if c[1] == "" else "_".join(c))
                       for c in summary.columns]
 
    # Add missing optional columns filled with NaN
    for _, (alias, _) in optional.items():
        if alias not in summary.columns:
            summary[alias] = np.nan
 
    # Round numeric columns
    num_cols = ["Max MPH", "Avg MPH", "Avg Spin", "Avg IVB", "Avg HB"]
    for col in num_cols:
        if col in summary.columns:
            summary[col] = summary[col].round(1)
 
    # ---- Fastball-first sort ----
    summary["_is_fastball"] = (
        summary["TaggedPitchType"]
        .str.lower()
        .str.contains("fastball")
        .astype(int)
    )
    summary = (
        summary
        .sort_values(["_is_fastball", "Pitches"], ascending=[False, False])
        .drop(columns="_is_fastball")
        .reset_index(drop=True)
    )
    return summary
 
 
# ---- 3b. Pitch Location scatter ----
def plot_pitch_locations(df: pd.DataFrame, pitcher_name: str) -> plt.Figure:
    """Scatter plot of pitch locations coloured by pitch type, over strike zone."""
    PALETTE = [
        "#e8a838", "#4e9af1", "#e85858", "#58c99a",
        "#c458e8", "#e8c858", "#58a4e8", "#e87858",
    ]
 
    fig, ax = plt.subplots(figsize=(5, 5.5))
    apply_dark_theme(fig, [ax])
 
    loc_df = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
 
    if loc_df.empty:
        ax.text(0.5, 0.5, "No location data", ha="center", va="center",
                color="#8b949e", transform=ax.transAxes)
    else:
        pitch_types = loc_df["TaggedPitchType"].unique()
        for idx, pt in enumerate(pitch_types):
            sub = loc_df[loc_df["TaggedPitchType"] == pt]
            color = PALETTE[idx % len(PALETTE)]
            ax.scatter(
                sub["PlateLocSide"], sub["PlateLocHeight"],
                label=pt, color=color, alpha=0.75, s=30,
                edgecolors="none", zorder=6,
            )
 
    draw_strike_zone(ax)
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(0.5, 5.0)
    ax.set_xlabel("Plate Side (ft)")
    ax.set_ylabel("Plate Height (ft)")
    ax.set_title(f"Pitch Locations\n{pitcher_name}", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right",
              framealpha=0.3, edgecolor="#30363d")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    return fig
 
 
# ---- 3c. Hot Zone KDE ----
def plot_hot_zone(df: pd.DataFrame, pitcher_name: str) -> plt.Figure:
    """Seaborn KDE density plot of pitch locations over the strike zone."""
    fig, ax = plt.subplots(figsize=(5, 5.5))
    apply_dark_theme(fig, [ax])
 
    loc_df = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
 
    if len(loc_df) >= 5:
        try:
            sns.kdeplot(
                data=loc_df,
                x="PlateLocSide",
                y="PlateLocHeight",
                fill=True,
                cmap="YlOrRd",
                alpha=0.75,
                levels=10,
                thresh=0.05,
                ax=ax,
            )
        except Exception:
            ax.text(0.5, 0.5, "Not enough data for KDE",
                    ha="center", va="center",
                    color="#8b949e", transform=ax.transAxes)
    else:
        ax.text(0.5, 0.5, "Not enough data for KDE",
                ha="center", va="center",
                color="#8b949e", transform=ax.transAxes)
 
    draw_strike_zone(ax)
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(0.5, 5.0)
    ax.set_xlabel("Plate Side (ft)")
    ax.set_ylabel("Plate Height (ft)")
    ax.set_title(f"Hot Zone (KDE)\n{pitcher_name}", fontsize=10, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    return fig
 
 
# ---- 3d. Velocity Tendency ----
def plot_velocity_tendency(df: pd.DataFrame, pitcher_name: str) -> plt.Figure:
    """Line plot of average RelSpeed per date, coloured by pitch type."""
    fig, ax = plt.subplots(figsize=(11, 3.5))
    apply_dark_theme(fig, [ax])
 
    if "RelSpeed" not in df.columns or df["RelSpeed"].dropna().empty:
        ax.text(0.5, 0.5, "No velocity data available",
                ha="center", va="center",
                color="#8b949e", transform=ax.transAxes)
        fig.tight_layout()
        return fig
 
    vel_df = df.dropna(subset=["RelSpeed", "Date"])
 
    if vel_df.empty:
        ax.text(0.5, 0.5, "No velocity data available",
                ha="center", va="center",
                color="#8b949e", transform=ax.transAxes)
        fig.tight_layout()
        return fig
 
    PALETTE = [
        "#e8a838", "#4e9af1", "#e85858", "#58c99a",
        "#c458e8", "#e8c858", "#58a4e8", "#e87858",
    ]
    pitch_types = vel_df["TaggedPitchType"].unique()
 
    for idx, pt in enumerate(pitch_types):
        sub = vel_df[vel_df["TaggedPitchType"] == pt].sort_values("Date")
        daily = sub.groupby("Date")["RelSpeed"].mean().reset_index()
        color = PALETTE[idx % len(PALETTE)]
        ax.plot(daily["Date"], daily["RelSpeed"],
                label=pt, color=color, linewidth=1.8,
                marker="o", markersize=4, alpha=0.9)
 
    ax.set_xlabel("Date")
    ax.set_ylabel("Avg Velocity (MPH)")
    ax.set_title(f"Velocity Tendency — {pitcher_name}", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right",
              framealpha=0.3, edgecolor="#30363d")
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout()
    return fig
 
 
# ---- 3e. PDF export for pitching ----
def export_pitching_pdf(summary_df: pd.DataFrame,
                         fig_loc: plt.Figure,
                         fig_kde: plt.Figure,
                         fig_vel: plt.Figure,
                         pitcher_name: str) -> bytes:
    """
    Build a multi-page PDF:
      Page 1: summary table
      Page 2: pitch locations
      Page 3: hot zone KDE
      Page 4: velocity tendency
    """
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # ---- Page 1: Summary Table ----
        fig_tbl, ax_tbl = plt.subplots(figsize=(11, max(3, len(summary_df) * 0.45 + 1.5)))
        fig_tbl.patch.set_facecolor("#0d1117")
        ax_tbl.axis("off")
        ax_tbl.set_title(
            f"Pitching Summary — {pitcher_name}",
            color="#e6edf3", fontsize=13, fontweight="bold", pad=16,
        )
 
        columns = list(summary_df.columns)
        cell_data = summary_df.values.tolist()
 
        tbl = ax_tbl.table(
            cellText=cell_data,
            colLabels=columns,
            loc="center",
            cellLoc="center",
        )
        # Dynamic column widths so long pitch names don't overflow
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.auto_set_column_width(col=list(range(len(columns))))
 
        # Style header row
        for j in range(len(columns)):
            cell = tbl[0, j]
            cell.set_facecolor("#e8a838")
            cell.set_text_props(color="#000000", fontweight="bold")
        # Style data rows
        for i in range(1, len(cell_data) + 1):
            for j in range(len(columns)):
                cell = tbl[i, j]
                cell.set_facecolor("#1c2230" if i % 2 == 0 else "#161b22")
                cell.set_text_props(color="#e6edf3")
 
        tbl.scale(1.1, 1.6)
        fig_tbl.tight_layout()
        pdf.savefig(fig_tbl, bbox_inches="tight", facecolor="#0d1117")
        plt.close(fig_tbl)
 
        # ---- Pages 2-4: Charts ----
        for fig in [fig_loc, fig_kde, fig_vel]:
            pdf.savefig(fig, bbox_inches="tight", facecolor="#0d1117")
 
    buf.seek(0)
    return buf.read()
 
 
# ---- 3f. Main pitching dashboard renderer ----
def render_pitching_dashboard(df: pd.DataFrame):
    """Full pitching dashboard: selector → metrics → table → charts → export."""
    st.markdown('<div class="section-header">⚾ Pitching Dashboard</div>',
                unsafe_allow_html=True)
 
    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column found in the data.")
        return
 
    pitchers = sorted(df["Pitcher"].dropna().unique())
    selected_pitcher = st.selectbox("Select Pitcher", pitchers)
 
    pitcher_df = df[df["Pitcher"] == selected_pitcher].copy()
    total_pitches = len(pitcher_df)
 
    # Minimum pitch warning
    if total_pitches < 15:
        st.warning(
            f"⚠️ **{selected_pitcher}** has only **{total_pitches}** pitches "
            "in this date range (minimum recommended: 15). Data may not be representative."
        )
 
    # ---- Metric row ----
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Pitches", f"{total_pitches:,}")
    with col2:
        avg_velo = pitcher_df["RelSpeed"].mean() if "RelSpeed" in pitcher_df.columns else np.nan
        st.metric("Avg Velocity", f"{avg_velo:.1f} mph" if not np.isnan(avg_velo) else "—")
    with col3:
        avg_spin = pitcher_df["SpinRate"].mean() if "SpinRate" in pitcher_df.columns else np.nan
        st.metric("Avg Spin Rate", f"{avg_spin:.0f} rpm" if not np.isnan(avg_spin) else "—")
    with col4:
        pitch_types = pitcher_df["TaggedPitchType"].nunique()
        st.metric("Pitch Types", str(pitch_types))
 
    st.markdown("<br>", unsafe_allow_html=True)
 
    # ---- Summary Table ----
    st.markdown('<div class="section-header">📋 Pitch Summary</div>',
                unsafe_allow_html=True)
    summary_df = build_pitch_summary(pitcher_df)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    csv_download_button(summary_df, f"{selected_pitcher}_pitch_summary.csv")
 
    st.markdown("<br>", unsafe_allow_html=True)
 
    # ---- Visual row: locations + hot zone ----
    st.markdown('<div class="section-header">📍 Pitch Locations & Hot Zone</div>',
                unsafe_allow_html=True)
    col_loc, col_kde = st.columns(2)
 
    fig_loc = plot_pitch_locations(pitcher_df, selected_pitcher)
    fig_kde = plot_hot_zone(pitcher_df, selected_pitcher)
 
    with col_loc:
        st.pyplot(fig_loc, use_container_width=True)
    with col_kde:
        st.pyplot(fig_kde, use_container_width=True)
 
    st.markdown("<br>", unsafe_allow_html=True)
 
    # ---- Velocity tendency (full width) ----
    st.markdown('<div class="section-header">📈 Velocity Tendency Over Time</div>',
                unsafe_allow_html=True)
    fig_vel = plot_velocity_tendency(pitcher_df, selected_pitcher)
    st.pyplot(fig_vel, use_container_width=True)
 
    # ---- PDF Export ----
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📤 Export Report</div>',
                unsafe_allow_html=True)
    pdf_bytes = export_pitching_pdf(
        summary_df, fig_loc, fig_kde, fig_vel, selected_pitcher
    )
    st.download_button(
        label="⬇️ Download PDF Report",
        data=pdf_bytes,
        file_name=f"{selected_pitcher}_pitching_report.pdf",
        mime="application/pdf",
    )
 
    # Close figures to free memory
    plt.close(fig_loc)
    plt.close(fig_kde)
    plt.close(fig_vel)
 
 
# =============================================================================
# STEP 4 — HITTING DASHBOARD
# =============================================================================
 
# ---- 4a. Monthly progression table ----
def build_hitting_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by Year-Month and compute hitting metrics.
    Handles missing columns gracefully. Most recent month at top.
    """
    df = df.copy()
    df["YearMonth"] = df["Date"].dt.to_period("M")
 
    agg = {"YearMonth": "count"}          # use as a proxy for pitches seen
    rename_map = {}
 
    # Build agg dict dynamically based on available columns
    base_pitches = pd.Series(df.groupby("YearMonth").size(), name="Pitches Seen")
 
    optional_metrics = {
        "ExitSpeed": ("Max ExitSpd", "Avg ExitSpd"),
        "Angle":     ("Max Angle",   "Avg Angle"),
        "Distance":  ("Max Dist",    "Avg Dist"),
    }
 
    records = []
    for period, group in df.groupby("YearMonth"):
        row = {"Month": str(period), "Pitches Seen": len(group)}
        for col, (max_name, avg_name) in optional_metrics.items():
            if col in df.columns:
                vals = group[col].dropna()
                row[max_name] = round(vals.max(), 1) if not vals.empty else np.nan
                row[avg_name] = round(vals.mean(), 1) if not vals.empty else np.nan
        records.append(row)
 
    monthly = pd.DataFrame(records)
    if monthly.empty:
        return monthly
 
    # Sort most recent month first
    monthly = monthly.sort_values("Month", ascending=False).reset_index(drop=True)
    return monthly
 
 
# ---- 4b. Spray Chart ----
def plot_spray_chart(df: pd.DataFrame, batter_name: str) -> plt.Figure:
    """
    Convert Distance + Bearing → cartesian coordinates.
    Draw a baseball field outline and scatter hits coloured by ExitSpeed.
    """
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    apply_dark_theme(fig, [ax])
 
    # Safety: filter rows that have both Distance and Bearing
    spray_df = df.dropna(subset=["Distance", "Bearing"]).copy()
 
    if spray_df.empty:
        ax.text(0.5, 0.5, "No spray chart data available",
                ha="center", va="center",
                color="#8b949e", transform=ax.transAxes)
        ax.set_title(f"Spray Chart\n{batter_name}", fontsize=10, fontweight="bold")
        fig.tight_layout()
        return fig
 
    # Convert polar (Distance, Bearing) → cartesian
    bearing_rad = np.deg2rad(spray_df["Bearing"])
    spray_df["Hit_X"] =  spray_df["Distance"] * np.sin(bearing_rad)
    spray_df["Hit_Y"] =  spray_df["Distance"] * np.cos(bearing_rad)
 
    # ---- Draw field ----
    FIELD_COLOR = "#1a2a1a"
    ax.set_facecolor(FIELD_COLOR)
 
    # Foul lines (45° from centre)
    max_dist = 420
    ax.plot([0,  max_dist * np.sin(np.deg2rad(45))],
            [0,  max_dist * np.cos(np.deg2rad(45))],
            color="#8b6914", lw=1.5, alpha=0.7)
    ax.plot([0, -max_dist * np.sin(np.deg2rad(45))],
            [0,  max_dist * np.cos(np.deg2rad(45))],
            color="#8b6914", lw=1.5, alpha=0.7)
 
    # Outfield arc (230–400 ft)
    angles_arc = np.linspace(-45, 45, 200)
    for radius in [230, 330, 400]:
        ax.plot(
            radius * np.sin(np.deg2rad(angles_arc)),
            radius * np.cos(np.deg2rad(angles_arc)),
            color="#4a5e3a", lw=1.0, alpha=0.5, linestyle="--",
        )
 
    # Infield diamond (90 ft bases)
    base_dist = 90 * np.sqrt(2) / 2
    diamond_x = [0, base_dist, 0, -base_dist, 0]
    diamond_y = [0, base_dist, 2 * base_dist, base_dist, 0]
    ax.plot(diamond_x, diamond_y, color="#c8a850", lw=1.0, alpha=0.6)
 
    # ---- Plot hits ----
    has_exit = "ExitSpeed" in spray_df.columns and spray_df["ExitSpeed"].notna().any()
    scatter = ax.scatter(
        spray_df["Hit_X"], spray_df["Hit_Y"],
        c=spray_df["ExitSpeed"] if has_exit else "#e8a838",
        cmap="coolwarm" if has_exit else None,
        s=40, alpha=0.85, edgecolors="none", zorder=5,
        vmin=60 if has_exit else None,
        vmax=110 if has_exit else None,
    )
    if has_exit:
        cb = fig.colorbar(scatter, ax=ax, pad=0.02, shrink=0.75)
        cb.set_label("Exit Speed (mph)", color="#8b949e", fontsize=8)
        cb.ax.yaxis.set_tick_params(color="#8b949e", labelcolor="#8b949e")
        cb.outline.set_edgecolor("#30363d")
 
    ax.set_xlim(-350, 350)
    ax.set_ylim(-30, 450)
    ax.set_xlabel("Horizontal Distance (ft)")
    ax.set_ylabel("Vertical Distance (ft)")
    ax.set_title(f"Spray Chart\n{batter_name}", fontsize=10, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    return fig
 
 
# ---- 4c. Damage Zone ----
def plot_damage_zone(df: pd.DataFrame, batter_name: str) -> plt.Figure:
    """
    Scatter of pitch locations (PlateLocSide × PlateLocHeight)
    coloured by ExitSpeed to reveal where the batter does most damage.
    """
    fig, ax = plt.subplots(figsize=(5, 5.5))
    apply_dark_theme(fig, [ax])
 
    loc_df = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
 
    if loc_df.empty:
        ax.text(0.5, 0.5, "No location data", ha="center", va="center",
                color="#8b949e", transform=ax.transAxes)
    else:
        has_exit = "ExitSpeed" in loc_df.columns and loc_df["ExitSpeed"].notna().any()
        c_vals = loc_df["ExitSpeed"] if has_exit else "#e8a838"
 
        scatter = ax.scatter(
            loc_df["PlateLocSide"], loc_df["PlateLocHeight"],
            c=c_vals,
            cmap="coolwarm" if has_exit else None,
            s=35, alpha=0.80, edgecolors="none", zorder=6,
            vmin=60 if has_exit else None,
            vmax=110 if has_exit else None,
        )
        if has_exit:
            cb = fig.colorbar(scatter, ax=ax, pad=0.02, shrink=0.75)
            cb.set_label("Exit Speed (mph)", color="#8b949e", fontsize=8)
            cb.ax.yaxis.set_tick_params(color="#8b949e", labelcolor="#8b949e")
            cb.outline.set_edgecolor("#30363d")
 
    draw_strike_zone(ax)
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(0.5, 5.0)
    ax.set_xlabel("Plate Side (ft)")
    ax.set_ylabel("Plate Height (ft)")
    ax.set_title(f"Damage Zone\n{batter_name}", fontsize=10, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    return fig
 
 
# ---- 4d. PDF export for hitting ----
def export_hitting_pdf(monthly_df: pd.DataFrame,
                        fig_spray: plt.Figure,
                        fig_damage: plt.Figure,
                        batter_name: str) -> bytes:
    """
    Build a multi-page PDF for the hitting report:
      Page 1: Monthly progression table
      Page 2: Spray chart
      Page 3: Damage zone
    """
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # ---- Page 1: Monthly table ----
        fig_tbl, ax_tbl = plt.subplots(
            figsize=(13, max(3, len(monthly_df) * 0.5 + 1.5))
        )
        fig_tbl.patch.set_facecolor("#0d1117")
        ax_tbl.axis("off")
        ax_tbl.set_title(
            f"Hitting Monthly Progression — {batter_name}",
            color="#e6edf3", fontsize=13, fontweight="bold", pad=16,
        )
 
        columns = list(monthly_df.columns)
        cell_data = monthly_df.fillna("—").values.tolist()
 
        tbl = ax_tbl.table(
            cellText=cell_data,
            colLabels=columns,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        # Dynamic column widths — critical to prevent text overlap
        tbl.auto_set_column_width(col=list(range(len(columns))))
 
        for j in range(len(columns)):
            cell = tbl[0, j]
            cell.set_facecolor("#e8a838")
            cell.set_text_props(color="#000000", fontweight="bold")
        for i in range(1, len(cell_data) + 1):
            for j in range(len(columns)):
                cell = tbl[i, j]
                cell.set_facecolor("#1c2230" if i % 2 == 0 else "#161b22")
                cell.set_text_props(color="#e6edf3")
 
        tbl.scale(1.1, 1.6)
        fig_tbl.tight_layout()
        pdf.savefig(fig_tbl, bbox_inches="tight", facecolor="#0d1117")
        plt.close(fig_tbl)
 
        # Pages 2–3: Charts
        for fig in [fig_spray, fig_damage]:
            pdf.savefig(fig, bbox_inches="tight", facecolor="#0d1117")
 
    buf.seek(0)
    return buf.read()
 
 
# ---- 4e. Main hitting dashboard renderer ----
def render_hitting_dashboard(df: pd.DataFrame):
    """Full hitting dashboard: selector → metrics → table → charts → export."""
    st.markdown('<div class="section-header">🏏 Hitting Dashboard</div>',
                unsafe_allow_html=True)
 
    if "Batter" not in df.columns or df["Batter"].dropna().empty:
        st.error("No 'Batter' column found in the data.")
        return
 
    batters = sorted(df["Batter"].dropna().unique())
    selected_batter = st.selectbox("Select Batter", batters)
 
    batter_df = df[df["Batter"] == selected_batter].copy()
    total_pitches = len(batter_df)
 
    # Minimum pitch warning
    if total_pitches < 15:
        st.warning(
            f"⚠️ **{selected_batter}** has only **{total_pitches}** pitches seen "
            "in this date range (minimum recommended: 15)."
        )
 
    # ---- Metric row ----
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pitches Seen", f"{total_pitches:,}")
    with col2:
        avg_exit = batter_df["ExitSpeed"].mean() if "ExitSpeed" in batter_df.columns else np.nan
        st.metric("Avg Exit Velo", f"{avg_exit:.1f} mph" if not np.isnan(avg_exit) else "—")
    with col3:
        max_exit = batter_df["ExitSpeed"].max() if "ExitSpeed" in batter_df.columns else np.nan
        st.metric("Max Exit Velo", f"{max_exit:.1f} mph" if not np.isnan(max_exit) else "—")
    with col4:
        avg_dist = batter_df["Distance"].mean() if "Distance" in batter_df.columns else np.nan
        st.metric("Avg Distance", f"{avg_dist:.0f} ft" if not np.isnan(avg_dist) else "—")
 
    st.markdown("<br>", unsafe_allow_html=True)
 
    # ---- Monthly Progression Table ----
    st.markdown('<div class="section-header">📅 Monthly Progression</div>',
                unsafe_allow_html=True)
    monthly_df = build_hitting_monthly(batter_df)
 
    if monthly_df.empty:
        st.info("No monthly data available for this batter.")
    else:
        st.dataframe(monthly_df, use_container_width=True, hide_index=True)
        csv_download_button(monthly_df, f"{selected_batter}_monthly.csv")
 
    st.markdown("<br>", unsafe_allow_html=True)
 
    # ---- Visuals: Spray Chart + Damage Zone ----
    st.markdown('<div class="section-header">🗺️ Spray Chart & Damage Zone</div>',
                unsafe_allow_html=True)
    col_spray, col_dmg = st.columns(2)
 
    fig_spray  = plot_spray_chart(batter_df, selected_batter)
    fig_damage = plot_damage_zone(batter_df, selected_batter)
 
    with col_spray:
        st.pyplot(fig_spray, use_container_width=True)
    with col_dmg:
        st.pyplot(fig_damage, use_container_width=True)
 
    # ---- PDF Export ----
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📤 Export Report</div>',
                unsafe_allow_html=True)
 
    if not monthly_df.empty:
        pdf_bytes = export_hitting_pdf(
            monthly_df, fig_spray, fig_damage, selected_batter
        )
        st.download_button(
            label="⬇️ Download PDF Report",
            data=pdf_bytes,
            file_name=f"{selected_batter}_hitting_report.pdf",
            mime="application/pdf",
        )
    else:
        st.info("Monthly data required for PDF export.")
 
    plt.close(fig_spray)
    plt.close(fig_damage)
 
 
# =============================================================================
# STEP 5 — MAIN APP ENTRY POINT
# =============================================================================
def main():
    # ---- Hero Banner ----
    st.markdown("""
    <div class="hero-banner">
        <div style="font-size:3rem; line-height:1">⚾</div>
        <div>
            <div class="hero-title">
                Trackman <span class="hero-accent">Analytics</span>
            </div>
            <div class="hero-subtitle">
                Advanced baseball data science dashboard for pitching & hitting
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
 
    # ---- Sidebar: File Uploader ----
    st.sidebar.markdown("## ⚾ Trackman Analytics")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 Upload Data")
 
    uploaded_files = st.sidebar.file_uploader(
        "Upload Trackman CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help="Select one or multiple Trackman export CSV files.",
    )
 
    # Guard: don't render dashboard until files are uploaded
    if not uploaded_files:
        st.markdown("""
        <div style="
            background: #161b22;
            border: 1px dashed #30363d;
            border-radius: 12px;
            padding: 60px 40px;
            text-align: center;
            margin-top: 40px;
        ">
            <div style="font-size: 3rem; margin-bottom: 16px;">📂</div>
            <div style="font-size: 1.4rem; font-weight: 700; color: #e6edf3; margin-bottom: 8px;">
                Upload your Trackman CSV files to begin
            </div>
            <div style="color: #8b949e; font-size: 0.95rem;">
                Use the sidebar on the left to upload one or multiple CSV exports.
                <br>The dashboard will automatically merge and clean your data.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
 
    # ---- Load & Clean Data ----
    with st.spinner("🔄 Loading and cleaning data..."):
        master_df = load_and_clean(uploaded_files)
 
    if master_df.empty:
        st.error("❌ No valid data could be loaded. Please check your CSV files.")
        return
 
    st.sidebar.success(f"✅ Loaded **{len(master_df):,}** pitches from "
                       f"**{len(uploaded_files)}** file(s).")
 
    # ---- Global Date Filter ----
    filtered_df = sidebar_date_filter(master_df)
 
    if filtered_df.empty:
        st.warning("⚠️ No data matches the selected date range.")
        return
 
    # ---- Dashboard Mode Selector ----
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 Dashboard Mode")
    mode = st.sidebar.radio(
        "Choose view",
        options=["⚾ Pitching", "🏏 Hitting"],
        horizontal=False,
    )
 
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Built with ❤️ using Streamlit, Pandas, "
        "Matplotlib & Seaborn"
    )
 
    # ---- Route to correct dashboard ----
    if mode == "⚾ Pitching":
        render_pitching_dashboard(filtered_df)
    else:
        render_hitting_dashboard(filtered_df)
 
 
# =============================================================================
if __name__ == "__main__":
    main()
 