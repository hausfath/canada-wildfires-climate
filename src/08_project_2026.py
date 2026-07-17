#!/usr/bin/env python3
"""
08_project_2026.py — preliminary FULL fire-season 2026 estimate from year-to-date data.

Calibrates the relationship between year-to-date (YTD, May 1 - Jul 9) and full-season
(May-Sep) national values across past years, then applies it to 2026's partial data.
  - Temperature & precip: pull YTD national (burnable-land, cos-lat weighted) from ERA5-Land
    via GEE (May+Jun monthly + Jul 1-9 daily), regress full-season (from national_fire_season.csv)
    on YTD over 1972-2025, predict 2026 (with OLS prediction SE).
  - Area burned: project full-year from the 2026 mid-July total (2.5 Mha) using the historical
    ratio of annual to mid-July cumulative area (NFD monthly, national).

Output: data/processed/proj_2026.json
"""
import ee, io, time, json, pathlib, numpy as np, pandas as pd, requests, rasterio
import statsmodels.api as sm

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT/"data"/"processed"; RAS = ROOT/"data"/"era5_rasters"
PROJECT = "api-project-819195003802"
BBOX = [-141.5, 41.0, -52.0, 84.0]; SCALE = 11132
CAL = range(1972, 2026)          # calibration years (full-season known)
AREA_YTD_2026 = 2.75e6           # CIFFC reported to 2026-07-17 (ha)


def pull(image, retries=6):
    params = {"region": ee.Geometry.Rectangle(BBOX, "EPSG:4326", False),
              "scale": SCALE, "crs": "EPSG:4326", "format": "GEO_TIFF"}
    last = None
    for a in range(1, retries+1):
        try:
            url = image.getDownloadURL(params)
            r = requests.get(url, timeout=600); r.raise_for_status()
            with rasterio.open(io.BytesIO(r.content)) as ds:
                return ds.read(masked=True).astype("float32").filled(np.nan)
        except Exception as ex:
            last = ex; time.sleep(12*a)
    raise last


