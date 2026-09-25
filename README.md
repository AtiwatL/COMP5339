# NSW EV Charger Data Integration and Augmentation

COMP5339 Data Engineering - Assignment 1

This project implements a reproducible data engineering pipeline for public electric vehicle charging infrastructure in New South Wales. It retrieves the December 2025 Transport for NSW charger dataset and the 2026 ABS SA4 boundaries, cleans and spatially integrates the records, augments DC chargers with Open Charge Map and PlugShare attributes, and stores the result in a normalized DuckDB Spatial database.

The final database contains **1,926 charger records**, including **411 DC records**, across all **28 spatial NSW SA4 regions**.

## Project structure

```text
COMP5339/
|-- 01_data_acquisition.ipynb     Retrieve and profile TfNSW and ABS data
|-- 02_data_cleaning.ipynb        Clean, reconcile and spatially join records
|-- 03_data_augmentation.ipynb    Match OCM/PlugShare and add attributes
|-- 04_data_storage.ipynb         Build and validate the DuckDB database
|-- requirements.txt              Python package requirements
|-- .env                          Local Task 3 API credentials
|-- sql/
|   `-- schema.sql                Standalone DDL for the database schema
|-- tools/
|   `-- Plug_share.py             Incremental PlugShare retrieval helper
`-- data/
    |-- raw/                      Original downloads and API snapshots
    |-- interim/                  Cleaning and matching audit outputs
    `-- processed/                Final CSVs and DuckDB database
```

The four numbered notebooks are the authoritative pipeline and must be run in order.

## Requirements

- Python 3.11 or 3.12; Python 3.11 is recommended.
- Internet access when source data or the DuckDB Spatial extension must be downloaded.
- Open Charge Map and Apify API credentials when Task 3 must retrieve uncached data.

All required Python packages are listed in `requirements.txt`. DuckDB Spatial is a DuckDB extension rather than a separate pip package. The notebooks install it with `INSTALL spatial` when necessary and load it with `LOAD spatial`.

## Setup

Open a terminal in the project directory and create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start JupyterLab from the same project directory:

```bash
python -m jupyter lab
```


## Task 3 API credentials

Task 3 reads the Open Charge Map and Apify credentials from the `.env` file in
the project root. 

```dotenv
OCM_API_KEY=open_charge_map_key
APIFY_TOKEN=apify_token
```

`OCM_API_KEY` retrieves Open Charge Map data. `APIFY_TOKEN` is used by `tools/Plug_share.py` to run the PlugShare scraper through Apify. Included OCM and PlugShare caches are reused when available, so rerunning Task 3 normally does not issue new requests.

## Execution instructions

Restart the kernel and run every cell from top to bottom in this order.

### 1. Data acquisition

Run `01_data_acquisition.ipynb`.

The notebook:

- discovers the December 2025 TfNSW CSV through the data.gov.au CKAN API;
- discovers and downloads the latest ABS ASGS Edition 4 SA4 shapefile;
- validates the downloaded content;
- records source URLs, retrieval metadata and SHA-256 checksums; and
- profiles the raw data before cleaning.

Main outputs:

- `data/raw/tfnsw/ev_20251216.csv`
- `data/raw/abs/SA4_2026_AUST_SHP_GDA2020.zip`
- `data/raw/abs/sa4_shapefile/`
- `data/raw/manifest.json`

### 2. Data cleaning and spatial integration

Run `02_data_cleaning.ipynb` after Task 1.

The notebook:

- standardizes fields, operators, addresses, postcodes and data types;
- parses simple and compound power ratings;
- reconciles conflicting duplicate groups and flags probable duplicates;
- transforms ABS boundaries from GDA2020 to WGS84; and
- assigns every charger to an SA4 region with DuckDB Spatial.

Main outputs:

- `data/interim/ev_chargers_clean.csv`
- `data/interim/charger_power_ratings.csv`
- `data/interim/cleaning_log.json`
- `data/interim/probable_duplicates.csv`
- `data/interim/sa4_regions_nsw.csv`

### 3. Data augmentation

Run `03_data_augmentation.ipynb` after Task 2.

The notebook:

- loads or retrieves Open Charge Map locations;
- matches DC charger candidates using distance, operator, street, postcode and DC evidence;
- uses PlugShare as a fallback for records without an accepted OCM match;
- removes confirmed shared-external-location duplicates; and
- adds `connector_type`, `operator_website` and `cost_applies`.

Main inputs and outputs:

- `data/raw/openchargemap/locations.json`
- `data/raw/openchargemap/locations.metadata.json`
- `data/raw/plugshare/coordinate_searches.json`
- `data/interim/ocm_matching_review.csv`
- `data/interim/plugshare_matching_review.csv`
- `data/interim/ev_chargers_augmented_full.csv`
- `data/processed/ev_chargers_augmented.csv`
- `data/processed/charger_power_ratings.csv`

### 4. Data transformation and storage

Run `04_data_storage.ipynb` after Task 3.

The notebook:

- applies the standalone DDL in `sql/schema.sql`;
- loads the normalized relational tables;
- reads and transforms the ABS boundaries with DuckDB Spatial;
- creates R-tree indexes on regional and site geometries; and
- validates row counts, keys, foreign keys, constraints and geometries.

