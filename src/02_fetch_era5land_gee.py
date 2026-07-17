#!/usr/bin/env python3
"""
02_fetch_era5land_gee.py — ERA5-Land fire-season climate per Canadian jurisdiction.

Uses the GEE "pull raster, aggregate locally" pattern (avoids reduceRegions'
"User memory limit exceeded" — cf. Carbon Brief/ERA5 30C/src/gee_compute.py):
  1) download a province-ID raster and a burnable-land mask ONCE (Canada bbox, 0.1 deg)
  2) per year, download a 6-band seasonal climate GeoTIFF (no server-side reduction)
  3) compute cos(lat)-area-weighted province means LOCALLY over (province & burnable)

Seasons: fire (May-Sep, primary) + jja (Jun-Aug, robustness).
Bands/year: {fire,jja} x {tmean_c, tmax_c, precip_mm}.
  tmean = mean monthly 2m temp; tmax = season-mean of daily-max 2m temp; precip = season total (mm).
Burnable mask: MODIS MCD12Q1 (2015) IGBP classes 1-9 (forest/shrub/savanna).
Caveats: ERA5-Land land-only; 1950s runs warm (anchor anomalies to 1961-1990).

Output: data/processed/era5land_forested_seasonal.csv
"""
import ee, io, time, pathlib, numpy as np, pandas as pd, requests, rasterio

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
RASTER = OUT.parent / "era5_rasters"; RASTER.mkdir(exist_ok=True)
PROJECT = "api-project-819195003802"
YEARS = range(1959, 2026)
SCALE = 11132
BBOX = [-141.5, 41.0, -52.0, 84.0]         # Canada [W,S,E,N]
SEASONS = {"fire": (5, 9), "jja": (6, 8)}

GAUL_MAP = {  # ADM1_NAME -> (idx, code, jurisdiction)
    "Alberta": (1,"AB","Alberta"),
    "British Columbia / Colombie-Britannique": (2,"BC","British Columbia"),
    "Manitoba": (3,"MB","Manitoba"),
    "New Brunswick / Nouveau-Brunswick": (4,"NB","New Brunswick"),
    "Newfoundland and Labrador / Terre-Neuve-et-Labrador": (5,"NL","Newfoundland and Labrador"),
    "Northwest Territories / Territoires du Nord-Ouest": (6,"NT","Northwest Territories"),
    "Nova Scotia / Nouvelle-Écosse": (7,"NS","Nova Scotia"),
    "Nunavut": (8,"NU","Nunavut"),
    "Ontario": (9,"ON","Ontario"),
    "Prince Edward Island / Île-du-Prince-Édouard": (10,"PEI","Prince Edward Island"),
    "Quebec / Québec": (11,"QC","Quebec"),
    "Saskatchewan": (12,"SK","Saskatchewan"),
    "Yukon": (13,"YT","Yukon"),
}
IDX2JUR = {v[0]: (v[1], v[2]) for v in GAUL_MAP.values()}


def pull(image, bands=None, retries=6):
    """getDownloadURL GeoTIFF -> (arr[bands,lat,lon], lat, lon), retry transient errors."""
    params = {"region": ee.Geometry.Rectangle(BBOX, "EPSG:4326", False),
              "scale": SCALE, "crs": "EPSG:4326", "format": "GEO_TIFF"}
    last = None
    for a in range(1, retries+1):
        try:
            url = image.getDownloadURL(params)
            r = requests.get(url, timeout=600); r.raise_for_status()
            with rasterio.open(io.BytesIO(r.content)) as ds:
                arr = ds.read(masked=True).astype("float32").filled(np.nan)
                T = ds.transform
                lon = T.c + T.a*(np.arange(ds.width)+0.5)
                lat = T.f + T.e*(np.arange(ds.height)+0.5)
            return arr, lat, lon
        except Exception as ex:
            last = ex; time.sleep(12*a)
    raise last


def season_image(monthly, daily, y):
    imgs = []
    for s,(m0,m1) in SEASONS.items():
        flt = ee.Filter.And(ee.Filter.calendarRange(y,y,'year'), ee.Filter.calendarRange(m0,m1,'month'))
        imgs.append(monthly.filter(flt).select("temperature_2m").mean().subtract(273.15).rename(f"{s}_tmean_c"))
        imgs.append(daily.filter(flt).select("temperature_2m_max").mean().subtract(273.15).rename(f"{s}_tmax_c"))
        imgs.append(monthly.filter(flt).select("total_precipitation_sum").sum().multiply(1000).rename(f"{s}_precip_mm"))
    return ee.Image.cat(imgs)

