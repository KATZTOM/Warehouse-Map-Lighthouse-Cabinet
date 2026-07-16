import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re

# ------------------------------------------------------------------
# 1. APPLICATION & PAGE INTERFACE CONFIG
# ------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="3D Warehouse Digital Twin")
st.title("🧱 Volumetric 3D Warehouse Digital Twin")
st.write("Solid 3D spatial layout featuring 100% opaque, non-transparent blocks.")

SHEET_URL = "https://docs.google.com/spreadsheets/d/12H6brX7AkORd6GBInlP0vYojQjrZYrO9vuZPT7g6Ffw/export?format=csv"

def bay_to_numeric(bay_str):
    num = 0
    for char in str(bay_str).upper().strip():
        if 'A' <= char <= 'Z':
            num = num * 26 + (ord(char) - ord('A') + 1)
    return num

# ------------------------------------------------------------------
# 2. DATA PROCESSING & GRID PARSER
# ------------------------------------------------------------------
@st.cache_data(ttl=15)
def load_and_parse_warehouse():
    try:
        raw_df = pd.read_csv(SHEET_URL, header=None)
        parsed_records = []
        
        for i in range(len(raw_df) - 1):
            row_current = raw_df.iloc[i]
            row_next = raw_df.iloc[i + 1]
            
            valid_cells = row_current.dropna().astype(str).str.strip()
            if valid_cells.empty:
                continue
                
            if any(re.match(r'^\d+_[A-Z]+_\d+$', cell) for cell in valid_cells):
                for col_idx in range(len(raw_df.columns)):
                    loc_code = str(row_current.iloc[col_idx]).strip()
                    sku_val = str(row_next.iloc[col_idx]).strip() if pd.notna(row_next.iloc[col_idx]) else ""
                    
                    if re.match(r'^\d+_[A-Z]+_\d+$', loc_code):
                        aisle, bay, level = loc_code.split('_')
                        
                        if sku_val == "" or sku_val.lower() in ['nan', 'empty'] or "order shipping" in sku_val.lower():
                            sku_val = ""
                            status = "Empty Slot"
                        elif "sample" in sku_val.lower():
                            status = "Sample Area"
                        else:
                            status = "Occupied"
                            
                        parsed_records.append({
                            "Location": loc_code,
                            "Aisle": int(aisle),
                            "Bay": bay,
                            "Bay_Num": bay_to_numeric(bay),
                            "Level": int(level),
                            "SKU": sku_val,
                            "Status": status
                        })
                        
        return pd.DataFrame(parsed_records)
    except Exception as e:
        st.error(f"Data Connection Error: {e}")
        return pd.DataFrame()

df = load_and_parse_warehouse()

if df.empty:
    st.warning("Re-connecting to live inventory stream...")
    st.stop()

# ------------------------------------------------------------------
# 3. SIDEBAR INTERACTIVE FILTERS
# ------------------------------------------------------------------
st.sidebar.header("🕹️ Map View Controls")
search_query = st.sidebar.text_input("🔍 Locate SKU:", "").strip()

all_aisles = sorted(df['Aisle'].unique())
selected_aisles = st.sidebar.multiselect("Active Aisles:", options=all_aisles, default=all_aisles)

show_empty = st.sidebar.checkbox("Show Empty Bins", value=True)
hide_text_labels = st.sidebar.checkbox("Clear Text Clutter (Hover Only Mode)", value=False)

filtered_df = df[df['Aisle'].isin(selected_aisles)].copy()
if not show_empty:
    filtered_df = filtered_df[filtered_df['Status'] != "Empty Slot"]

# Solid color themes
color_map = {
    "Occupied": "#2E5B82",     # Matte Steel Blue
    "Empty Slot": "#4B9E4B",   # Soft Rack Green
    "Sample Area": "#D98824"   # Warning Amber
}

# ------------------------------------------------------------------
# 4. SOLID 3D CUBOID GENERATOR WITH WIREFRAME CONTOURS
# ------------------------------------------------------------------
def add_solid_box(fig, x_min, x_max, y_min, y_max, z_min, z_max, color_hex, opacity=1.0, line_vectors=None):
    """Generates a 100% solid cuboid mesh and logs its matching wireframe outlines"""
    x_verts = [x_min, x_max, x_max, x_min, x_min, x_max, x_max, x_min]
    y_verts = [y_min, y_min, y_max, y_max, y_min, y_min, y_max, y_max]
    z_verts = [z_min, z_min, z_min, z_min, z_max, z_max, z_max, z_max] 
    
    i_idx = [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1]
    j_idx = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6]
    k_idx = [2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5]
    
    fig.add_trace(go.Mesh3d(
        x=x_verts, y=y_verts, z=z_verts,
        i=i_idx, j=j_idx, k=k_idx,
        color=color_hex,
        opacity=opacity, # Keeping this strictly 1.0 for true solid rendering
        flatshading=True,
        lighting=dict(ambient=0.7, diffuse=0.7, roughness=0.2, specular=0.1),
        hoverinfo='none',
        showlegend=False
    ))
    
    # Trace outlines for clean wireframe boundaries
    if line_vectors is not None:
        lx, ly, lz = line_vectors
        v = [
            [x_min, y_min, z_min], [x_max, y_min, z_min], [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_max], [x_max, y_min, z_max], [x_max, y_max, z_max], [x_min, y_max, z_max]
        ]
        trace_path = [0, 1, 2, 3, 0, 4, 5, 1, 5, 6, 2, 6, 7, 3, 7, 4]
        for p in trace_path:
            lx.append(v[p][0])
            ly.append(v[p][1])
            lz.append(v[p][2])
        lx.append(None); ly.append(None); lz.append(None)

