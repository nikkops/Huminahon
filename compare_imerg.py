import glob
import os
import re
import sys

import h5py
import numpy as np

LAT_MIN, LAT_MAX = 13.69, 18.62
LON_MIN, LON_MAX = 119.48, 122.72

def summarize(path):
    with h5py.File(path, "r") as f:
        datasets = {}

        def collect(name, obj):
            if isinstance(obj, h5py.Dataset):
                datasets[name] = obj

        f.visititems(collect)

        def find(base):
            for name, ds in datasets.items():
                if name.split("/")[-1].lower() == base:
                    return ds
            raise KeyError(f"{base} not found in {path}")

        lat = find("lat")[()].astype("float64")
        lon = find("lon")[()].astype("float64")
        data = np.squeeze(find("precipitation")[()].astype("float64"))

        # make the array (lat, lon) no matter how the file stores it
        if data.shape == (len(lon), len(lat)):
            data = data.T
        elif data.shape != (len(lat), len(lon)):
            raise ValueError(f"unexpected shape {data.shape} in {path}")

        data[data < -9000] = np.nan  # fill value
        lat_ok = (lat >= LAT_MIN) & (lat <= LAT_MAX)
        lon_ok = (lon >= LON_MIN) & (lon <= LON_MAX)
        box = data[np.ix_(lat_ok, lon_ok)]
        return float(np.nanmean(box)), float(np.nanmax(box)), int(np.isfinite(box).sum())

def main(folder):
    files = sorted(glob.glob(os.path.join(folder, "*.nc4")) + glob.glob(os.path.join(folder, "*.nc")))
    rows = []
    for path in files:
        m = re.search(r"3IMERG\.(\d{8})", os.path.basename(path))
        day = m.group(1) if m else os.path.basename(path)
        rows.append((day, summarize(path)))
    rows.sort(key=lambda r: r[0])

    print(f"{'date (UTC)':<12}{'mean mm/day':>13}{'max mm/day':>13}{'pixels':>9}")
    for day, (mean, mx, n) in rows:
        print(f"{day:<12}{mean:>13.1f}{mx:>13.1f}{n:>9}")

if __name__ == "__main__":
    main(sys.argv[1])