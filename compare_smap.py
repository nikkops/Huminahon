import glob
import os
import re
import sys

import h5py
import numpy as np

LAT_MIN, LAT_MAX = 13.69, 18.62
LON_MIN, LON_MAX = 119.48, 122.72
VARS = ["sm_surface", "sm_rootzone", "sm_surface_wetness", "sm_rootzone_wetness"]


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

        lat, lon = find("cell_lat")[()], find("cell_lon")[()]
        box = (lat >= LAT_MIN) & (lat <= LAT_MAX) & (lon >= LON_MIN) & (lon <= LON_MAX)
        result = {}
        for v in VARS:
            data = find(v)[()].astype("float64")
            data[data < -9000] = np.nan  # fill value is typically -9999
            result[v] = float(np.nanmean(data[box]))
        return result


def main(folder):
    files = sorted(glob.glob(os.path.join(folder, "*.nc4")))
    rows = []
    for path in files:
        m = re.search(r"gph_(\d{8})T(\d{6})", os.path.basename(path))
        stamp = f"{m.group(1)} {m.group(2)}" if m else os.path.basename(path)
        rows.append((stamp, summarize(path)))
    rows.sort(key=lambda r: r[0])

    print(f"{'date time (UTC)':<18}{'surf':>8}{'root':>8}{'surf_wet':>10}{'root_wet':>10}")
    for stamp, r in rows:
        print(f"{stamp:<18}{r['sm_surface']:>8.3f}{r['sm_rootzone']:>8.3f}"
              f"{r['sm_surface_wetness']:>10.3f}{r['sm_rootzone_wetness']:>10.3f}")


if __name__ == "__main__":
    main(sys.argv[1])