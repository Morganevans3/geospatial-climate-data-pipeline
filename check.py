"""
Created by Morgan
Purpose: Check for missing or incomplete daily aggregate climate files.

This script scans ../../Data/CDS_Climate/Raw/csv_daily/
and reports:
  - Files with missing values (NaN)
  - Files with zero or very few rows
  - Missing months or variables
  - Missing or out-of-bounds latitude/longitude values
"""

import os
import pandas as pd
import numpy as np

# === Paths ===
DAILY_DIR = "../../../Data/CDS_Climate/Raw/csv_daily/"
expected_vars = ["t2m", "d2m", "u10", "v10", "tp"]

# === Bounding box (from 'area': [37.0, 61.0, 23.0, 78.0]) ===
LAT_MIN, LAT_MAX = 23.0, 37.0
LON_MIN, LON_MAX = 61.0, 78.0

# === Helper ===
def summarize_file(fpath):
    try:
        df = pd.read_csv(fpath, parse_dates=["date"])
    except Exception as e:
        return {"status": "❌ Load failed", "error": str(e)}

    info = {
        "rows": len(df),
        "cols": len(df.columns),
        "% missing": "n/a",
        "start": None,
        "end": None,
        "status": "OK"
    }

    # Empty or unreadable file
    if info["rows"] == 0:
        info["status"] = "⚠️ Empty"
        return info

    # --- Check for missing data ---
    n_missing = df.isna().sum().sum()
    frac_missing = n_missing / (info["rows"] * info["cols"])
    info["% missing"] = round(frac_missing * 100, 3)

    # --- Check for date range ---
    if "date" in df.columns:
        info["start"] = str(df["date"].min())[:10]
        info["end"] = str(df["date"].max())[:10]
    else:
        info["status"] = "⚠️ Missing date column"

    # --- Check for lat/lon columns ---
    lat_col = [c for c in df.columns if c.lower().startswith("lat")]
    lon_col = [c for c in df.columns if c.lower().startswith("lon") or c.lower().startswith("long")]

    if not lat_col or not lon_col:
        info["status"] = "⚠️ Missing lat/lon"
        return info

    lat_col, lon_col = lat_col[0], lon_col[0]

    # --- Check coordinate bounds ---
    lat_out = df[(df[lat_col] < LAT_MIN) | (df[lat_col] > LAT_MAX)]
    lon_out = df[(df[lon_col] < LON_MIN) | (df[lon_col] > LON_MAX)]

    if len(lat_out) > 0 or len(lon_out) > 0:
        info["status"] = "⚠️ Out of bounds"
        info["lat_violations"] = len(lat_out)
        info["lon_violations"] = len(lon_out)

    # --- Overall status ---
    if n_missing > 0:
        info["status"] = "⚠️ Missing values"

    return info


# === Scan all files ===
summary = []
all_files = sorted([f for f in os.listdir(DAILY_DIR) if f.endswith("_daily.csv")])

print(f"Checking {len(all_files)} daily CSVs in {DAILY_DIR}...\n")

for file in all_files:
    var = file.split("_")[0]
    fpath = os.path.join(DAILY_DIR, file)
    info = summarize_file(fpath)
    info["file"] = file
    info["var"] = var
    summary.append(info)

# === Convert to DataFrame ===
report = pd.DataFrame(summary)
report = report[["file", "var", "status", "rows", "cols", "% missing", "start", "end"]].sort_values(["var", "file"])

# === Print summary ===
print("=== SUMMARY REPORT ===")
print(report.to_string(index=False))

# === Variable coverage check ===
print("\n=== VARIABLE COVERAGE CHECK ===")
months = {f.split("_")[2] for f in all_files}
for var in expected_vars:
    present_months = {f.split("_")[2] for f in all_files if f.startswith(var + "_")}
    missing_months = sorted(set(months) - present_months)
    if missing_months:
        print(f"❌ Missing months for {var}: {missing_months}")
    else:
        print(f"✓ {var} has all months present.")

# === Save report ===
out_csv = os.path.join(DAILY_DIR, "_QA_daily_file_report.csv")
report.to_csv(out_csv, index=False)
print(f"\nSaved detailed QA report → {out_csv}")
