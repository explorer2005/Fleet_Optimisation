import argparse
import pandas as pd
import requests
import os
import time

def calculate_time_matrix(ambulance_file, demand_file, output_file):
    print(f"Loading ambulance locations from {ambulance_file}...")
    ambulances = pd.read_csv(ambulance_file)
    print(f"Loading demand points from {demand_file}...")
    demands = pd.read_csv(demand_file)

    # Ensure required columns
    req_amb = ['Ambulance_ID', 'Ambulance_Lat', 'Ambulance_Lon']
    for col in req_amb:
        if col not in ambulances.columns:
            # Try to map columns if standard names aren't used
            if col == 'Ambulance_ID':
                if 'ID' in ambulances.columns:
                    ambulances.rename(columns={'ID': 'Ambulance_ID'}, inplace=True)
                else:
                    ambulances['Ambulance_ID'] = ambulances.index
            elif col == 'Ambulance_Lat' and 'Latitude' in ambulances.columns:
                ambulances.rename(columns={'Latitude': 'Ambulance_Lat'}, inplace=True)
            elif col == 'Ambulance_Lon' and 'Longitude' in ambulances.columns:
                ambulances.rename(columns={'Longitude': 'Ambulance_Lon'}, inplace=True)
            else:
                raise ValueError(f"Ambulance file missing required column: {col}")

    req_dem = ['Cluster_ID', 'Demand_Point_Lat', 'Demand_Point_Lon']
    for col in req_dem:
        if col not in demands.columns:
            raise ValueError(f"Demand file missing required column: {col}")

    demands.rename(columns={'Cluster_ID': 'Demand_Point_ID'}, inplace=True)

    osrm_url = "http://router.project-osrm.org/route/v1/driving/"
    
    results = []
    
    print(f"Calculating travel times for {len(ambulances)} ambulances and {len(demands)} demand points...")
    total_requests = len(ambulances) * len(demands)
    req_count = 0

    for _, amb_row in ambulances.iterrows():
        amb_id = amb_row['Ambulance_ID']
        amb_lat = amb_row['Ambulance_Lat']
        amb_lon = amb_row['Ambulance_Lon']
        
        for _, dem_row in demands.iterrows():
            dem_id = dem_row['Demand_Point_ID']
            dem_lat = dem_row['Demand_Point_Lat']
            dem_lon = dem_row['Demand_Point_Lon']
            
            url = f"{osrm_url}{amb_lon},{amb_lat};{dem_lon},{dem_lat}?overview=false"
            
            try:
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if data['code'] == 'Ok':
                    # Extract duration in minutes
                    travel_time = data['routes'][0]['duration'] / 60.0
                else:
                    travel_time = float('inf')
            except Exception as e:
                print(f"Error fetching OSRM data: {e}")
                travel_time = float('inf')
                
            results.append({
                'Ambulance_ID': amb_id,
                'Demand_Point_ID': dem_id,
                'Travel_Time': travel_time
            })
            
            req_count += 1
            if req_count % 10 == 0:
                print(f"Progress: {req_count}/{total_requests}")
            time.sleep(0.1) # Be nice to public API

    df_matrix = pd.DataFrame(results)
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    print(f"Saving OD matrix to {output_file}...")
    df_matrix.to_csv(output_file, index=False)
    print("OD Time Matrix calculation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate travel time matrix using OSRM")
    parser.add_argument("--ambulance", required=True, help="Path to ambulance locations dataset")
    parser.add_argument("--demand", required=True, help="Path to demand points dataset")
    parser.add_argument("--output", required=True, help="Path to output OD time matrix")
    
    args = parser.parse_args()
    calculate_time_matrix(args.ambulance, args.demand, args.output)