def main():
    ee.Initialize(project=PROJECT)
    monthly = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
    daily = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
    lc = ee.ImageCollection("MODIS/061/MCD12Q1").filter(ee.Filter.calendarRange(2015,2015,'year')).first().select("LC_Type1")
    burnable = lc.gte(1).And(lc.lte(9))

    prov = np.load(RAS/"province_idx.npy"); burn = np.load(RAS/"burnable.npy")
    g = np.load(RAS/"grid.npz"); lat = g["lat"]
    wlat = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], prov.shape)
    mask = (prov > 0) & (burn > 0)
    W = wlat[mask]

    def ytd_image(y):
        mon = monthly.filter(ee.Filter.calendarRange(y, y, 'year')).filter(ee.Filter.calendarRange(5, 6, 'month'))
        tmm = mon.select("temperature_2m").mean()                       # ~May+Jun mean (K)
        pmm = mon.select("total_precipitation_sum").sum().multiply(1000) # May+Jun total (mm)
        dj = daily.filter(ee.Filter.calendarRange(y, y, 'year'))\
                  .filter(ee.Filter.calendarRange(7, 7, 'month')).filter(ee.Filter.calendarRange(1, 9, 'day_of_month'))
        tj = dj.select("temperature_2m").mean()
        pj = dj.select("total_precipitation_sum").sum().multiply(1000)
        tmean = tmm.multiply(61).add(tj.multiply(9)).divide(70).subtract(273.15).rename("ytd_tmean")  # day-weighted May1-Jul9
        precip = pmm.add(pj).rename("ytd_precip")
        return ee.Image.cat([tmean, precip]).updateMask(burnable)

    def natl(arr):
        v = arr[mask]; ok = np.isfinite(v)
        return float(np.sum(v[ok]*W[ok])/np.sum(W[ok]))

    ytd_cache = PROC/"ytd_2026_calib.csv"
    if ytd_cache.exists():
        ytd = pd.read_csv(ytd_cache)
        print("loaded cached YTD pull", ytd_cache)
    else:
        rows = []
        for y in list(CAL) + [2026]:
            a = pull(ytd_image(y))
            rows.append(dict(year=y, ytd_tmean=natl(a[0]), ytd_precip=natl(a[1])))
            print(f"  {y} ytd_tmean={rows[-1]['ytd_tmean']:.2f}C ytd_precip={rows[-1]['ytd_precip']:.0f}mm", flush=True)
            pd.DataFrame(rows).to_csv(ytd_cache, index=False)   # incremental cache (resumable)
        ytd = pd.DataFrame(rows)

    full = pd.read_csv(ROOT/"outputs"/"tables"/"national_fire_season.csv")[["year", "tmean_c", "precip_mm"]]
    cal = ytd.merge(full, on="year").query("year in @CAL")

    def fit_predict(xcol, ycol, xnew):
        X = sm.add_constant(cal[xcol]); m = sm.OLS(cal[ycol], X).fit()
        pr = m.get_prediction(sm.add_constant(pd.Series([xnew]), has_constant="add"))
        f = pr.summary_frame(alpha=0.32)  # ~1 sigma
        # PREDICTION interval (obs_ci) — includes residual scatter, not just fitted-line uncertainty
        return float(f["mean"].iloc[0]), float(f["mean"].iloc[0]-f["obs_ci_lower"].iloc[0]), m.rsquared

    y26 = ytd.query("year==2026").iloc[0]
    t_full, t_se, t_r2 = fit_predict("ytd_tmean", "tmean_c", y26.ytd_tmean)
    p_full, p_se, p_r2 = fit_predict("ytd_precip", "precip_mm", y26.ytd_precip)

    # area: annual / mid-July cumulative ratio from NFD monthly
    mo = pd.read_csv(ROOT/"data"/"nfd_area_burned_by_month.csv", encoding="latin-1").rename(columns={"Area (hectares)": "ha"})
    mmap = {m: i for i, m in enumerate(["January","February","March","April","May","June","July",
            "August","September","October","November","December"], 1)}
    mo["m"] = mo["Month"].map(mmap)
    nat = mo.groupby(["Year", "m"]).ha.sum().unstack(fill_value=0)
    ann = nat.sum(1); midjul = nat.loc[:, 1:6].sum(1) + 0.5*nat.get(7, 0)
    ratio = (ann/midjul).replace([np.inf], np.nan).dropna()
    ratio = ratio[(ann > 5e4)]                       # drop near-zero years
    r_med = float(ratio.median())
    area_full = AREA_YTD_2026 * r_med

    proj = dict(year=2026, preliminary=True,
                ytd_tmean_c=float(y26.ytd_tmean), ytd_precip_mm=float(y26.ytd_precip),
                tmean_c=t_full, tmean_se=t_se, tmean_r2=t_r2,
                precip_mm=p_full, precip_se=p_se, precip_r2=p_r2,
                area_ha=area_full, area_ytd_ha=AREA_YTD_2026, area_ratio=r_med,
                note="Full May-Sep projected from YTD (May1-Jul9) via OLS on 1972-2025; area from annual/mid-July ratio.")
    (PROC/"proj_2026.json").write_text(json.dumps(proj, indent=2))
    print("\n=== 2026 PRELIMINARY PROJECTION ===")
    print(f"  YTD:  tmean {y26.ytd_tmean:.2f}C  precip {y26.ytd_precip:.0f}mm")
    print(f"  full tmean = {t_full:.2f} ± {t_se:.2f} C   (R²={t_r2:.2f})")
    print(f"  full precip= {p_full:.0f} ± {p_se:.0f} mm  (R²={p_r2:.2f})")
    print(f"  full area  = {area_full/1e6:.1f} Mha   (×{r_med:.2f} of mid-July {AREA_YTD_2026/1e6:.1f} Mha)")
    print("  wrote", PROC/"proj_2026.json")


if __name__ == "__main__":
    main()
