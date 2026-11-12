import sys
import h5py
import numpy as np

# Luzon box from your Earthdata Search rectangle
LAT_MIN, LAT_MAX = 13.69, 18.62
LON_MIN, LON_MAX = 119.48, 122.72

TARGETS = ["sm_surface", "sm_rootzone", "sm_profile",
           "sm_surface_wetness", "sm_rootzone_wetness"]


def main(path):
    with h5py.File(path, "r") as f:
        datasets = {}

        def collect(name, obj):
            if isinstance(obj, h5py.Dataset):
                datasets[name] = obj

        f.visititems(collect)

        print(f"File: {path}")
        print(f"{len(datasets)} datasets. First 40:")
        for name, ds in list(datasets.items())[:40]:
            print(f"  {name}  shape={ds.shape}  dtype={ds.dtype}")

        def find(base):
            for name, ds in datasets.items():
                if name.split("/")[-1].lower() == base:
                    return ds
            return None

        lat_ds, lon_ds = find("cell_lat"), find("cell_lon")
        if lat_ds is None or lon_ds is None:
            print("\nCould not find cell_lat / cell_lon. Send me the list above.")
            return

        lat, lon = lat_ds[()], lon_ds[()]
        box = (lat >= LAT_MIN) & (lat <= LAT_MAX) & (lon >= LON_MIN) & (lon <= LON_MAX)
        print(f"\nPixels inside the Luzon box: {int(box.sum())}")

        for name, ds in datasets.items():
            base = name.split("/")[-1]
            if base not in TARGETS:
                continue
            if ds.shape != lat.shape:
                print(f"\n{base}: shape {ds.shape} does not match lat/lon {lat.shape}, skipping")
                continue
            data = ds[()].astype("float64")
            data[data < -9000] = np.nan  # fill value is typically -9999
            vals = data[box]
            vals = vals[~np.isnan(vals)]
            print(f"\n{name}")
            print(f"  valid pixels in box: {vals.size}")
            if vals.size:
                print(f"  min {vals.min():.3f}  mean {vals.mean():.3f}  max {vals.max():.3f}")


if __name__ == "__main__":
    main(sys.argv[1])