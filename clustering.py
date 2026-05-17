import argparse
import pandas as pd
import numpy as np
import os
from sklearn.cluster import KMeans

def cluster_data(input_file, output_file, n_clusters):
    print(f"Loading processed accident data from {input_file}...")
    if input_file.endswith('.csv'):
        df = pd.read_csv(input_file)
    else:
        df = pd.read_excel(input_file)

    # Need Accident_Lat and Accident_Lon
    if 'Accident_Lat' not in df.columns or 'Accident_Lon' not in df.columns:
        raise ValueError("Input dataset must contain 'Accident_Lat' and 'Accident_Lon' columns")

    # Drop NaNs
    df = df.dropna(subset=['Accident_Lat', 'Accident_Lon'])
    
    X = df[['Accident_Lat', 'Accident_Lon']]
    
    print(f"Performing KMeans clustering with {n_clusters} clusters...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['Cluster_ID'] = kmeans.fit_predict(X)
    
    # Calculate demand frequency (number of accidents per cluster)
    cluster_counts = df['Cluster_ID'].value_counts().reset_index()
    cluster_counts.columns = ['Cluster_ID', 'Demand_Frequency']
    
    # Get cluster centers
    centroids = pd.DataFrame(kmeans.cluster_centers_, columns=['Demand_Point_Lat', 'Demand_Point_Lon'])
    centroids['Cluster_ID'] = centroids.index
    
    # Merge centers with frequencies
    output_df = pd.merge(centroids, cluster_counts, on='Cluster_ID')
    
    # Sort by Cluster_ID
    output_df = output_df.sort_values('Cluster_ID').reset_index(drop=True)
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"Saving demand points to {output_file}...")
    output_df.to_csv(output_file, index=False)
    print("Clustering complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cluster accident points into demand points")
    parser.add_argument("--input", required=True, help="Path to pre-processed accident dataset")
    parser.add_argument("--output", required=True, help="Path to output demand points dataset")
    parser.add_argument("--n_clusters", type=int, default=20, help="Number of clusters (default: 20)")
    
    args = parser.parse_args()
    cluster_data(args.input, args.output, args.n_clusters)
