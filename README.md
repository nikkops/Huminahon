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
- **Storage:** one S3 bucket with these prefixes: `raw/smap/`, `raw/imerg/`, `raw/ibtracs/`, `reference/`, `processed/`, `athena-results/`, `models/`, `artifacts/layers/`. The dashboard goes in its own small bucket.
- **Ingestion:** one job per storm event (a Lambda function), so failures stay isolated, jobs can run in parallel and a single event can be retried. The function gets its libraries (numpy, h5py, earthaccess) from a Lambda layer.
- **Secrets and permissions:** the Earthdata username and password are kept in Parameter Store (username as String, password as SecureString). Code uses an IAM role (`huminahon-ingest-lambda-role`) with least-privilege permissions, not access keys.
- **Later:** Parquet files queried with Glue and Athena, modelling, a static dashboard served through CloudFront, and infrastructure as code.

## Key decisions

- **Scope:** Luzon only for version 1.
- **"Raw" data** means as delivered by NASA, restricted to the Luzon box. The cut is made right after reading.
- **UTC days** are used for both datasets. Manila's midnight (16:00 UTC) falls in the middle of a 3-hour SMAP window, so it cannot be cut cleanly.
- **SMAP day filter:** keep a granule only if its start time falls on the target date. Searching by date range also returns the previous day's last window.
- **Land mask:** SMAP water cells hold the fill value -9999, so land cells are the ones that are not -9999. The mask is built once, because the grid is the same in every file.
- **Output granularity:** one file per day in `raw/`, to avoid thousands of tiny files that slow Athena down. A consolidated layer in `processed/` is planned.
- **Output file format:** not final. The ingestion Lambda has no pandas or pyarrow (they pushed the package past Lambda's 250 MB limit), so the leading plan is a plain NumPy file (`.npz`) per day in `raw/`, with a separate later step converting to Parquet (one row per cell per timestamp) in `processed/`, because Athena and Glue read Parquet natively.

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

### Checkpoint 3

Finished the pilot reads for both datasets on one day of Typhoon Vamco, in AWS CloudShell, and worked out the Luzon windows.

**Results**

- **SMAP window:** the Luzon box is a clean rectangle on the grid (rows 553 to 619, columns 3208 to 3241), so 67 x 34 = 2,278 cells. Of these, 1,354 hold valid data, which matches the earlier land-cell count. The remaining cells are water.
- **SMAP read time:** about 1 second for the four variables (`sm_surface`, `sm_rootzone`, `sm_surface_wetness`, `sm_rootzone_wetness`), plus about 0.7 seconds to open the file. Mean root-zone wetness for the Nov 11 22:30 UTC window was 0.944, consistent with the earlier peak.
- **IMERG window:** the `precipitation` variable has axis order (time, lon, lat). The Luzon window is 32 x 49 = 1,568 cells, read in about 0.9 seconds, plus 0.6 seconds to open. The Nov 12 window mean (37.5 mm/day) and maximum (246.6 mm/day) match the earlier box check.
- **Estimate:** about 5.5 minutes per event window (168 SMAP files and 21 IMERG files), read one after another. That fits inside Lambda's 15-minute limit. This comes from single measurements, probably over HTTPS, so it will be measured again inside the Lambda.

**Findings**

- `sm_rootzone_pctl` is a percentile (0 to 100) of root-zone soil moisture. NASA's percentile conversion uses a static climatology data set. It is not yet known whether that reference varies through the year, so it may or may not replace a self-built seasonal baseline.
- SMAP L4 relies on a land model alone during instrument outages (19 June to 23 July 2019 and 6 August to 20 September 2022). Storm events in those windows need flagging.

**Next:** decide the output file format, store the Earthdata login in Parameter Store, then create the Lambda role and function.

### Checkpoint 4

Stored the Earthdata login in Parameter Store, created the Lambda role and function, and got the dependency layer working.

**What was built**

- **Parameter Store:** two parameters under a `/huminahon/earthdata/` path, the username as a String and the password as a SecureString (free on the Standard tier, encrypted with the default AWS-managed key). Parameter Store was chosen over Secrets Manager because it costs nothing for this use.
- **Lambda role:** `huminahon-ingest-lambda-role`, trusted by `lambda.amazonaws.com`, plus the basic execution policy for logs. Its inline policy allows only: read and write objects under `raw/*`, list the bucket limited to the `raw/` prefix, and read parameters under the Earthdata path. Nothing else.
- **Lambda function:** `huminahon-ingest`, with a first test that read both parameters (decrypting the password) and returned only their lengths, so the login itself is never printed or logged.
- **Layer:** `huminahon-deps` (version 1), built in CloudShell with `pip install earthaccess h5py numpy --target ./python`, zipped (about 49 MB, 139 MB unzipped), uploaded to `artifacts/layers/` in the bucket, then created from that S3 location in Copy mode. Compatible with Python 3.13 and x86_64.
- **Import test:** numpy 2.5.5, h5py 3.16.0 and earthaccess 1.0.0 all import from the layer. The run took about 2 seconds and used 126 MB of the 1,024 MB configured.

**Lessons**

- The first build (with pandas and pyarrow) was 389 MB unzipped, over Lambda's 250 MB limit for function plus layers. Dropping pandas and pyarrow from the ingestion step brought it to 139 MB. Parquet conversion moves to a separate step later.
- A layer must match the Lambda's Python version and CPU architecture. CloudShell had Python 3.13 while the function defaulted to a newer runtime, so the function's runtime was changed to 3.13 instead of rebuilding the layer.
- A layer over 50 MB cannot go through the console's direct upload, so it goes via S3 first.
- Lambda roles give temporary credentials, so no access keys are stored anywhere.

## Open questions for the next session

**Ingestion function design**
- What does the function receive as input, and what in it says which event and which days to fetch?
- What is the S3 key layout for one day's output, and which S3 call lets the function check "already done" so it can skip (making reruns safe)?
- What is written when a day fails or has no data, so a later run can tell the difference between "not done" and "nothing there"?

**Reading the data**
- Does direct S3 access work from inside Lambda? (The in-region check said `False` in CloudShell and was never tested. Try `earthaccess.get_s3_filesystem`.)
- How long does one event take inside Lambda, compared with the 5.5 minute estimate? Does the timeout (15 minutes at most) and memory need to change from the current settings?

**Data and modelling**
- Is the `sm_rootzone_pctl` climatology seasonal, or can it not replace a self-built baseline?
- How are SMAP (9 km) and IMERG (0.1 degree) put on a common grid, and how is the land mask applied to IMERG?
- How are events inside the SMAP outage windows (2019 and 2022) flagged?

**AWS housekeeping**
- Was the `iam:PassRole` policy for the builder group actually saved? (The function was created fine, so it may already work.)
- How are all 78 events run, and how are failures tracked (SQS with a dead-letter queue, or Step Functions)?
- Should the layer build commands go into the repo so the layer can be rebuilt?

## Known limitations

- SMAP L4 is partly model output, not purely observed.
- SMAP L4 is model-only during instrument outages (June to July 2019, August to September 2022), and these overlap typhoon season.
- SMAP (9 km grid) and IMERG (0.1 degree grid) use different grids, so combining them needs a decision (regridding or aggregation).
- IMERG is less accurate over complex terrain and coasts.
- IMERG includes ocean cells, so a land mask is needed so both datasets cover the same places.
- IBTrACS only tracks cyclones, so non-storm rain events (monsoon, shear lines) are not included.
- Only one storm has been checked so far, and box averages hide cell-level variation.
- The AWS Free plan ends in May 2027, so the project is meant to be rebuilt from code and notes.

## Roadmap

- [x] AWS account, MFA, budget, IAM user, S3 bucket
- [x] Pilot search for one day (IMERG and SMAP)
- [x] Find Luzon grid cells and time one granule read (SMAP and IMERG)
- [ ] Decide the output file format and write the first cut-out to S3
- [ ] Test direct S3 access (the in-region flag reported `False` in CloudShell)
- [x] Store the Earthdata login in Parameter Store
- [x] Create the Lambda role and function, with a working dependency layer
- [ ] Download all events (about 78 storms)
- [ ] Convert to Parquet, query with Athena
- [ ] Seasonal baselines and recovery-time target
- [ ] Modelling and SHAP
- [ ] Static dashboard
- [ ] Infrastructure as code
