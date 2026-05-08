import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import io
from matplotlib.backends.backend_pdf import PdfPages

st.set_page_config(page_title="Trackman Dashboard", layout="wide")

# ---------------------------------------------------------
# 1. FILE UPLOADER & LOAD DATA 
# ---------------------------------------------------------
st.sidebar.title("1. Upload Trackman Data")
uploaded_file = st.sidebar.file_uploader("Drop Trackman CSV here", type=['csv'])

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)

    # Fix dates for Brazil format
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    
    # --- WARMUP FILTER (LIVE PITCHES ONLY) ---
    if 'PitchCall' in df.columns:
        df = df[df['PitchCall'].notna()]
        df = df[df['PitchCall'] != 'Undefined']
        df = df[df['PitchCall'] != 'Warmup']
        
    if 'Batter' in df.columns:
        df = df[df['Batter'].notna()]
        df = df[df['Batter'] != 'Warmup']

    if 'TaggedPitchType' in df.columns:
        df['TaggedPitchType'] = df['TaggedPitchType'].fillna('Unknown')
        
    return df

# STOP THE APP IF NO FILE IS UPLOADED
if uploaded_file is None:
    st.title("⚾ Trackman Analysis Dashboard")
    st.info("👈 Please upload your Trackman CSV file in the sidebar menu to begin.")
    st.stop()

# If a file is uploaded, proceed with loading!
df = load_data(uploaded_file)

# ---------------------------------------------------------
# 2. APP SIDEBAR (Navigation)
# ---------------------------------------------------------
st.sidebar.title("2. Navigation")
dashboard_type = st.sidebar.radio("Select Dashboard:", ["Pitching", "Hitting"])

# ---------------------------------------------------------
# 3. PITCHING DASHBOARD
# ---------------------------------------------------------
if dashboard_type == "Pitching":
    st.title("⚾ Pitching Analysis Dashboard (Live Pitches Only)")
    
    all_pitchers = sorted(df['Pitcher'].dropna().unique())
    selected_pitcher = st.selectbox("Select a Pitcher:", all_pitchers)
    
    # 1. Get ALL data for this pitcher
    p_df_all = df[df['Pitcher'] == selected_pitcher].copy()
    
    # 2. Check Tuesday/Thursday count
    p_df_tuethu = p_df_all[p_df_all['Date'].dt.dayofweek.isin([1, 3])].copy()
    
    if len(p_df_tuethu) >= 15:
        p_df = p_df_tuethu
        st.success(f"Showing Tuesday/Thursday Data")
        st.subheader(f"Data Summary: {selected_pitcher} (Tue/Thu Pitches: {len(p_df)})")
    else:
        p_df = p_df_all
        st.warning(f"⚠️ Less than 15 pitches on Tue/Thu. Showing ALL available live pitches for this player.")
        st.subheader(f"Data Summary: {selected_pitcher} (Total Pitches: {len(p_df)})")
    
    if p_df.empty:
        st.warning("No live data found for this pitcher.")
    else:
        try:
            summary = p_df.groupby('TaggedPitchType').agg(
                Pitch_Count=('TaggedPitchType', 'count'),
                Max_MPH=('RelSpeed', 'max'),
                Avg_MPH=('RelSpeed', 'mean'),
                Avg_Spin=('SpinRate', 'mean'),
                Avg_IVB=('InducedVertBreak', 'mean'),
                Avg_HB=('HorzBreak', 'mean')
            ).round(1).reset_index()
            
            # --- THE FIX: SORT FASTBALL TO THE TOP ---
            summary['sort_order'] = summary['TaggedPitchType'].apply(lambda x: 0 if 'Fastball' in str(x) else 1)
            summary = summary.sort_values(by=['sort_order', 'Pitch_Count'], ascending=[True, False]).drop('sort_order', axis=1).reset_index(drop=True)
            
            st.dataframe(summary, use_container_width=True)
            
        except KeyError:
            st.error("Check Trackman column names to ensure averages can be calculated.")

        st.divider()

        # --- GENERATE PLOTS ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Pitch Locations")
            fig1, ax1 = plt.subplots(figsize=(6, 6))
            sns.scatterplot(data=p_df, x='PlateLocSide', y='PlateLocHeight', hue='TaggedPitchType', s=80, ax=ax1)
            ax1.add_patch(plt.Rectangle((-0.83, 1.5), 1.66, 2.0, fill=False, color='black', linewidth=2))
            ax1.set_xlim(-2.5, 2.5); ax1.set_ylim(0, 5)
            st.pyplot(fig1)

        with col2:
            st.subheader("Overall Hot Zone")
            fig2, ax2 = plt.subplots(figsize=(6, 6))
            sns.kdeplot(data=p_df, x='PlateLocSide', y='PlateLocHeight', cmap="Reds", fill=True, thresh=0.05, ax=ax2)
            ax2.add_patch(plt.Rectangle((-0.83, 1.5), 1.66, 2.0, fill=False, color='black', linewidth=2))
            ax2.set_xlim(-2.5, 2.5); ax2.set_ylim(0, 5)
            st.pyplot(fig2)

        st.subheader("Velocity Tendency Over Time")
        tendency_df = p_df.sort_values('Date')
        fig3, ax3 = plt.subplots(figsize=(10, 4))
        sns.lineplot(data=tendency_df, x='Date', y='RelSpeed', hue='TaggedPitchType', marker='o', errorbar=None, ax=ax3)
        ax3.grid(True, alpha=0.3)
        fig3.autofmt_xdate()
        st.pyplot(fig3)

        # --- DOWNLOAD BUTTONS ---
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            csv_data = summary.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📊 Download {selected_pitcher} Data (CSV)",
                data=csv_data,
                file_name=f"{selected_pitcher}_Pitching_Data.csv",
                mime='text/csv',
            )

        with col_btn2:
            pdf_buffer = io.BytesIO()
            with PdfPages(pdf_buffer) as pdf:
                fig_tbl, ax_tbl = plt.subplots(figsize=(12, 4))
                ax_tbl.axis('tight')
                ax_tbl.axis('off')
                ax_tbl.set_title(f"Pitching Summary (Live BP/Games): {selected_pitcher}", fontweight="bold", fontsize=16)
                
                tbl = ax_tbl.table(cellText=summary.values, colLabels=summary.columns, loc='center', cellLoc='center')
                tbl.auto_set_column_width(col=list(range(len(summary.columns)))) 
                tbl.scale(1, 2)
                tbl.auto_set_font_size(False)
                tbl.set_fontsize(12)
                pdf.savefig(fig_tbl, bbox_inches='tight')
                plt.close(fig_tbl)

                pdf.savefig(fig1, bbox_inches='tight')
                pdf.savefig(fig2, bbox_inches='tight')
                pdf.savefig(fig3, bbox_inches='tight')
            
            pdf_bytes = pdf_buffer.getvalue()
            st.download_button(
                label=f"📄 Download {selected_pitcher} Visual Report (PDF)",
                data=pdf_bytes,
                file_name=f"{selected_pitcher}_Visual_Report.pdf",
                mime='application/pdf',
            )

