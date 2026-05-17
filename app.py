import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import subprocess
import os
import time

st.set_page_config(page_title="Ambulance Fleet Optimization", layout="wide", page_icon="🚑")

# --- UI Sidebar & Configuration ---
st.sidebar.title("🚑 Fleet Optimization Control")
st.sidebar.markdown("Use this panel to configure and re-run the optimization pipeline.")

st.sidebar.subheader("Optimization Parameters")
r1 = st.sidebar.slider("Primary Response Time (r1) min", min_value=5.0, max_value=30.0, value=10.0, step=1.0)
r2 = st.sidebar.slider("Secondary Response Time (r2) min", min_value=10.0, max_value=60.0, value=20.0, step=1.0)
alpha = st.sidebar.slider("Fleet Reliability (Alpha)", min_value=0.1, max_value=1.0, value=0.95, step=0.05)
n_clusters = st.sidebar.slider("Number of Demand Clusters", min_value=5, max_value=50, value=20, step=1)

import sys

def run_pipeline(full=True):
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    details_text = st.sidebar.empty()
    
    python_exec = sys.executable
    
    def run_cmd(cmd, step_name, base_progress, progress_chunk):
        status_text.text(f"Running {step_name}...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in process.stdout:
            if "Progress:" in line:
                details_text.text(line.strip())
            
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
            
        progress_bar.progress(base_progress + progress_chunk)
        details_text.empty()
    
    try:
        if full:
            # Step 1: Pre-processing
            cmd1 = [python_exec, "pre_processing.py", 
                    "--accident_input", r"data\raw\chainage_latlong_accident.csv", 
                    "--equipment_input", r"data\raw\EquipmentReport_LatLong.csv", 
                    "--output", r"data\processed\Accident_Lat_Lon.csv"]
            run_cmd(cmd1, "Step 1: Pre-processing Data", 0, 20)
            
            # Step 2: Clustering
            cmd2 = [python_exec, "clustering.py", 
                    "--input", r"data\processed\Accident_Lat_Lon.csv", 
                    "--output", r"data\processed\Demand_Points.csv", 
                    "--n_clusters", str(n_clusters)]
            run_cmd(cmd2, "Step 2: Clustering Demand Points", 20, 20)
            
            # Step 3: OD Matrix
            status_text.text("Step 3: Calculating Travel Times (API)... This may take 2-3 minutes.")
            cmd3 = [python_exec, "od_time_matrix.py", 
                    "--ambulance", r"data\raw\ambulance_locations.csv", 
                    "--demand", r"data\processed\Demand_Points.csv", 
                    "--output", r"data\processed\od_matrix.csv"]
            run_cmd(cmd3, "Step 3: Calculating Travel Times", 40, 40)
        else:
            progress_bar.progress(80)
            
        # Step 4: Optimization
        cmd4 = [python_exec, "pulp_optimization.py", 
                "--input", r"data\processed\od_matrix.csv", 
                "--r1", str(r1), 
                "--r2", str(r2), 
                "--alpha", str(alpha), 
                "--output", r"data\processed\optimized_deployment.csv"]
        run_cmd(cmd4, "Step 4: Running LP Optimization", 80, 20)
        
        status_text.success("Execution Complete!")
        time.sleep(2)
        status_text.empty()
        progress_bar.empty()
        
    except subprocess.CalledProcessError as e:
        status_text.error(f"Pipeline Failed at step: {' '.join(e.cmd)}")
        progress_bar.empty()

if st.sidebar.button("⚡ Run Fast Optimization Only"):
    run_pipeline(full=False)
    st.rerun()

if st.sidebar.button("🚀 Run FULL Pipeline (Takes longer)"):
    run_pipeline(full=True)
    st.rerun()

# --- Main App Dashboard ---
st.title("Ambulance Fleet Deployment Dashboard")
st.markdown("Visualizing optimal ambulance staging locations to maximize coverage for historical accident hotspots.")

# Load Data
def load_data():
    ambulances = pd.DataFrame()
    demands = pd.DataFrame()
    deployments = pd.DataFrame()
    
    if os.path.exists(r"data\raw\ambulance_locations.csv"):
        ambulances = pd.read_csv(r"data\raw\ambulance_locations.csv")
        # Ensure Ambulance_ID exists
        if 'Ambulance_ID' not in ambulances.columns:
            if 'ID' in ambulances.columns:
                ambulances.rename(columns={'ID': 'Ambulance_ID'}, inplace=True)
            else:
                ambulances['Ambulance_ID'] = ambulances.index
                
    if os.path.exists(r"data\processed\Demand_Points.csv"):
        demands = pd.read_csv(r"data\processed\Demand_Points.csv")
        
    if os.path.exists(r"data\processed\optimized_deployment.csv"):
        try:
            deployments = pd.read_csv(r"data\processed\optimized_deployment.csv")
        except pd.errors.EmptyDataError:
            deployments = pd.DataFrame()
            
    return ambulances, demands, deployments

ambulances, demands, deployments = load_data()

# Render Map
if not ambulances.empty and not demands.empty:
    if deployments.empty:
        st.warning("⚠️ **No active deployment plan found!** This usually means your time constraints (r1 / r2) are mathematically impossible to satisfy with the current Alpha fleet limit. Try relaxing the sliders (e.g., higher response times or higher Alpha) and click 'Run Fast Optimization Only' again.")
        
    st.subheader("Interactive Deployment Map")
    
    # Calculate center of map
    center_lat = demands['Demand_Point_Lat'].mean()
    center_lon = demands['Demand_Point_Lon'].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")
    
    # Add Demand Points
    for _, row in demands.iterrows():
        freq = row.get('Demand_Frequency', 1)
        folium.CircleMarker(
            location=[row['Demand_Point_Lat'], row['Demand_Point_Lon']],
            radius=freq * 0.5 + 3, # Scale by frequency
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.6,
            popup=f"Demand Cluster: {row.get('Cluster_ID', 'N/A')}<br>Frequency: {freq}"
        ).add_to(m)
        
    # Find deployed ambulances
    deployed_ambs = set()
    if not deployments.empty:
        deployed_ambs = set(deployments['Ambulance_ID'].unique())
        
    # Add Ambulances
    for _, row in ambulances.iterrows():
        lat_col = 'Ambulance_Lat' if 'Ambulance_Lat' in row else 'Latitude'
        lon_col = 'Ambulance_Lon' if 'Ambulance_Lon' in row else 'Longitude'
        
        amb_id = row['Ambulance_ID']
        is_deployed = amb_id in deployed_ambs # Only mark green if actually in the active set
        
        color = "green" if is_deployed else "lightgray"
        icon_type = "plus" if is_deployed else "minus"
        status = "Active" if is_deployed else "Standby"
        
        folium.Marker(
            location=[row[lat_col], row[lon_col]],
            icon=folium.Icon(color=color, icon=icon_type),
            popup=f"Ambulance Base: {amb_id}<br>Status: {status}"
        ).add_to(m)
        
    # Draw Assignment Lines
    if not deployments.empty:
        # Create dictionaries for fast lookup
        amb_dict = {}
        for _, row in ambulances.iterrows():
            lat_col = 'Ambulance_Lat' if 'Ambulance_Lat' in row else 'Latitude'
            lon_col = 'Ambulance_Lon' if 'Ambulance_Lon' in row else 'Longitude'
            amb_dict[row['Ambulance_ID']] = (row[lat_col], row[lon_col])
            
        dem_dict = {}
        for _, row in demands.iterrows():
            # In pulp script, Demand_Point_ID was Cluster_ID
            dem_id = row.get('Demand_Point_ID', row.get('Cluster_ID'))
            dem_dict[dem_id] = (row['Demand_Point_Lat'], row['Demand_Point_Lon'])
            
        for _, row in deployments.iterrows():
            amb_id = row['Ambulance_ID']
            dem_id = row['Assigned_Demand_Point_ID']
            
            if amb_id in amb_dict and dem_id in dem_dict:
                points = [amb_dict[amb_id], dem_dict[dem_id]]
                folium.PolyLine(points, color="blue", weight=2, opacity=0.8, dash_array="5").add_to(m)
                
    folium_static(m, width=1000, height=600)
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    deployed_count = len(deployed_ambs) if not deployments.empty else 0
    col1.metric("Active Ambulances", f"{deployed_count} / {len(ambulances)}")
    col2.metric("Total Demand Clusters", len(demands))
    
    if not deployments.empty:
        covered = len(deployments['Assigned_Demand_Point_ID'].unique())
        col3.metric("Clusters Covered", f"{covered} / {len(demands)}")
        
        st.subheader("Assignment Data")
        st.dataframe(deployments, use_container_width=True)
else:
    st.info("No data found. Please run the optimization pipeline from the sidebar to generate the map.")