# ------------------------------------------------------------------
# 5. ASSEMBLE 3D CANVAS & ENVIRONMENT
# ------------------------------------------------------------------
fig = go.Figure()

# Initialize global coordinate trackers for dark edge outlines
lx, ly, lz = [], [], []

# --- 1. THE CONCRETE FLOOR SLAB (100% Solid) ---
add_solid_box(
    fig, 
    x_min=17.0, x_max=25.0,    
    y_min=0.0, y_max=54.0,     
    z_min=0.1, z_max=0.5,      
    color_hex="#D5D8DC", 
    opacity=1.0,
    line_vectors=(lx, ly, lz)
)

# --- 2. THE STRUCTURAL BACK WALL (100% Solid) ---
add_solid_box(
    fig, 
    x_min=24.6, x_max=24.9, 
    y_min=0.0, y_max=54.0, 
    z_min=0.5, z_max=4.8,      
    color_hex="#AEB6BF", 
    opacity=1.0,
    line_vectors=(lx, ly, lz)
)

# --- 3. THE STORAGE RACK INVENTORY BINS (100% Solid) ---
dx, dy, dz = 0.38, 0.42, 0.38

for row in filtered_df.itertuples():
    x, y, z = row.Aisle, row.Bay_Num, row.Level
    
    if search_query:
        if search_query.lower() in str(row.SKU).lower():
            box_color = "#C0392B"  # Highlight match in Crimson
            box_opacity = 1.0
        else:
            box_color = "#ECEFF1"  # Unmatched items turn light gray but stay 100% solid
            box_opacity = 1.0     
    else:
        box_color = color_map.get(row.Status, "#7F7F7F")
        box_opacity = 1.0 # FORCE 100% SOLID BLOCKS
        
    add_solid_box(
        fig, 
        x_min=x-dx, x_max=x+dx, 
        y_min=y-dy, y_max=y+dy, 
        z_min=z-dz, z_max=z+dz, 
        color_hex=box_color, 
        opacity=box_opacity,
        line_vectors=(lx, ly, lz)
    )

# --- 4. RENDER WIREFRAME CONTOURS LAYER ---
fig.add_trace(go.Scatter3d(
    x=lx, y=ly, z=lz,
    mode='lines',
    line=dict(color='rgba(30, 30, 30, 0.9)', width=2.0),
    hoverinfo='skip',
    showlegend=False
))

# --- 5. EMBEDDED TEXT LAYER ---
if not hide_text_labels:
    text_df = filtered_df[filtered_df['SKU'].str.contains(search_query, case=False)] if search_query else filtered_df
    
    fig.add_trace(go.Scatter3d(
        x=text_df['Aisle'], y=text_df['Bay_Num'], z=text_df['Level'],
        mode='text',
        text=text_df.apply(lambda r: f"<b>{r['SKU']}</b>" if r['SKU'] else f"{r['Bay']}{r['Level']}", axis=1),
        textposition="middle center",
        textfont=dict(size=8, color="rgba(0, 0, 0, 0.9)"),
        hoverinfo='skip'
    ))

# --- 6. INVISIBLE HOVER DETECTION LAYER ---
fig.add_trace(go.Scatter3d(
    x=filtered_df['Aisle'], y=filtered_df['Bay_Num'], z=filtered_df['Level'],
    mode='markers',
    marker=dict(size=1, opacity=0.0),
    hoverinfo='text',
    hovertext=filtered_df.apply(lambda r: f"📍 <b>Loc:</b> {r['Location']}<br>📦 <b>SKU:</b> {r['SKU'] if r['SKU'] else 'Empty'}<br>📊 <b>Status:</b> {r['Status']}", axis=1),
    showlegend=False
))

# ------------------------------------------------------------------
# 6. AXIS MAP GEOMETRY & CAMERA VIEWPORTS
# ------------------------------------------------------------------
unique_bays = df[['Bay', 'Bay_Num']].drop_duplicates().sort_values('Bay_Num')

fig.update_layout(
    scene=dict(
        xaxis=dict(title='Aisle No.', tickmode='linear', dtick=1, showbackground=False),
        yaxis=dict(
            title='Bay Columns', 
            tickmode='array',
            tickvals=unique_bays['Bay_Num'].tolist(),
            ticktext=unique_bays['Bay'].tolist(),
            showbackground=False
        ),
        zaxis=dict(title='Level Height', tickmode='linear', dtick=1, range=[0.0, 5.0], showbackground=False),
        aspectmode='manual',
        aspectratio=dict(x=1.8, y=4.8, z=1.4) 
    ),
    margin=dict(l=0, r=0, b=0, t=10),
    height=850
)

st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# 7. DIRECTORY DATA VIEW
# ------------------------------------------------------------------
st.dataframe(filtered_df[['Location', 'SKU', 'Status']].sort_values(by=['Location']), use_container_width=True)