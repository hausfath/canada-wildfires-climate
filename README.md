# Canadian Wildfires: Climate, Area Burned & the 2026 Smoke Event

Analysis + shareable chart thread on Canadian wildfire in climate context, built around the
2026 air-quality crisis. Reproducible pipeline: `src/01…→05…`.

## The current event (2026, as of 2026-07-17)
~2.8 Mha burned, 3,586 fires (878 still active). **By day-of-year this is at/above the typical
pace** — the long-term median area burned by mid-July is only ~1.5 Mha (mean ~1.8), so 2026 is
*not* below average; it only looks low against annual totals or the recent record decade. It is,
however, **far below 2023 (record) and 2025 (2nd)** — not a record-area year. Yet air quality has
been catastrophic (Toronto the worst
major-city air on Earth on July 15; Thunder Bay AQI >1,500; alerts across the northern US).
**This is a smoke transport/meteorology story, not a record-burn story:** smoke exposure depends
on *where* fires burn, plume injection height, wind trajectories, and population downwind — not
on total hectares. The charts state this explicitly so a below-average area bar is not misread.

## Headline findings
- **Area burned has surged.** 2023 = **14.8 Mha (NBAC)** / ~17–18 Mha (agency/CIFFC) — the all-time
  record, ~2.5× the previous record. 2025 = ~7–9 Mha, 2nd largest. (Product differences explain the
  "15 vs 18 Mha" range; see below.)
- **Hotter, drier fire seasons burn the most.** In the Rohde-style climate-space plot, 2023 and 2025
  sit deep in the Hot & Dry quadrant; the recent era (2011–25) has shifted measurably warmer.
- **Temperature ↔ area burned is strong and robust.** Nationally r = 0.61 (fire-season mean temp vs
  log area burned, 1972–2025); **survives detrending (0.57), first-differencing (0.46), and
  controlling for precipitation (partial r = 0.58)** — i.e. not a spurious shared trend. ≈ **+80%
  area burned per +1 °C**. Strongest in the western/northern boreal (Yukon, BC, NWT, AB, SK, MB, ON,
  all FDR-significant); weaker/non-significant in the east (QC, NL, NB) — consistent with the
  literature's regional heterogeneity. Precipitation correlates ≈ −0.49.
- **Fire seasons have warmed ≈ +2.2 °C Canada-wide** (May–Sep mean, 1959→2025, per-gridcell LOWESS),
  strongest in the high Arctic (>3 °C) and boreal (~2–2.5 °C). This is the warming behind the shift.
- **Lightning drives ~71%** of area burned (1990–2023) — remote boreal megafires.

(Paleofire / long-term context is discussed in `literature/synthesis.md` but is intentionally kept
out of the shareable chart thread — the proxy-vs-hectares nuance distracts from the main point.)

## Data sources
- **Area burned:** NRCan CNFDB `NFDB_point_stats.xlsx` — national + per-agency, 1959–2025, incl. the
  spatially-accurate **NBAC** composite (1972–2025). 2026 = CIFFC preliminary (partial season).
  NFD by-cause (1990–2023) for the lightning/human split. `data/cnfdb/…_large_fires` polygons for the map.
- **Climate:** ERA5-Land (ECMWF/Copernicus) via **Google Earth Engine** — fire-season (May–Sep) & JJA
  mean 2 m temp, mean daily-max temp, and total precip, area-weighted over **province ∩ forested/woody
  land** (MODIS IGBP classes 1–9), cos-lat weighted. (JJA retained as a robustness season.)

## Methods notes / honest caveats
- **Area products differ:** NBAC (mapped, spatially accurate) < agency/point (reported). We use NBAC
  as primary and label sources explicitly. `total_ha_point` and `total_ha_nbac` both provided.
- **Provincial regressions** use the homogeneous NBAC 1972–2025 window; the pre-1972 point series and
  2026 preliminary point are shown for context only — **no statistics span the source splice.**
- **Robust inference:** effective sample size (Bretherton 1999), moving-block bootstrap CIs,
  Durbin–Watson; raw + detrended + first-differenced reported together; BH-FDR across powered
  jurisdictions; leave-out-2023/2025 refit. Small/non-boreal jurisdictions (PEI etc.) screened out.
- **Temperature is an integrated hot-dry fire-weather indicator** (co-varies with VPD/drought) — the
  correlation is an association, not an isolated causal temperature coefficient. Precipitation is
  shown alongside (Rohde plot) and partialled out.
- ERA5-Land is land-only (coastal-province means land-biased) and its 1950s record runs warm; the
  long series is used for display, correlations start 1972.

## Reproduce
```
python src/01_fetch_fire_data.py       # area-burned CSVs (needs data/NFDB_point_stats.xlsx, nfd csv)
python src/02_fetch_era5land_gee.py    # ERA5-Land seasonal climate via GEE (~30 min; project id in script)
python src/04_analysis.py              # correlations -> outputs/tables/
python src/05_figures.py               # the 5-chart thread -> outputs/figures/
python src/09_berkeley_boreal_1850.py  # fire-season warming since 1850 (needs Berkeley Earth nc, see below)
```
(`03` zonal step is folded into `02`/`04`. Map uses `data/processed/large_fires_2015_2024.gpkg`.)

`09` extends the fire-season warming story back to **1850** using Berkeley Earth's 0.25° gridded
land+ocean monthly anomaly (`Global_TAVG_Gridded_0p25deg.nc`, ~7 GB, download from
[Berkeley Earth](https://berkeleyearth.org/data/); the script expects it at `../Climate Map/`). It
reuses this project's MODIS forest ∩ Canadian-province mask, regridded to the Berkeley grid.
Result: **≈ +2.4 °C** fire-season (May–Sep) warming over Canadian boreal forest since 1850
(≈ +1.85 °C vs an 1850–1900 baseline); 2023 is the hottest fire season in the 176-year record.

Note for cloners: the large raw inputs (`data/cnfdb/`, `data/era5_rasters/`, and the derived
`data/processed/*.gpkg` fire polygons) are not tracked in git for size reasons — `01`/`02`
re-download or rebuild them. All small derived tables needed for `04`/`05` are included, so the
statistics and most figures reproduce out of the box.

## Outputs
`outputs/figures/1_hero_area_burned.png` · `2_fire_season_weather.png` (Rohde replica, centerpiece) ·
`3_provincial_relationship.png` · `4_map_decade_active.png` (2015–24 burned + 2026 active fires) ·
`5_cause_split.png` · `6_fire_season_warming_map.png` (per-gridcell LOWESS warming, ERA5-Land 1959→2025) ·
`7_boreal_fireseason_1850.png` (fire-season temperature time series 1850–2025, Berkeley Earth) ·
`8_boreal_fireseason_warming_map_1850.png` (per-gridcell change 1850→2025).
Shareable page: `outputs/canada_wildfires.html` (self-contained). Tables in `outputs/tables/`
(incl. `berkeley_boreal_fireseason_1850_2025.csv`); literature in `literature/synthesis.md`.