BANDS = [f"{s}_{m}" for s in SEASONS for m in ("tmean_c","tmax_c","precip_mm")]


def main():
    ee.Initialize(project=PROJECT)
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME","Canada"))
    name2idx = ee.Dictionary({k: v[0] for k,v in GAUL_MAP.items()})
    labeled = gaul.map(lambda f: f.set("idx", name2idx.get(f.get("ADM1_NAME"), 0)))\
                  .filter(ee.Filter.neq("idx", 0))\
                  .map(lambda f: f.simplify(10000))   # 10 km tol: makes paint tractable
    prov_img = ee.Image(0).byte().paint(labeled, "idx").rename("idx")
    lc = ee.ImageCollection("MODIS/061/MCD12Q1").filter(ee.Filter.calendarRange(2015,2015,'year'))\
            .first().select("LC_Type1")
    burnable = lc.gte(1).And(lc.lte(9)).rename("burn")

    # static rasters (once)
    provf = RASTER/"province_idx.npy"; burnf = RASTER/"burnable.npy"; gridf = RASTER/"grid.npz"
    if not (provf.exists() and burnf.exists()):
        print("pulling province-idx + burnable rasters ...")
        pa, lat, lon = pull(prov_img)                     # nearest at 0.1deg
        ba, _, _ = pull(burnable.unmask(0))
        np.save(provf, pa[0]); np.save(burnf, ba[0]); np.savez(gridf, lat=lat, lon=lon)
    prov = np.load(provf); burn = np.load(burnf)
    g = np.load(gridf); lat, lon = g["lat"], g["lon"]
    wlat = np.cos(np.deg2rad(lat))[:, None]               # cos-lat area weight
    print(f"grid {prov.shape}, provinces present: {sorted(set(np.unique(prov[~np.isnan(prov)]).astype(int))-{0})}")

    monthly = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
    daily   = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")

    rows = []
    for y in YEARS:
        f = RASTER/f"clim_{y}.npz"
        if f.exists():
            arr = np.load(f)["arr"]
        else:
            t0=time.time()
            arr,_,_ = pull(season_image(monthly, daily, y), )
            np.savez_compressed(f, arr=arr)
            print(f"  {y} pulled {arr.shape} in {time.time()-t0:.0f}s", flush=True)
        for idx,(code,jur) in IDX2JUR.items():
            m = (prov==idx) & (burn>0)
            if not m.any(): continue
            w = np.broadcast_to(wlat, prov.shape)[m]
            rec = dict(year=y, code=code, jurisdiction=jur)
            for season in SEASONS:
                for metric in ("tmean_c","tmax_c","precip_mm"):
                    bi = BANDS.index(f"{season}_{metric}")
                    v = arr[bi][m]; ok=np.isfinite(v)
                    val = np.nansum(v[ok]*w[ok])/np.sum(w[ok]) if ok.any() else np.nan
                    rec[f"{season}_{metric}"]=val
            rows.append(rec)

    df = pd.DataFrame(rows).sort_values(["code","year"])
    # tidy to long: one row per year/jurisdiction/season
    long=[]
    for _,r in df.iterrows():
        for s in SEASONS:
            long.append(dict(year=int(r.year), code=r.code, jurisdiction=r.jurisdiction, season=s,
                             tmean_c=r[f"{s}_tmean_c"], tmax_c=r[f"{s}_tmax_c"], precip_mm=r[f"{s}_precip_mm"]))
    out = pd.DataFrame(long).sort_values(["season","code","year"])
    out.to_csv(OUT/"era5land_forested_seasonal.csv", index=False)
    print("\nWrote", OUT/"era5land_forested_seasonal.csv", "shape", out.shape)
    clim = out[(out.season=="fire") & out.year.between(1991,2020)].groupby("jurisdiction")[["tmean_c","tmax_c","precip_mm"]].mean().round(1)
    print("\n1991-2020 fire-season (May-Sep) climatology:\n", clim.to_string())


if __name__ == "__main__":
    main()
