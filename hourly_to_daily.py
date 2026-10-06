'''
Created by Morgan

step 2: Convert ERA5 hourly CSVs into daily aggregated CSVs.
- Input: csv_files/*_hourly.csv (from download.py)
- Output: csv_daily/{var}_{year}_{month}_daily.csv
'''

import os
import pandas as pd

# Folders
raw_csv_folder = "../../../Data/CDS_Climate/Raw/csv_files/"
daily_csv_folder = "../../../Data/CDS_Climate/Raw/csv_daily/"
os.makedirs(daily_csv_folder, exist_ok=True)

# Variables and short names (match what download.py saved)
variables = {
    "t2m": "2m_temperature",
    "d2m": "2m_dewpoint_temperature",
    "u10": "10m_u_component_of_wind",
    "v10": "10m_v_component_of_wind",
    "tp": "total_precipitation",
}

# Loop through hourly CSV files
for file in os.listdir(raw_csv_folder):
    if not file.endswith("_hourly.csv"):
        continue

    var = file.split("_")[0]  # short var name (e.g., t2m, d2m)
    if var not in variables:
        continue

    file_path = os.path.join(raw_csv_folder, file)
    print(f"Processing {file_path} ...")

    df = pd.read_csv(file_path, parse_dates=["date"])

    # Group by lat, lon, date
    agg_funcs = {}

    if var in ["t2m", "d2m"]:  # temps, dewpoint: need mean, min, max
        agg_funcs[var] = ["mean", "min", "max"]
    elif var == "tp":  # precip: sum
        agg_funcs[var] = ["sum"]
    else:  # wind components: mean only
        agg_funcs[var] = ["mean"]

    daily = (
        df.groupby(["latitude", "longitude", "date"])
        .agg(agg_funcs)
        .reset_index()
    )

    # Flatten multi-level columns
    daily.columns = [
        "_".join(col).strip("_") if isinstance(col, tuple) else col
        for col in daily.columns
    ]

    # Save daily CSV
    out_file = os.path.join(daily_csv_folder, file.replace("_hourly.csv", "_daily.csv"))
    daily.to_csv(out_file, index=False)
    print(f"Saved daily file: {out_file}")
