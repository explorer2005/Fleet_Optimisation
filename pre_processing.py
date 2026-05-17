import argparse
import pandas as pd
import numpy as np
import os

def pre_process(accident_input, equipment_input, output):
    print(f"Loading accident data from {accident_input}...")
    # Handle CSV or Excel based on extension
    if accident_input.endswith('.csv'):
        df1 = pd.read_csv(accident_input)
    else:
        df1 = pd.read_excel(accident_input)
        
    print(f"Loading equipment data from {equipment_input}...")
    if equipment_input.endswith('.csv'):
        df2 = pd.read_csv(equipment_input)
    else:
        df2 = pd.read_excel(equipment_input)

    # Filter for fatal accidents if column exists
    if 'Nature of Accident' in df1.columns:
        df1 = df1[df1['Nature of Accident'] == 'Fatal']

    # Clean equipment chainage
    if 'CHAINAGE' in df2.columns:
        df2['CHAINAGE'] = df2['CHAINAGE'].astype(str)
        df2 = df2[~df2['CHAINAGE'].isin(['MTCC', 'STCC', 'CCTV-NARSINGI-FLYOVER 152.050-IN'])]
        
        chainage_nums = []
        # Extract numeric part
        for i, row in df2.iterrows():
            equipment_chainage = str(row['CHAINAGE']).split('_')[0]
            try:
                chainage_nums.append(float(equipment_chainage))
            except ValueError:
                chainage_nums.append(np.nan)
                
        df2['CHAINAGE_NUM'] = chainage_nums
        df2 = df2.dropna(subset=['CHAINAGE_NUM'])
        df2['CHAINAGE'] = df2['CHAINAGE_NUM']
        df2 = df2.drop(columns=['CHAINAGE_NUM'])

    # Sort accident data
    if 'PPT_Chainage No' in df1.columns:
        df1['PPT_Chainage No'] = pd.to_numeric(df1['PPT_Chainage No'], errors='coerce')
        df1 = df1.dropna(subset=['PPT_Chainage No'])
        sorted_df = df1.sort_values(by=['PPT_Chainage No'], ascending=True).reset_index(drop=True)
    else:
        sorted_df = df1

    # Map accident chainage to nearest equipment chainage
    print("Mapping accident chainage to nearest equipment...")
    def find_nearest_equip(acc_chainage):
        if not pd.isna(acc_chainage):
            differences = np.abs(df2['CHAINAGE'] - acc_chainage)
            nearest_idx = differences.idxmin()
            return df2.loc[nearest_idx]
        return pd.Series()

    if 'PPT_Chainage No' in sorted_df.columns:
        matched_equip = sorted_df['PPT_Chainage No'].apply(find_nearest_equip)
        
        # Add lat/lon
        sorted_df['Accident_Lat'] = matched_equip['LATITUDE']
        sorted_df['Accident_Lon'] = matched_equip['LONGITUDE']
        sorted_df['nearest_equip_chainage'] = matched_equip['CHAINAGE']
        
        # Rename column for output consistency if required
        sorted_df = sorted_df.rename(columns={'PPT_Chainage No': 'Accident_Chainage'})

    # Make output directory if it doesn't exist
    os.makedirs(os.path.dirname(output), exist_ok=True)
    
    print(f"Saving processed data to {output}...")
    sorted_df.to_csv(output, index=False)
    print("Pre-processing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map accident chainage to equipment lat/lon")
    parser.add_argument("--accident_input", required=True, help="Path to raw accident dataset")
    parser.add_argument("--equipment_input", required=True, help="Path to equipment dataset")
    parser.add_argument("--output", required=True, help="Path to output processed dataset")
    
    args = parser.parse_args()
    pre_process(args.accident_input, args.equipment_input, args.output)
