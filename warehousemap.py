import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
import ssl
import urllib.request
import io
import streamlit.components.v1 as components

# ------------------------------------------------------------------
# 1. APPLICATION & PAGE INTERFACE CONFIG
# ------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="3D Warehouse Digital Twin")
st.title("🧱 Professional 3D Warehouse Digital Twin")
st.write("Live interactive layout with 3D modeling and high-definition scrollable 2D floor plans.")

SHEET_URL = "https://docs.google.com/spreadsheets/d/12H6brX7AkORd6GBInlP0vYojQjrZYrO9vuZPT7g6Ffw/export?format=csv"

# Physical X-axis mapping to group back-to-back racks and leave wide walking paths
X_PHYSICAL_MAPPING = {
    24: 24.0,  # Single-sided rack against back wall
    23: 22.35, # Spaced back-to-back pair (faced North)
    22: 21.65, # Spaced back-to-back pair (faced South)
    21: 19.35, # Spaced back-to-back pair (faced North)
    20: 18.65, # Spaced back-to-back pair (faced South)
    19: 16.35, # Spaced back-to-back pair (faced North)
    18: 15.65  # Spaced back-to-back pair (faced South)
}

# Spacious 2D Layout heights - prevents 75px markers from crashing vertically
Y_2D_BLUEPRINT_MAPPING = {
    18: 1.0,
    19: 2.5,  # Clean vertical separation for back-to-back rows
    20: 4.5,  # Open walking aisle walkway lane
    21: 6.0,  # Clean vertical separation for back-to-back rows
    22: 8.0,  # Open walking aisle walkway lane
    23: 9.5,  # Clean vertical separation for back-to-back rows
    24: 11.5  # Top row wall path
}

def bay_to_numeric(bay_str):
    num = 0
    for char in str(bay_str).upper().strip():
        if 'A' <= char <= 'Z':
            num = num * 26 + (ord(char) - ord('A') + 1)
    return num

# Verify if a bay falls on a physical rack line based on your clipboard sketch
def is_physical_shelf(aisle, bay_num):
    if aisle in [18, 19]:
        if 1 <= bay_num <= 20:   # A to T
            return True
        if 23 <= bay_num <= 46:  # W to AT
            return True
        if 49 <= bay_num <= 50:  # AW to AX
            return True
    elif aisle in [20, 21, 22, 23, 24]:
        if 1 <= bay_num <= 20:   # A to T
            return True
        if 23 <= bay_num <= 46:  # W to AT
            return True
        if 49 <= bay_num <= 52:  # AW to AZ
            return True
    return False