# ---------------------------------------------------------
# 4. HITTING DASHBOARD
# ---------------------------------------------------------
elif dashboard_type == "Hitting":
    st.title("🏏 Hitting Analysis Dashboard (Live BP/Games)")
    
    all_batters = sorted(df['Batter'].dropna().unique())
    selected_batter = st.selectbox("Select a Batter:", all_batters)
    
    # 1. Get ALL data for this batter
    b_df_all = df[df['Batter'] == selected_batter].copy()
    
    # 2. Check Tuesday/Thursday count
    b_df_tuethu = b_df_all[b_df_all['Date'].dt.dayofweek.isin([1, 3])].copy()
    
    if len(b_df_tuethu) >= 15:
        b_df = b_df_tuethu
        st.success(f"Showing Tuesday/Thursday Data")
        st.subheader(f"Monthly Progression: {selected_batter} (Tue/Thu Pitches Seen: {len(b_df)})")
    else:
        b_df = b_df_all
        st.warning(f"⚠️ Less than 15 pitches seen on Tue/Thu. Showing ALL available live data for this player.")
        st.subheader(f"Monthly Progression: {selected_batter} (Total Pitches Seen: {len(b_df)})")
    
    if b_df.empty:
        st.warning("No live data found for this batter.")
    else:
        # --- MONTHLY AGGREGATION LOGIC ---
        for col in ['ExitSpeed', 'Angle', 'Distance']:
            if col in b_df.columns:
                b_df[col] = pd.to_numeric(b_df[col], errors='coerce')
        
        b_df['Month'] = b_df['Date'].dt.strftime('%Y-%m')
        
        agg_args = {'Pitches_Seen': pd.NamedAgg(column='Date', aggfunc='count')}
        if 'ExitSpeed' in b_df.columns:
            agg_args['Max_EV'] = pd.NamedAgg(column='ExitSpeed', aggfunc='max')
            agg_args['Avg_EV'] = pd.NamedAgg(column='ExitSpeed', aggfunc='mean')
        if 'Angle' in b_df.columns:
            agg_args['Max_LA'] = pd.NamedAgg(column='Angle', aggfunc='max')
            agg_args['Avg_LA'] = pd.NamedAgg(column='Angle', aggfunc='mean')
        if 'Distance' in b_df.columns:
            agg_args['Max_Dist'] = pd.NamedAgg(column='Distance', aggfunc='max')
            agg_args['Avg_Dist'] = pd.NamedAgg(column='Distance', aggfunc='mean')
            
        hit_summary = b_df.groupby('Month').agg(**agg_args).round(1).reset_index()
        hit_summary = hit_summary.sort_values('Month', ascending=False)
        
        st.dataframe(hit_summary, use_container_width=True)
        
        st.divider()

        # --- GENERATE PLOTS ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"Spray Chart (Tracked Hits Only)")
            fig4, ax4 = plt.subplots(figsize=(6, 6))
            
            ax4.plot([0, -250], [0, 250], color='black', linewidth=2) 
            ax4.plot([0, 250], [0, 250], color='black', linewidth=2)  
            theta = np.linspace(-np.pi/4, np.pi/4, 100)
            r = 350 + 50 * np.cos(2*theta) 
            ax4.plot(r*np.sin(theta), r*np.cos(theta), color='green', linestyle='--', linewidth=2)
            
            spray_df = b_df[b_df['Bearing'].notna() & b_df['Distance'].notna()].copy()
            
            if not spray_df.empty:
                spray_df['Hit_X'] = spray_df['Distance'] * np.sin(np.radians(spray_df['Bearing']))
                spray_df['Hit_Y'] = spray_df['Distance'] * np.cos(np.radians(spray_df['Bearing']))

                if 'ExitSpeed' in spray_df.columns:
                    sns.scatterplot(data=spray_df, x='Hit_X', y='Hit_Y', hue='ExitSpeed', palette='coolwarm', s=100, edgecolor='black', ax=ax4)
                else:
                    sns.scatterplot(data=spray_df, x='Hit_X', y='Hit_Y', color='blue', s=100, edgecolor='black', ax=ax4)
                    
            ax4.plot(0, 0, marker='d', color='black', markersize=10) 
            ax4.set_xlim(-300, 300); ax4.set_ylim(-50, 450)
            st.pyplot(fig4)
            
        with col2:
            st.subheader("Damage Zone (Exit Velo in Strike Zone)")
            fig5, ax5 = plt.subplots(figsize=(6, 6))
            
            zone_df = b_df[b_df['PlateLocSide'].notna() & b_df['PlateLocHeight'].notna()].copy()
            
            if 'ExitSpeed' in zone_df.columns and not zone_df.empty:
                sc = ax5.scatter(zone_df['PlateLocSide'], zone_df['PlateLocHeight'], c=zone_df['ExitSpeed'], cmap='coolwarm', s=150, edgecolors='black')
                plt.colorbar(sc, ax=ax5, label="Exit Velocity (MPH)")
            else:
                ax5.text(0.5, 0.5, 'Missing Coordinate Data', ha='center', va='center')
                
            ax5.add_patch(plt.Rectangle((-0.83, 1.5), 1.66, 2.0, fill=False, color='black', linewidth=2))
            ax5.set_xlim(-2.5, 2.5); ax5.set_ylim(0, 5)
            st.pyplot(fig5)

        # --- DOWNLOAD BUTTONS ---
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            csv_hit_data = hit_summary.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📊 Download {selected_batter} Monthly Summary (CSV)",
                data=csv_hit_data,
                file_name=f"{selected_batter}_Monthly_Hitting_Summary.csv",
                mime='text/csv',
            )
            
        with col_btn2:
            pdf_buffer = io.BytesIO()
            with PdfPages(pdf_buffer) as pdf:
                fig_tbl_hit, ax_tbl_hit = plt.subplots(figsize=(12, min(6, len(hit_summary)*0.5 + 1)))
                ax_tbl_hit.axis('tight')
                ax_tbl_hit.axis('off')
                ax_tbl_hit.set_title(f"Hitting Progression (Monthly): {selected_batter}", fontweight="bold", fontsize=16)
                
                tbl_hit = ax_tbl_hit.table(cellText=hit_summary.astype(str).values, colLabels=hit_summary.columns, loc='center', cellLoc='center')
                tbl_hit.auto_set_column_width(col=list(range(len(hit_summary.columns)))) 
                tbl_hit.scale(1, 2)
                tbl_hit.auto_set_font_size(False)
                tbl_hit.set_fontsize(10)
                pdf.savefig(fig_tbl_hit, bbox_inches='tight')
                plt.close(fig_tbl_hit)

                pdf.savefig(fig4, bbox_inches='tight')
                pdf.savefig(fig5, bbox_inches='tight')
            
            pdf_bytes = pdf_buffer.getvalue()
            st.download_button(
                label=f"📄 Download {selected_batter} Visual Report (PDF)",
                data=pdf_bytes,
                file_name=f"{selected_batter}_Hitting_Visuals.pdf",
                mime='application/pdf',
            )