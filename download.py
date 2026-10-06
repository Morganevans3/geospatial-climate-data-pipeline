'''
Written by Morgan

Step 1:
Downloads all data into a nc file for 1980-2018

Having two Python instances running at the same time; one for downloading, one for processing;
In the processor, check every 30 seconds on whether there is new incoming downloaded data; sleep otherwise
Once processed, delete the nc file to save space

Note for using for other countries
within the retrieve command change the area to wherever you need the bounds to be
it is [North, West, South, East] and I also commented that there
if you are taking it from the minimum and maximums of the csv villages add or subtract about 1 degree for KNN to work best
also do it in increments of .25 so like the bound would be 3.8 use 3.75 and if 1.05 use 1
'''

import cdsapi
import xarray as xr
import pandas as pd
import os

# Folders
raw_folder = '../../../Data/CDS_Climate/Raw/nc_files/'
os.makedirs(raw_folder, exist_ok=True)

# Initialize CDS API
c = cdsapi.Client()

# Variables to download from ERA5
variables = [
    '2m_temperature',
    '2m_dewpoint_temperature',
    '10m_u_component_of_wind',
    '10m_v_component_of_wind',
    'total_precipitation',
]
# Map CDS variable name -> short name in NetCDF
var_map = {
    '2m_temperature': 't2m',
    '2m_dewpoint_temperature': 'd2m',
    '10m_u_component_of_wind': 'u10',
    '10m_v_component_of_wind': 'v10',
    'total_precipitation': 'tp',
}

years = range(1980, 2018)
months = [f"{m:02d}" for m in range(1, 13)]
days = [f"{d:02d}" for d in range(1, 32)]

for year in years:
    for month in months:
        for var in variables:
            output_file = os.path.join(raw_folder, f'{var}_{year}_{month}.nc')

            short_var = var_map[var]  # look up actual variable name in file
            csv_file = os.path.join('../../../Data/CDS_Climate/Raw/csv_files/', f'{short_var}_{year}_{month}_hourly.csv')
            daily_csv_file = os.path.join('../../../Data/CDS_Climate/Raw/csv_daily/', f'{short_var}_{year}_{month}_daily.csv')
            if os.path.exists(csv_file) or os.path.exists(daily_csv_file):
                print(f"Skipping {output_file} (already exists)")
                continue

            print(f"Downloading {var} for {year}-{month}...")
            c.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': [var],
                    'year': str(year),
                    'month': month,
                    'day': days,
                    'time': [f"{h:02d}:00" for h in range(24)],
                    'area': [37.0, 61.0, 23.0, 78.0],  # [North, West, South, East]
                    'format': 'netcdf'
                },
                output_file
            )
            ds = xr.open_dataset(output_file)

            # Convert to dataframe
            df = ds[short_var].to_dataframe().reset_index()

            # Ensure correct date column
            if 'time' in df.columns:
                df.rename(columns={'time': 'date'}, inplace=True)
            elif 'valid_time' in df.columns:
                df.rename(columns={'valid_time': 'date'}, inplace=True)

            # Convert to just date
            df['date'] = pd.to_datetime(df['date']).dt.date

            # Save as CSV
            df.to_csv(csv_file, index=False)
            print(f"Saved CSV: {csv_file}")



