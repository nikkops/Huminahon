# Huminahon

*Predicting How Long Philippine Soil Takes to Settle After Typhoons*

A data pipeline and machine learning project built on NASA Earth observation data. It measures how many days soil moisture takes to return to its seasonal normal after typhoons and heavy-rain floods, then predicts which areas stay waterlogged longest.

**Status:** in progress. Themed on the NASA Space Apps 2026 challenge "Be an Earth System Trend Detective".

## Research question

After a typhoon or flood event, how many days until root-zone soil moisture returns to its normal seasonal range, and which Luzon regions stay waterlogged longest (relevant for crop areas)?

## Study area

- Luzon: latitude 13.69 to 18.62, longitude 119.48 to 122.72.
- Data starts in April 2015, when SMAP L4 begins.
- Region is stored as a partition column, so the Visayas and Mindanao can be added in version 2 without a redesign.

## Data sources

| Data | Product | Used for | Notes |
|---|---|---|---|
| Soil moisture | SMAP L4 `SPL4SMGP` V008 | Root-zone wetness (the recovery target) | 3-hourly, 9 km grid, partly model output |
| Rainfall | GPM IMERG Final Run daily `GPM_3IMERGDF` V07 | Rainfall total and peak | 0.1 degree, mm/day, days are UTC |
| Storm events | IBTrACS v04r01, Western Pacific | Storm list, wind strength | Wind in knots, tracks cyclones only |
| Land cover, soil, elevation | MODIS MCD12C1, SMAP L4 constants | Version 2 | Not used in version 1 |

## Method (planned)

- **Target:** days until root-zone wetness returns to its seasonal normal range.
- **Models:** survival analysis (a recovery is censored if the next storm interrupts it) and gradient boosting.
- **Features:** rainfall total and peak, storm wind strength, pre-event wetness, season, location, days since the previous storm.
- **Evaluation:** train/test split by event, baselines, SHAP and feature importance.

## AWS design

- **Region:** `us-west-2`, where NASA Earthdata Cloud data is hosted.
- **Storage:** one S3 bucket with these prefixes: `raw/smap/`, `raw/imerg/`, `raw/ibtracs/`, `reference/`, `processed/`, `athena-results/`, `models/`. The dashboard goes in its own small bucket.
- **Ingestion:** one job per storm event (a Lambda function), so failures stay isolated, jobs can run in parallel and a single event can be retried.
- **Secrets and permissions:** the Earthdata login is kept in Parameter Store (SecureString). Code uses an IAM role with least-privilege permissions, not access keys.
- **Later:** Parquet files queried with Glue and Athena, modelling, a static dashboard served through CloudFront, and infrastructure as code.

## Key decisions

- **Scope:** Luzon only for version 1.
- **"Raw" data** means as delivered by NASA, restricted to the Luzon box. The cut is made right after reading.
- **UTC days** are used for both datasets. Manila's midnight (16:00 UTC) falls in the middle of a 3-hour SMAP window, so it cannot be cut cleanly.
- **SMAP day filter:** keep a granule only if its start time falls on the target date. Searching by date range also returns the previous day's last window.

## Updates

### Checkpoint 1

Started setting up AWS. Created an IAM group with the PowerUserAccess policy for the users who act as builders. This policy does not allow viewing billing or managing IAM. Also created a Budget under Billing with a monthly cap of $20. Lastly, created an S3 bucket in the `us-west-2` Region. This Region was selected so the NASA data can be read in-region without having to download it over the internet, even though other Regions are geographically closer to the Philippines. The bucket uses the default SSE-S3 encryption, and versioning is turned off for now.

### Checkpoint 2

Set up the bucket prefixes and ran a pilot search for one day of Typhoon Vamco (2020-11-12) from AWS CloudShell, using the `earthaccess` library with the Earthdata login read from environment variables.

**Findings**

- IMERG returns 1 file per day, about 28.9 MB, covering the whole globe.
- SMAP L4 returns 8 files per day (one per 3 hours), about 140.8 MB each. Storing every file whole for all events would be roughly 1.8 TB, so only the needed variables and the Luzon cells will be read.
- The SMAP search returned 9 files instead of 8. The extra file belonged to the previous day, because its window ends exactly at 00:00. The fix is to filter by start date.
- Each SMAP variable is stored as one block covering the whole grid (1624 x 3856 cells, float32), so slicing a small area saves less than expected. The saving comes from reading only the 4 variables needed out of about 50.
- Opening a granule takes under a second, because the file is read lazily.
- Both a direct `s3://` link and an `https://` link exist for each file. The library's in-region check reported `False` even in `us-west-2`. The cause is not confirmed, and direct S3 access has not been tested yet.

**Lessons**

- In `read -s -p "prompt" NAME`, the variable name at the end is what stores the input. Without it, the input is dropped.
- CloudShell runs Python in a virtual environment, so `pip install --user` does not apply.
- S3 folders are only key prefixes, which is why the CLI shows them as `PRE`.

**Next:** find the Luzon grid cells once from `cell_lat` and `cell_lon`, check whether `sm_rootzone_pctl` is useful for the seasonal baseline, time the read of one granule, then time a full event window.

## Known limitations

- SMAP L4 is partly model output, not purely observed.
- IMERG is less accurate over complex terrain and coasts.
- IMERG includes ocean cells, so a land mask is needed so both datasets cover the same places.
- IBTrACS only tracks cyclones, so non-storm rain events (monsoon, shear lines) are not included.
- Only one storm has been checked so far, and box averages hide cell-level variation.
- The AWS Free plan ends in May 2027, so the project is meant to be rebuilt from code and notes.

## Roadmap

- [x] AWS account, MFA, budget, IAM user, S3 bucket
- [x] Pilot search for one day (IMERG and SMAP)
- [ ] Find Luzon grid cells once and time one granule read
- [ ] Store the Earthdata login in Parameter Store
- [ ] Create the Lambda role and function
- [ ] Download all events (about 78 storms)
- [ ] Convert to Parquet, query with Athena
- [ ] Seasonal baselines and recovery-time target
- [ ] Modelling and SHAP
- [ ] Static dashboard
- [ ] Infrastructure as code
