import argparse
import pandas as pd
import pulp
import os

def optimize_deployment(input_matrix_file, r1, r2, alpha, output_file):
    print(f"Loading OD matrix from {input_matrix_file}...")
    df_matrix = pd.read_csv(input_matrix_file)
    
    # Need Ambulance_ID, Demand_Point_ID, Travel_Time
    if not all(col in df_matrix.columns for col in ['Ambulance_ID', 'Demand_Point_ID', 'Travel_Time']):
        raise ValueError("OD Matrix must contain 'Ambulance_ID', 'Demand_Point_ID', and 'Travel_Time' columns")

    ambulances = df_matrix['Ambulance_ID'].unique().tolist()
    demand_points = df_matrix['Demand_Point_ID'].unique().tolist()
    
    # Create travel time dictionary
    travel_times = {}
    for _, row in df_matrix.iterrows():
        a_id = row['Ambulance_ID']
        d_id = row['Demand_Point_ID']
        t_time = row['Travel_Time']
        if a_id not in travel_times:
            travel_times[a_id] = {}
        travel_times[a_id][d_id] = t_time

    # We assume uniform demand frequency if not provided, else 1
    # For a full model, demand frequency would be needed, but README only specifies OD matrix as input
    
    print(f"Formulating optimization model (r1={r1}, r2={r2}, alpha={alpha})...")
    # Define problem
    prob = pulp.LpProblem("Ambulance_Deployment_Optimization", pulp.LpMaximize)
    
    # Decision variables
    # x[i, j] = 1 if ambulance i is assigned to demand point j
    x = pulp.LpVariable.dicts("assign", 
                              [(i, j) for i in ambulances for j in demand_points], 
                              cat='Binary')
                              
    # y[i] = 1 if ambulance i is deployed
    y = pulp.LpVariable.dicts("deploy", ambulances, cat='Binary')
    
    # z[j] = 1 if demand point j is covered within r1
    z = pulp.LpVariable.dicts("covered_r1", demand_points, cat='Binary')
    
    # Objective: Maximize coverage within r1
    prob += pulp.lpSum([z[j] for j in demand_points]), "Maximize_Coverage"
    
    # Constraints
    # 1. Coverage constraint for r1
    for j in demand_points:
        prob += pulp.lpSum([x[(i, j)] for i in ambulances if travel_times[i].get(j, float('inf')) <= r1]) >= z[j]
        
    # 2. Coverage constraint for r2 (All demand points must be covered within r2)
    # If a demand point cannot be covered by ANY ambulance within r2, we skip the strict constraint
    # to avoid infeasibility, or we do best-effort.
    for j in demand_points:
        valid_ambulances = [i for i in ambulances if travel_times[i].get(j, float('inf')) <= r2]
        if valid_ambulances:
            prob += pulp.lpSum([x[(i, j)] for i in valid_ambulances]) >= 1
            
    # 3. Each ambulance can be assigned to at most N demand points (assuming 1 for simplicity, or relaxing)
    # The README output "Ambulance_ID, Assigned_Demand_Point_ID" implies an ambulance is assigned to specific points.
    for j in demand_points:
        # Each demand point is assigned exactly to 1 ambulance (or at least 1)
        prob += pulp.lpSum([x[(i, j)] for i in ambulances]) >= 1

    # 4. Link x and y (if ambulance i is assigned, it must be deployed)
    for i in ambulances:
        for j in demand_points:
            prob += x[(i, j)] <= y[i]
            
    # 5. Limit deployed ambulances based on alpha (e.g. only deploy a fraction)
    # Let's interpret alpha as proportion of total fleet to deploy, or reliability.
    max_ambulances = int(len(ambulances) * alpha)
    if max_ambulances < 1: max_ambulances = 1
    prob += pulp.lpSum([y[i] for i in ambulances]) <= max_ambulances
    
    print("Solving optimization model...")
    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    status = pulp.LpStatus[prob.status]
    print(f"Optimization Status: {status}")
    
    # Extract results
    results = []
    if status == 'Optimal':
        for i in ambulances:
            for j in demand_points:
                if pulp.value(x[(i, j)]) == 1:
                    results.append({
                        'Ambulance_ID': i,
                        'Assigned_Demand_Point_ID': j
                    })
    else:
        print("Warning: Could not find optimal solution with strict constraints.")
        print("Consider increasing r1/r2 or alpha.")
        
    df_results = pd.DataFrame(results)
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    print(f"Saving deployment plan to {output_file}...")
    df_results.to_csv(output_file, index=False)
    print("Optimization complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize ambulance deployment using PuLP")
    parser.add_argument("--input", required=True, help="Path to OD time matrix dataset")
    parser.add_argument("--r1", type=float, default=10.0, help="Primary response time in minutes")
    parser.add_argument("--r2", type=float, default=20.0, help="Secondary response time in minutes")
    parser.add_argument("--alpha", type=float, default=0.95, help="Alpha reliability factor (e.g., 0.95)")
    parser.add_argument("--output", required=True, help="Path to output deployment plan")
    
    args = parser.parse_args()
    optimize_deployment(args.input, args.r1, args.r2, args.alpha, args.output)
