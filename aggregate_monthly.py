"""
Created by Morgan

Step 5: Aggregate daily panels (k=3,5,10) into monthly panels with means, sums, and temperature bins.
- Input: ../../../Data/CDS_Climate/Processed/panels/daily_panel_k{3,5,10}.csv
- Output: ../../../Data/CDS_Climate/Processed/panels/monthly_panel_k{3,5,10}.csv
"""

import os
import numpy as np
import pandas as pd

# ---- Paths ----
BASE_DIR = "../../../Data/CDS_Climate/Processed/panels/"
os.makedirs(BASE_DIR, exist_ok=True)

# ---- Helper functions ----
def kelvin_to_fahrenheit(k):
    return (k - 273.15) * 9.0 / 5.0 + 32.0

def compute_bin_counts(df, temp_bin_column, bin_labels, label_prefix):
    """Compute bin counts for a given bin column and prefix labels."""
    counts = (
        df.groupby(["village_id", "year_month", temp_bin_column], observed=True)
          .size()
          .unstack(fill_value=0)
          .reset_index()
    )

    # Ensure all bins exist and reorder consistently
    for lbl in bin_labels:
        if lbl not in counts.columns:
            counts[lbl] = 0
    counts = counts[["village_id", "year_month"] + bin_labels]

    # Rename columns with prefix
    rename_map = {lbl: f"{label_prefix}_{lbl}" for lbl in bin_labels}
    counts = counts.rename(columns=rename_map)

    return counts

# ---- Loop for each k ----
for k in [3, 5, 10]:
    print(f"\n=== Processing k = {k} ===")
    DAILY_PANEL = os.path.join(BASE_DIR, f"daily_panel_k{k}.csv")
    OUT_FILE = os.path.join(BASE_DIR, f"monthly_panel_k{k}.csv")

    # ---- Load daily panel ----
    print("Loading daily panel ...")
    df = pd.read_csv(DAILY_PANEL, parse_dates=["timestamp"])

    # ---- Temperature conversions ----
    df["temp_mean_F"] = kelvin_to_fahrenheit(df["temp_mean_K"])
    df["temp_min_F"] = kelvin_to_fahrenheit(df["temp_min_K"])
    df["temp_max_F"] = kelvin_to_fahrenheit(df["temp_max_K"])
    df["dewpoint_mean_F"] = kelvin_to_fahrenheit(df["dewpoint_mean_K"])

    # ---- Month key (month start) ----
    df["year_month"] = df["timestamp"].dt.to_period("M").dt.to_timestamp()

    # ---- Define dynamic bins ----
    temp_min_global = np.floor(min(
        df["temp_mean_F"].min(),
        df["temp_min_F"].min(),
        df["temp_max_F"].min()
    ) / 5) * 5

    temp_max_global = np.ceil(max(
        df["temp_mean_F"].max(),
        df["temp_min_F"].max(),
        df["temp_max_F"].max()
    ) / 5) * 5

    bin_edges = np.arange(temp_min_global - 5, temp_max_global + 10, 5)
    bin_labels = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}" for i in range(len(bin_edges) - 1)]

    print(f"  Created {len(bin_labels)} bins from {bin_edges[0]}°F to {bin_edges[-1]}°F")

    # ---- Assign bins for mean, min, and max ----
    df["temp_bin_mean"] = pd.cut(
        df["temp_mean_F"], bins=bin_edges, labels=bin_labels,
        right=False, include_lowest=True
    )
    df["temp_bin_min"] = pd.cut(
        df["temp_min_F"], bins=bin_edges, labels=bin_labels,
        right=False, include_lowest=True
    )
    df["temp_bin_max"] = pd.cut(
        df["temp_max_F"], bins=bin_edges, labels=bin_labels,
        right=False, include_lowest=True
    )

    # ---- Aggregations (means and sums) ----
    mean_vars = [
        "temp_mean_F",
        "temp_min_F",
        "temp_max_F",
        "dewpoint_mean_F",
        "wind_speed_ms",
        "relative_humidity_pct",
        "vapor_pressure_hPa",
        "apparent_temp_C",
        "wet_bulb_C",
    ]
    sum_vars = ["precipitation_mm"]

    agg_dict = {var: "mean" for var in mean_vars}
    agg_dict.update({var: "sum" for var in sum_vars})

    monthly_meansums = (
        df.groupby(["village_id", "year_month"], dropna=False)
          .agg(agg_dict)
          .reset_index()
    )

    # Rename columns for clarity
    monthly_meansums = monthly_meansums.rename(
        columns={
            "temp_mean_F": "temp_mean_F_monthly_mean",
            "temp_min_F": "temp_min_F_monthly_mean",
            "temp_max_F": "temp_max_F_monthly_mean",
            "dewpoint_mean_F": "dewpoint_mean_F_monthly_mean",
            "wind_speed_ms": "wind_speed_ms_monthly_mean",
            "relative_humidity_pct": "relative_humidity_pct_monthly_mean",
            "vapor_pressure_hPa": "vapor_pressure_hPa_monthly_mean",
            "apparent_temp_C": "apparent_temp_C_monthly_mean",
            "wet_bulb_C": "wet_bulb_C_monthly_mean",
            "precipitation_mm": "precipitation_mm_monthly_sum",
        }
    )

    # ---- Compute bin counts ----
    mean_bins = compute_bin_counts(df, "temp_bin_mean", bin_labels, "temp_mean_bin_count")
    min_bins = compute_bin_counts(df, "temp_bin_min", bin_labels, "temp_min_bin_count")
    max_bins = compute_bin_counts(df, "temp_bin_max", bin_labels, "temp_max_bin_count")

    # ---- Merge everything ----
    monthly_panel = (
        monthly_meansums
        .merge(mean_bins, on=["village_id", "year_month"], how="left")
        .merge(min_bins, on=["village_id", "year_month"], how="left")
        .merge(max_bins, on=["village_id", "year_month"], how="left")
    )

    # ---- Internal QA ----
    non_missing_days = (
        df[~df["temp_mean_F"].isna()]
          .groupby(["village_id", "year_month"])
          .size()
          .rename("non_missing_temp_days")
          .reset_index()
    )

    qa = mean_bins.merge(non_missing_days, on=["village_id", "year_month"], how="left")
    qa["_sum_all_bins"] = qa[[f"temp_mean_bin_count_{lbl}" for lbl in bin_labels]].sum(axis=1)

    bad = qa.loc[qa["_sum_all_bins"] != qa["non_missing_temp_days"]]
    if not bad.empty:
        print(f"  ⚠️ {len(bad)} months have mismatched bin totals — check data quality.")
    else:
        print("  ✓ All months have correct bin totals.")

    # ---- Save ----
    monthly_panel = monthly_panel.rename(columns={"year_month": "timestamp"})
    monthly_panel = monthly_panel.sort_values(["village_id", "timestamp"])
    monthly_panel.to_csv(OUT_FILE, index=False)

    print(f"  ✓ Saved monthly panel → {OUT_FILE}")
