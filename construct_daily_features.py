'''
Created by Morgan

step 3: Merge daily CSVs into one dataset with derived features.
- Input: ../../../Data/CDS_Climate/Raw/csv_daily/*_daily.csv (from hourly_to_daily.py)
- Output: ../../../Data/CDS_Climate/processed/daily_features/daily_features.csv
'''

import os
import re
import pandas as pd
import numpy as np

# ---- Paths ----
daily_csv_folder = "../../../Data/CDS_Climate/Raw/csv_daily/"
daily_out_folder = "../../../Data/CDS_Climate/processed/daily_features/"
os.makedirs(daily_out_folder, exist_ok=True)

out_file_csv = os.path.join(daily_out_folder, "daily_features.csv")

# ----------------------------
# Helper functions
# ----------------------------
def kelvin_to_celsius(k):
    return k - 273.15

def uv_to_speed_dir(u, v):
    """Convert u/v wind components to speed (m/s) and direction (deg FROM)."""
    speed = np.sqrt(u**2 + v**2)
    angle_rad = np.arctan2(v, u)
    angle_deg_math = np.degrees(angle_rad)
    dir_from = (270 - angle_deg_math) % 360
    return speed, dir_from

def saturation_vapor_pressure(Tc):
    """Tetens formula over water (hPa)."""
    return 6.112 * np.exp((17.67 * Tc) / (Tc + 243.5))

def vapor_pressure_from_dewpoint(Td_c):
    return saturation_vapor_pressure(Td_c)

def relative_humidity(Tc, Td_c):
    e = vapor_pressure_from_dewpoint(Td_c)
    es = saturation_vapor_pressure(Tc)
    return np.clip((e / es) * 100.0, 0, 100)

def apparent_temperature(Ta_c, ws_ms, e_hPa):
    """Steadman/BOM formula (°C)."""
    return Ta_c + 0.33 * e_hPa - 0.70 * ws_ms - 4.0

def wet_bulb_temperature_stull(Tc, RH):
    """Stull (2011) approximation (°C)."""
    RH = np.clip(RH, 1e-6, 100.0)
    return (Tc * np.arctan(0.151977 * np.sqrt(RH + 8.313659))
            + np.arctan(Tc + RH) - np.arctan(RH - 1.676331)
            + 0.00391838 * RH**1.5 * np.arctan(0.023101 * RH)
            - 4.686035)

# ----------------------------
# Load and stack all monthly CSVs per variable
# ----------------------------
print("Loading and stacking daily CSVs...")

var_groups = {}
for file in os.listdir(daily_csv_folder):
    if not file.endswith("_daily.csv"):
        continue

    var_match = re.match(r"^([a-z0-9]+)_", file)
    if not var_match:
        continue

    var_name = var_match.group(1)
    fpath = os.path.join(daily_csv_folder, file)
    df = pd.read_csv(fpath, parse_dates=["date"])

    # Append each file to its variable list
    var_groups.setdefault(var_name, []).append(df)

# Concatenate all months for each variable
daily_dfs = {}
for var, dfs in var_groups.items():
    daily_dfs[var] = pd.concat(dfs, ignore_index=True)
    print(f"  Combined {len(dfs)} monthly files for variable '{var}' ({len(daily_dfs[var])} rows)")

# ----------------------------
# Merge across variables
# ----------------------------
print("Merging variables by type...")
if "t2m" not in daily_dfs:
    raise ValueError("Missing base variable t2m (temperature) for merge.")

merged = daily_dfs["t2m"]
for var, df in daily_dfs.items():
    if var == "t2m":
        continue
    merged = merged.merge(df, on=["latitude", "longitude", "date"], how="outer")

print(f"Variables merged: {list(daily_dfs.keys())}")

# ----------------------------
# Derived features
# ----------------------------
print("Computing derived features...")

# Rename columns consistently
col_map = {
    "t2m_mean": "temp_mean_K",
    "t2m_min": "temp_min_K",
    "t2m_max": "temp_max_K",
    "d2m_mean": "dewpoint_mean_K",
    "d2m_min": "dewpoint_min_K",
    "d2m_max": "dewpoint_max_K",
    "u10_mean": "u10",
    "v10_mean": "v10",
    "tp_sum": "precipitation_m",
}
merged = merged.rename(columns=col_map)

# Wind speed & direction
if "u10" in merged.columns and "v10" in merged.columns:
    merged["wind_speed_ms"], merged["wind_dir_deg_from"] = uv_to_speed_dir(
        merged["u10"], merged["v10"]
    )
else:
    print("⚠️ Missing u10/v10 columns — skipping wind calculations.")
    merged["wind_speed_ms"] = np.nan
    merged["wind_dir_deg_from"] = np.nan

# Humidity & vapor pressure
if "temp_mean_K" in merged.columns and "dewpoint_mean_K" in merged.columns:
    Ta_c = kelvin_to_celsius(merged["temp_mean_K"])
    Td_c = kelvin_to_celsius(merged["dewpoint_mean_K"])
    merged["vapor_pressure_hPa"] = vapor_pressure_from_dewpoint(Td_c)
    merged["relative_humidity_pct"] = relative_humidity(Ta_c, Td_c)

    # Apparent & wet bulb temperatures
    merged["apparent_temp_C"] = apparent_temperature(
        Ta_c, merged["wind_speed_ms"], merged["vapor_pressure_hPa"]
    )
    merged["wet_bulb_C"] = wet_bulb_temperature_stull(Ta_c, merged["relative_humidity_pct"])
else:
    print("⚠️ Missing temperature or dewpoint data — skipping humidity calculations.")

# Convert precipitation from meters → mm
if "precipitation_m" in merged.columns:
    merged["precipitation_mm"] = merged["precipitation_m"] * 1000.0

# ----------------------------
# Save output
# ----------------------------
merged.to_csv(out_file_csv, index=False)
print(f"✓ Saved merged daily features to {out_file_csv}")