Main outputs:

- `data/processed/ev_chargers.duckdb`
- `sql/schema.sql`

If an upstream output is missing, a later notebook stops and identifies the notebook that must be run first.

## Included data and outputs

### Raw data

| Path | Description |
|---|---|
| `data/raw/tfnsw/ev_20251216.csv` | Original December 2025 TfNSW CSV containing 1,958 records. |
| `data/raw/abs/SA4_2026_AUST_SHP_GDA2020.zip` | Original ABS ASGS Edition 4 SA4 archive. |
| `data/raw/abs/sa4_shapefile/` | Extracted shapefile and its metadata and sidecar files. |
| `data/raw/openchargemap/locations.json` | Cached OCM response used for augmentation. |
| `data/raw/openchargemap/locations.metadata.json` | OCM request parameters, retrieval time, count and checksum. |
| `data/raw/plugshare/coordinate_searches.json` | Incremental PlugShare search cache used by Task 3. |
| `data/raw/manifest.json` | Primary-source provenance, file sizes and checksums. |

### Interim audit data

| Path | Description |
|---|---|
| `data/interim/ev_chargers_clean.csv` | Cleaned and spatially integrated data containing 1,946 records. |
| `data/interim/charger_power_ratings.csv` | Parsed power components before Task 3 duplicate removal. |
| `data/interim/cleaning_log.json` | Count and description of every cleaning action. |
| `data/interim/probable_duplicates.csv` | Cross-feed duplicate candidates retained as flags. |
| `data/interim/sa4_regions_nsw.csv` | NSW SA4 reference output. |
| `data/interim/ocm_matching_review.csv` | OCM evidence, decisions and reasons. |
| `data/interim/plugshare_matching_review.csv` | PlugShare evidence, decisions and reasons. |
| `data/interim/ev_chargers_augmented_full.csv` | Full augmentation audit data with source-specific fields. |

### Processed deliverables

| Path | Description |
|---|---|
| `data/processed/ev_chargers_augmented.csv` | Compact final dataset containing 1,926 records. |
| `data/processed/charger_power_ratings.csv` | Power components belonging to retained final chargers. |
| `data/processed/ev_chargers.duckdb` | Final populated DuckDB Spatial database. |
| `sql/schema.sql` | DDL that recreates the schema, constraints and R-tree indexes. |

## Database schema

The final database uses seven normalized tables:

- `sa4_region`
- `charging_site`
- `operator`
- `charger`
- `charger_power_rating`
- `connector_type`
- `charger_connector`

Sites are separated from chargers so co-located installations can share one address and geometry while retaining charger-level operator, type, status and power characteristics. Compound power ratings are stored as separate components, and connector support is represented as a many-to-many relationship.

To inspect the database from Python:

```python
import duckdb

con = duckdb.connect("data/processed/ev_chargers.duckdb", read_only=True)
print(con.sql("SHOW TABLES").df())
print(con.sql("SELECT charger_type, COUNT(*) FROM charger GROUP BY 1").df())
con.close()
```

## Assumptions and decisions

**Source selection and geography.** The required TfNSW input is interpreted as
the latest resource released in December 2025, `ev_20251216.csv`. TfNSW
coordinates are treated as WGS84 (`EPSG:4326`), while the ABS boundaries use
GDA2020 (`EPSG:7844`) and are transformed before the spatial join. A coastal
point that falls just outside a polygon may be assigned to the nearest SA4 only
within the stated tolerance; the assisted assignment remains identified in the
output.

**Sites and charger records.** Records with the same cleaned coordinate pair
share one `site_id`, but their charger records remain separate so differences
in operator, AC/DC type, status, plugs and power are preserved. Multiple source
records are treated as probable duplicates only when they independently select
the same accepted external location. The most complete record is retained, and
distance to the external location resolves a completeness tie.

**External matching.** OCM is the primary augmentation source, and PlugShare is
used only for DC records without an accepted OCM match. Candidates farther than
250 m are rejected. Candidates from 50 to 250 m require the same canonical
operator and street similarity of at least 0.90, followed by postcode and DC
validation. If several candidates pass, the nearest is selected; if none pass,
the nearest failed candidate is retained for audit without contributing
attributes.

**Attribute interpretation.** Only external connections explicitly identified
as DC contribute connector types. A null `cost_applies` value means that no
accepted source provided reliable cost evidence; it does not mean charging is
free. OCM and PlugShare values are cached snapshots and may differ from the
current live infrastructure.

## Reproducibility and validation

- Primary downloads are automated and recorded in `manifest.json` with checksums.
- Downloads are written to temporary files before replacing valid cached files.
- Cached API responses avoid repeated paid or rate-limited requests.
- Original values and matching evidence remain in interim audit files.
- The notebooks assert record counts, identifier uniqueness and preservation of retained source values.
- The storage notebook validates relational integrity, geometry validity and CRS metadata.

## Known limitations

- Community-maintained external sources may contain incomplete or outdated information.
- Matching favours precision, so review candidates contribute no augmented attributes.
- `cost_applies` records whether payment applies, not the complete tariff structure.
- SA4 counts do not measure road-network accessibility or real-time availability.
- The project covers NSW and augments DC records only.
