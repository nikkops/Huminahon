import sys

import pandas as pd

# Usage: python check_events.py .\events\ibtracs.WP.list.v04r01.csv
# Prints the track of Typhoon Vamco (Ulysses), 2020, one row every 12 hours.

path = sys.argv[1]

# skiprows=[1] skips the units row that sits under the header
df = pd.read_csv(
    path,
    skiprows=[1],
    low_memory=False,
    usecols=["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "USA_WIND"],
)
df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"])

v = df[(df["NAME"] == "VAMCO") & (df["SEASON"] == 2020)]
if v.empty:
    print("VAMCO 2020 not found. Check you used the WP file.")
else:
    print(f"{len(v)} rows for VAMCO 2020 (3-hourly)")
    print(v.iloc[::4].to_string(index=False))  # every 12 hours