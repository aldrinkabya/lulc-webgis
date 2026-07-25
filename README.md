# Interactive WebGIS Platform for Multi-Temporal LULC Monitoring in Bangladesh

An open-source, browser-based WebGIS platform for visualizing and analyzing multi-temporal **Land Use / Land Cover (LULC)** change across Bangladesh.

## Features

- **Multi-temporal LULC overlay** — toggle classified maps for 2019 and 2023 with per-class filtering (Forest, Built-up, Water, Farmland, Meadow).
- **Side-by-side comparison** — swipe slider to compare two years simultaneously.
- **Change detection layers** — visualize class-level LULC transitions and brickfield expansion/contraction between 2019 and 2023.
- **Zonal statistics** — click a district/upazila or draw a custom polygon/rectangle to compute class-area breakdowns in real time.
- **Multiple basemaps** — street map (OpenStreetMap) and satellite imagery (Bing Maps, Esri Wayback).
- **Institutions layer** — optional overlay of Bangladeshi educational institutions from a bundled CSV.
- **Measurement tools** — on-map distance, perimeter, and area rulers.

## Repository Structure

```
├── api.py                        # FastAPI backend — tile serving & zonal statistics
├── brickfield_algo.py            # Brickfield change-detection rendering logic
├── preprocess.py                 # CLI: RGB LULC raster → single-band COG
├── preprocess_brickfield.py      # CLI: brickfield mask → single-band COG
├── process_bing_satellite_cogs.py# CLI: satellite imagery → clipped COG
├── bgd_admbnda_adm0_bbs_20201113.json  # Bangladesh national boundary (UN OCHA)
├── requirements.txt              # Python backend dependencies
├── .env.example                  # Environment variable template
├── CITATION.cff                  # Citation metadata
├── LICENSE                       # MIT License
└── frontend/                     # Next.js web application
    ├── src/
    │   ├── app/                  # Next.js App Router pages
    │   ├── components/           # React UI components (Map, Charts, Sidebar, …)
    │   ├── config.js             # API URL + dataset key configuration
    │   ├── css/                  # Component stylesheets
    │   └── hooks/                # Custom React hooks
    └── public/                   # Static assets (icons, boundary GeoJSON, CSV)
```

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| **Backend** | Python ≥ 3.10, pip |
| **Frontend** | Node.js ≥ 18, npm |
| **Data** | Cloud-Optimized GeoTIFFs placed in `data/cogs/` (see [Data Preparation](#data-preparation)) |

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/aldrin-kabya/webgis-research-release.git
cd webgis-research-release
cp .env.example .env
```

### 2. Backend

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

## Data Preparation

The backend serves tiles from COG files located in the directory specified by `LULC_DATA_DIR` (default: `data/cogs/`). Expected filenames:

| File | Description |
|------|-------------|
| `2019_cog.tif` | Single-band LULC classification for 2019 |
| `2023_cog.tif` | Single-band LULC classification for 2023 |
| `brickfield_2019_cog.tif` | Binary brickfield mask for 2019 |
| `brickfield_2023_cog.tif` | Binary brickfield mask for 2023 |
| `bing_satellite_2019_cog.tif` | RGB satellite imagery COG for 2019 |
| `bing_satellite_2023_cog.tif` | RGB satellite imagery COG for 2023 |

Use the preprocessing scripts to generate these from raw rasters:

```bash
# LULC classification rasters (RGB → single-band COG)
python preprocess.py --input-2019 raw/lulc_2019.tif --input-2023 raw/lulc_2023.tif

# Brickfield masks
python preprocess_brickfield.py --input-2019 raw/brick_2019.tif --input-2023 raw/brick_2023.tif

# Satellite imagery (requires GDAL CLI tools)
python process_bing_satellite_cogs.py --year 2019 --input raw/bing_2019.tif
python process_bing_satellite_cogs.py --year 2023 --input raw/bing_2023.tif
```

## Environment Variables

See [`.env.example`](.env.example) for all configurable variables. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LULC_DATA_DIR` | `data/cogs` | Path to COG data directory |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL used by the frontend |

## Bundled Data Files

| File | Source / License |
|------|-----------------|
| `bgd_admbnda_adm0_bbs_20201113.json` | Bangladesh national boundary — [UN OCHA / BBS](https://data.humdata.org/), CC-BY |
| `frontend/public/bgd_admbnda_adm*_simplified.json` | Administrative boundaries (simplified) — UN OCHA / BBS, CC-BY |
| `frontend/public/institution_list_U_bd_only.csv` | Bangladeshi educational institutions — UGC Bangladesh, public data |

## Citation

If you use this software in your research, please cite the accompanying paper:

> *An Interactive WebGIS Platform for Multi-Temporal LULC Monitoring in Bangladesh.* 2026.

See [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata.

## License

This project is licensed under the [MIT License](LICENSE).