# ------------------------------------------------------------------
# 2. DATA PROCESSING & GRID PARSER (WITH SSL BYPASS)
# ------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_and_parse_warehouse():
    try:
        context = ssl._create_unverified_context()
        
        req = urllib.request.Request(
            SHEET_URL, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, context=context) as response:
            csv_data = response.read().decode('utf-8')
            
        raw_df = pd.read_csv(io.StringIO(csv_data), header=None)
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
                        aisle_val, bay, level_val = loc_code.split('_')
                        aisle = int(aisle_val)
                        bay_num = bay_to_numeric(bay)
                        level = int(level_val)
                        
                        if is_physical_shelf(aisle, bay_num):
                            if sku_val == "" or sku_val.lower() in ['nan', 'empty'] or "order shipping" in sku_val.lower():
                                sku_val = ""
                                status = "Empty Slot"
                            elif "sample" in sku_val.lower():
                                status = "Sample Area"
                            else:
                                status = "Occupied"
                                
                            parsed_records.append({
                                "Location": loc_code,
                                "Aisle": aisle,
                                "Aisle_Phys": X_PHYSICAL_MAPPING.get(aisle, float(aisle)),
                                "Aisle_2D": Y_2D_BLUEPRINT_MAPPING.get(aisle, float(aisle)), # Track spacious 2D heights
                                "Bay": bay,
                                "Bay_Num": bay_num,
                                "Level": level,
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
# 3. SIDEBAR VIEW SELECTOR & FILTERS
# ------------------------------------------------------------------
st.sidebar.markdown("### 🗺️ Display Perspective")
view_mode = st.sidebar.radio(
    label="Choose perspective mode:",
    options=["3D Perspective (All Levels)", "Level 1 (2D Floor Plan)", "Level 2 (2D Floor Plan)", "Level 3 (2D Floor Plan)", "Level 4 (2D Floor Plan)"],
    index=0,
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.header("🕹️ Map View Controls")
search_query = st.sidebar.text_input("🔍 Locate SKU:", "").strip()

all_aisles = sorted(df['Aisle'].unique())
selected_aisles = st.sidebar.multiselect("Active Aisles:", options=all_aisles, default=all_aisles)

show_empty = st.sidebar.checkbox("Show Empty Bins", value=True)
hide_text_labels = st.sidebar.checkbox("Clear Text Clutter (Hover Only Mode)", value=False)

if "3D" not in view_mode:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📏 2D Blueprint Scaling")
    map_scale = st.sidebar.slider("🗺️ Map Width (Horizontal Expansion)", min_value=2000, max_value=5000, value=3500, step=100)
    bin_size = st.sidebar.slider("🟩 Bin Block Size (Box Scale)", min_value=20, max_value=100, value=55)
    font_size = st.sidebar.slider("🔤 SKU Label Font Size", min_value=8, max_value=16, value=10)
    show_steel_frames = False
else:
    show_steel_frames = st.sidebar.checkbox("Show Structural Steel Rack Frames", value=True)

# Filter baseline data
filtered_df = df[df['Aisle'].isin(selected_aisles)].copy()
if not show_empty:
    filtered_df = filtered_df[filtered_df['Status'] != "Empty Slot"]

# Solid color themes
color_map = {
    "Occupied": "#2E5B82",     # Matte Steel Blue
    "Empty Slot": "#4B9E4B",   # Soft Rack Green
    "Sample Area": "#D98824"   # Warning Amber
}

# Apply global query highlighting
if search_query:
    filtered_df['Render_Color'] = filtered_df.apply(
        lambda r: "#C0392B" if search_query.lower() in str(r['SKU']).lower() else "#ECEFF1", axis=1
    )
    filtered_df['Render_Opacity'] = 1.0
else:
    filtered_df['Render_Color'] = filtered_df['Status'].map(color_map).fillna("#7F7F7F")
    filtered_df['Render_Opacity'] = 1.0

# ------------------------------------------------------------------
# 4. SOLID 3D CUBOID GENERATOR WITH WIREFRAME CONTOURS
# ------------------------------------------------------------------
def add_solid_box(fig, x_min, x_max, y_min, y_max, z_min, z_max, color_hex, opacity=1.0, line_vectors=None):
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
        opacity=opacity,
        flatshading=True,
        lighting=dict(ambient=0.75, diffuse=0.6, roughness=0.1, specular=0.1),
        hoverinfo='none',
        showlegend=False
    ))
    
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
# 5. RENDERING ROUTER (3D MODEL vs 2D SCROLLABLE BLUEPRINT VIEW)
# ------------------------------------------------------------------
unique_bays = df[['Bay', 'Bay_Num']].drop_duplicates().sort_values('Bay_Num')

if "3D" in view_mode:
    # --------------------------------------------------------------
    # PERSPECTIVE A: FULL 3D MODEL
    # --------------------------------------------------------------
    fig = go.Figure()
    lx, ly, lz = [], [], []

    add_solid_box(fig, x_min=14.5, x_max=25.0, y_min=0.0, y_max=54.0, z_min=0.1, z_max=0.45, color_hex="#D5D8DC", opacity=1.0, line_vectors=(lx, ly, lz))
    add_solid_box(fig, x_min=24.5, x_max=24.8, y_min=0.0, y_max=54.0, z_min=0.45, z_max=4.8, color_hex="#AEB6BF", opacity=1.0, line_vectors=(lx, ly, lz))

    dx, dy, box_height = 0.22, 0.40, 0.38  
    filtered_df['Z_Min'] = filtered_df['Level'] - 0.55
    filtered_df['Z_Max'] = filtered_df['Z_Min'] + box_height
    filtered_df['Z_Center'] = (filtered_df['Z_Min'] + filtered_df['Z_Max']) / 2.0

    for row in filtered_df.itertuples():
        add_solid_box(
            fig, 
            x_min=row.Aisle_Phys-dx, x_max=row.Aisle_Phys+dx, 
            y_min=row.Bay_Num-dy, y_max=row.Bay_Num+dy, 
            z_min=row.Z_Min, z_max=row.Z_Max, 
            color_hex=row.Render_Color, 
            opacity=row.Render_Opacity,
            line_vectors=(lx, ly, lz)
        )

    fig.add_trace(go.Scatter3d(x=lx, y=ly, z=lz, mode='lines', line=dict(color='rgba(40, 40, 40, 0.9)', width=1.5), hoverinfo='skip', showlegend=False))

    if show_steel_frames:
        steel_upright_x, steel_upright_y, steel_upright_z = [], [], []
        steel_beam_x, steel_beam_y, steel_beam_z = [], [], []
        
        for aisle in selected_aisles:
            x_p = X_PHYSICAL_MAPPING.get(aisle)
            if x_p is None:
                continue
            segments = [(0.5, 20.5), (22.5, 46.5)]
            if aisle in [18, 19]:
                segments.append((48.5, 50.5))
            else:
                segments.append((48.5, 52.5))
                
            for y_start, y_end in segments:
                for y_p in [y_start, y_end]:
                    for x_off in [-0.3, 0.3]:
                        steel_upright_x.extend([x_p + x_off, x_p + x_off, None])
                        steel_upright_y.extend([y_p, y_p, None])
                        steel_upright_z.extend([0.45, 4.3, None])
                
                for lvl in [0.45, 1.45, 2.45, 3.45, 4.3]:
                    for x_off in [-0.3, 0.3]:
                        steel_beam_x.extend([x_p + x_off, x_p + x_off, None])
                        steel_beam_y.extend([y_start, y_end, None])
                        steel_beam_z.extend([lvl, lvl, None])
                        
        fig.add_trace(go.Scatter3d(x=steel_upright_x, y=steel_upright_y, z=steel_upright_z, mode='lines', line=dict(color='rgba(41, 128, 185, 0.95)', width=3.5), hoverinfo='skip', showlegend=False))
        fig.add_trace(go.Scatter3d(x=steel_beam_x, y=steel_beam_y, z=steel_beam_z, mode='lines', line=dict(color='rgba(230, 126, 34, 0.95)', width=2.5), hoverinfo='skip', showlegend=False))

    if not hide_text_labels:
        text_df = filtered_df[filtered_df['SKU'].str.contains(search_query, case=False)] if search_query else filtered_df
        fig.add_trace(go.Scatter3d(
            x=text_df['Aisle_Phys'], y=text_df['Bay_Num'], z=text_df['Z_Center'], 
            mode='text',
            text=text_df.apply(lambda r: f"<b>{r['SKU']}</b>" if r['SKU'] else f"{r['Bay']}{r['Level']}", axis=1),
            textposition="middle center",
            textfont=dict(size=8, color="rgba(0, 0, 0, 0.9)"),
            hoverinfo='skip'
        ))

    fig.add_trace(go.Scatter3d(
        x=filtered_df['Aisle_Phys'], y=filtered_df['Bay_Num'], z=filtered_df['Z_Center'],
        mode='markers',
        marker=dict(size=1, opacity=0.0),
        hoverinfo='text',
        hovertext=filtered_df.apply(lambda r: f"📍 <b>Loc:</b> {r['Location']}<br>📦 <b>SKU:</b> {r['SKU'] if r['SKU'] else 'Empty'}<br>📊 <b>Status:</b> {r['Status']}", axis=1),
        showlegend=False
    ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Aisle No.', tickmode='array', tickvals=list(X_PHYSICAL_MAPPING.values()), ticktext=[f"Aisle {k}" for k in X_PHYSICAL_MAPPING.keys()], showbackground=False),
            yaxis=dict(title='Bay Columns', tickmode='array', tickvals=unique_bays['Bay_Num'].tolist(), ticktext=unique_bays['Bay'].tolist(), showbackground=False, autorange='reversed'),
            zaxis=dict(title='Level Height', tickmode='linear', dtick=1, range=[0.0, 5.0], showbackground=False),
            aspectmode='manual',
            aspectratio=dict(x=1.8, y=4.8, z=1.4) 
        ),
        margin=dict(l=0, r=0, b=0, t=10),
        height=850
    )
    
    st.plotly_chart(fig, use_container_width=True)

else:
    # --------------------------------------------------------------
    # PERSPECTIVE B: FIXED SCATTER-BASED 2D BLUEPRINT VIEW
    # --------------------------------------------------------------
    target_level = int(re.search(r'\d+', view_mode).group())
    level_df = filtered_df[filtered_df['Level'] == target_level].copy()
    
    st.info(f"📋 Displaying 2D Architectural blueprint for Level {target_level}. Scroll horizontally to view the entire warehouse length.")

    if search_query:
        level_df['Text_Color'] = level_df.apply(
            lambda r: 'white' if search_query.lower() in str(r['SKU']).lower() else 'black', axis=1
        )
    else:
        level_df['Text_Color'] = level_df['Status'].apply(lambda s: 'white' if s == 'Occupied' else 'black')

    fig = go.Figure()

    # --- OPTIMIZED BATCHED RENDER ENGINE ---
    # Instead of loops making hundreds of shapes, group data by status
    for status_type, group in level_df.groupby('Status'):
        bx, by = [], []
        for row in group.itertuples():
            # Trace out a 2D rectangle path seamlessly using a single vector line array
            bx.extend([row.Bay_Num - 0.38, row.Bay_Num + 0.38, row.Bay_Num + 0.38, row.Bay_Num - 0.38, row.Bay_Num - 0.38, None])
            by.extend([row.Aisle_2D - 0.38, row.Aisle_2D - 0.38, row.Aisle_2D + 0.38, row.Aisle_2D + 0.40, row.Aisle_2D - 0.38, None])
            
        fig.add_trace(go.Scatter(
            x=bx, y=by,
            mode='lines',
            fill='toself',
            fillcolor=color_map.get(status_type, "#7F7F7F"),
            line=dict(color="rgb(40, 40, 40)", width=1.5),
            hoverinfo='skip',
            showlegend=False
        ))

    # Add corridor guide boundaries along the clean 2D elevations
    for aisle, y_val in Y_2D_BLUEPRINT_MAPPING.items():
        fig.add_shape(
            type="line",
            x0=0.5, x1=53.5,
            y0=y_val, y1=y_val,
            line=dict(color="rgba(180, 180, 180, 0.4)", width=1, dash="dash"),
        )

    fig.update_layout(
        xaxis=dict(
            title='Bay Columns (A-Z Left to Right)', 
            tickmode='array', 
            tickvals=unique_bays['Bay_Num'].tolist(), 
            ticktext=unique_bays['Bay'].tolist(),
            gridcolor='rgb(240, 240, 240)',
            zeroline=False,
            range=[0.0, 53.0],
            fixedrange=True             
        ),
        yaxis=dict(
            # Added standalone padding standoff and expanded layout boundaries
            title=dict(text='Aisles (Wide physical paths preserved)', standoff=45), 
            tickmode='array', 
            tickvals=list(Y_2D_BLUEPRINT_MAPPING.values()), 
            ticktext=[f"Aisle {k}" for k in Y_2D_BLUEPRINT_MAPPING.keys()],
            gridcolor='rgb(240, 240, 240)',
            zeroline=False,
            range=[0.0, 12.5], 
            fixedrange=True             
        ),
        plot_bgcolor='white',
        margin=dict(l=140, r=40, b=40, t=10), # Opened left padding room for clean text readouts
        width=map_scale,  
        height=660, 
        autosize=False
    )

    # UI CLEANUP: Keeps the fast scrolling engine active but strips away lasso tools and box selection overlays
    chart_html = fig.to_html(include_plotlyjs='cdn', full_html=False, config={'modeBarButtonsToRemove': ['lasso2d', 'select2d']})

    scroll_wrapper_html = f"""
    <div style="overflow-x: auto; overflow-y: hidden; width: 100%; border: 1px solid #E6E8EA; border-radius: 6px; padding: 5px; background-color: #ffffff;">
        <div style="width: {map_scale}px;">
            {chart_html}
        </div>
    </div>
    """
    
    components.html(scroll_wrapper_html, height=710, scrolling=False)

# ------------------------------------------------------------------
# 6. DIRECTORY DATA VIEW
# ------------------------------------------------------------------
st.dataframe(filtered_df[['Location', 'SKU', 'Status']].sort_values(by=['Location']), use_container_width=True)
