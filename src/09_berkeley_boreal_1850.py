#!/usr/bin/env python3
"""
09_berkeley_boreal_1850.py — Fire-season (May-Sep) temperature over Canadian boreal
forested land since 1850, from Berkeley Earth high-res gridded data.

Extends the ERA5-Land fire-season warming analysis (which starts 1959) back to 1850
using Berkeley Earth's 0.25deg monthly land+ocean anomaly field.

Region = the SAME "forested Canada" mask behind the rest of this project:
  MODIS IGBP forest/shrub/savanna (classes 1-9) intersected with Canadian
  provinces/territories, from data/era5_rasters/{burnable.npy, province_idx.npy, grid.npz}.
  That 0.1deg mask is regridded (nearest-neighbour) onto the Berkeley 0.25deg grid.
  Boreal-dominated by construction (Canada's forest is overwhelmingly boreal/taiga);
  a >=50N variant is also written as a strict-boreal sensitivity check.

Response: Berkeley Earth surface-temperature ANOMALY (deg C vs its 1951-1980 climatology).
  Absolute baseline is irrelevant here — we report CHANGE (smoothed 2025 minus smoothed
  1850, and vs an 1850-1900 pre-industrial mean), matching fig 6's LOWESS-difference method.

Outputs:
  outputs/tables/berkeley_boreal_fireseason_1850_2025.csv   (annual series + LOWESS)
  outputs/figures/7_boreal_fireseason_1850.png              (time series, hero)
  outputs/figures/8_boreal_fireseason_warming_map_1850.png  (per-gridcell change map)
"""
import pathlib, numpy as np, pandas as pd
import xarray as xr
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.nonparametric.smoothers_lowess import lowess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLIMATE_MAP = ROOT.parent / "Climate Map"
BERK = CLIMATE_MAP / "Global_TAVG_Gridded_0p25deg.nc"
RAST = ROOT / "data" / "era5_rasters"
FIG = ROOT / "outputs" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
TAB = ROOT / "outputs" / "tables"; TAB.mkdir(parents=True, exist_ok=True)

FIRE = "#c0392b"; INK = "#222222"; GREY = "#9aa0a6"
FIRE_MONTHS = (5, 6, 7, 8, 9)          # May-Sep, matching the ERA5-Land analysis
BASE0, BASE1 = 1850, 1900              # pre-industrial reference window
SRC = ("Data: Berkeley Earth 0.25° gridded land+ocean anomaly (1850–2026); "
       "forest mask MODIS MCD12Q1 IGBP 1–9 ∩ Canadian provinces.")


def berkeley_month(dec_year):
    """Berkeley decimal-year -> (integer year, integer month 1-12)."""
    yr = np.floor(dec_year).astype(int)
    mon = np.round((dec_year - yr) * 12 + 0.5).astype(int)
    return yr, mon


def build_forest_mask_on_berkeley(blat, blon, min_lat=None):
    """Nearest-neighbour regrid of the 0.1deg forested-Canada mask onto Berkeley cells."""
    g = np.load(RAST / "grid.npz"); mlat, mlon = g["lat"], g["lon"]
    burn = np.load(RAST / "burnable.npy")                      # 1 = forest/shrub/savanna, else nan
    prov = np.load(RAST / "province_idx.npy")                  # province id (1-14), else nan/<=0
    forested = np.isfinite(burn) & (burn > 0.5) & np.isfinite(prov) & (prov > 0)
    # normalise mask grid to ascending lat/lon (raster lat is north->south)
    if mlat[0] > mlat[-1]:
        mlat = mlat[::-1]; forested = forested[::-1, :]
    if mlon[0] > mlon[-1]:
        mlon = mlon[::-1]; forested = forested[:, ::-1]
    # nearest mask index for each berkeley coordinate (grids are regular -> searchsorted)
    def nn(coord, grid):
        idx = np.searchsorted(grid, coord)
        idx = np.clip(idx, 1, len(grid) - 1)
        left = grid[idx - 1]; right = grid[idx]
        idx[np.abs(coord - left) <= np.abs(coord - right)] -= 1
        return idx
    within = (blat >= mlat.min()) & (blat <= mlat.max())
    withinx = (blon >= mlon.min()) & (blon <= mlon.max())
    ilat = np.where(within, nn(blat, mlat), 0)
    ilon = np.where(withinx, nn(blon, mlon), 0)
    mask = forested[np.ix_(ilat, ilon)]
    mask &= within[:, None] & withinx[None, :]
    if min_lat is not None:
        mask &= (blat[:, None] >= min_lat)
    return mask


def fire_season_series(min_lat=None, label="forested Canada"):
    ds = xr.open_dataset(BERK, decode_times=False)
    # Canada bounding box to keep memory sane
    ds = ds.sel(latitude=slice(41, 84), longitude=slice(-142, -51))
    blat = ds.latitude.values; blon = ds.longitude.values
    yr, mon = berkeley_month(ds.time.values)
    sel = np.isin(mon, FIRE_MONTHS)
    sub = ds.temperature.isel(time=np.where(sel)[0])           # (t, lat, lon) anomaly
    syr = yr[sel]
    mask = build_forest_mask_on_berkeley(blat, blon, min_lat=min_lat)
    print(f"[{label}] berkeley forested cells: {int(mask.sum())} "
          f"(min_lat={min_lat})")
    w = np.cos(np.deg2rad(blat))[:, None] * mask               # cos-lat area weight
    w = np.broadcast_to(w, (1,) + w.shape)
    arr = sub.values                                           # load subset (~200MB)
    valid = np.isfinite(arr)
    wa = np.where(valid, w, 0.0)
    num = np.nansum(np.where(valid, arr, 0.0) * wa, axis=(1, 2))
    den = np.nansum(wa, axis=(1, 2))
    monthly = num / den                                        # per (year,month) fire-month mean
    df = pd.DataFrame({"year": syr, "t": monthly})
    ann = df.groupby("year").t.mean().reset_index()            # fire-season (May-Sep) mean/yr
    ann = ann[ann.year <= 2025]                                # drop partial 2026
    lo = lowess(ann.t.values, ann.year.values, frac=0.25, return_sorted=False)
    ann["lowess"] = lo
    ds.close()
    return ann, mask, blat, blon


def per_gridcell_change(blat, blon, mask):
    """Smoothed(2025) - smoothed(1850) fire-season anomaly per cell (for the map)."""
    ds = xr.open_dataset(BERK, decode_times=False).sel(
        latitude=slice(41, 84), longitude=slice(-142, -51))
    yr, mon = berkeley_month(ds.time.values)
    sel = np.isin(mon, FIRE_MONTHS) & (yr <= 2025)
    arr = ds.temperature.isel(time=np.where(sel)[0]).values
    syr = yr[sel]
    years = np.unique(syr)
    # fire-season mean per year per cell
    fs = np.stack([np.nanmean(arr[syr == y], axis=0) for y in years])  # (nyear, lat, lon)
    change = np.full(mask.shape, np.nan)
    ys = years.astype(float)
    for i in range(mask.shape[0]):
        for j in range(mask.shape[1]):
            if not mask[i, j]:
                continue
            col = fs[:, i, j]
            good = np.isfinite(col)
            if good.sum() < 60:
                continue
            sm = lowess(col[good], ys[good], frac=0.3, return_sorted=False)
            change[i, j] = sm[-1] - sm[0]
    ds.close()
    return change


def main():
    ann, mask, blat, blon = fire_season_series(label="forested Canada (boreal-dominated)")
    ann_b, _, _, _ = fire_season_series(min_lat=50, label="forested Canada >=50N (strict boreal)")

    pre = ann[ann.year.between(BASE0, BASE1)].t.mean()
    recent = ann[ann.year.between(2011, 2025)].t.mean()
    chg_lowess = ann.lowess.iloc[-1] - ann.lowess.iloc[0]
    chg_pre = recent - pre
    print(f"\nfire-season change (LOWESS 2025 - 1850): {chg_lowess:+.2f} C")
    print(f"fire-season 2011-2025 mean vs {BASE0}-{BASE1}: {chg_pre:+.2f} C")

    out = ann.rename(columns={"t": "fireseason_anom_c", "lowess": "fireseason_lowess_c"})
    out["fireseason_anom_c_ge50N"] = ann_b.set_index("year").reindex(out.year).t.values
    out.to_csv(TAB / "berkeley_boreal_fireseason_1850_2025.csv", index=False)
    print("wrote", TAB / "berkeley_boreal_fireseason_1850_2025.csv")

    # ---- figure 7: time series ----
    fig, ax = plt.subplots(figsize=(10.2, 6.0))
    fig.subplots_adjust(top=0.83, bottom=0.12, left=0.09, right=0.97)
    ax.bar(ann.year, ann.t, width=0.9,
           color=np.where(ann.t >= 0, FIRE, "#6699cc"), alpha=0.35, zorder=1)
    ax.plot(ann.year, ann.lowess, color=FIRE, lw=2.6, zorder=3, label="LOWESS smooth")
    ax.axhline(pre, color=INK, ls="--", lw=1, alpha=.7)
    ax.text(1852, pre + .10, "1850–1900 mean", fontsize=8.5, color=INK)
    ax.annotate(f"+{chg_lowess:.1f} °C since 1850", xy=(2024, ann.lowess.iloc[-1]),
                xytext=(1946, 2.75), fontsize=11, fontweight="bold",
                color=FIRE, ha="left", va="center",
                arrowprops=dict(arrowstyle="->", color=FIRE, connectionstyle="arc3,rad=-0.15"))
    ax.set_xlim(1848, 2027); ax.set_ylim(-2.6, 3.4)
    ax.set_ylabel("Fire-season (May–Sep) temperature anomaly (°C)")
    ax.set_xlabel("Year")
    ax.grid(alpha=.25)
    fig.suptitle("Canada's boreal fire seasons have warmed sharply since the 19th century",
                 y=0.965, fontsize=14.5, fontweight="bold", color=INK)
    fig.text(0.5, 0.90, "May–September mean temperature over Canadian forested (boreal-dominated) "
             "land, anomaly vs 1951–1980.", ha="center", fontsize=9.6, color="#555")
    fig.text(0.006, 0.015, SRC, fontsize=6.4, color="#888")
    fig.savefig(FIG / "7_boreal_fireseason_1850.png", dpi=200)
    plt.close(fig); print("wrote 7_boreal_fireseason_1850.png")

    # ---- figure 8: per-gridcell change map ----
    change = per_gridcell_change(blat, blon, mask)
    fig, ax = plt.subplots(figsize=(10.5, 7.4))
    fig.subplots_adjust(top=0.86, bottom=0.05, left=0.04, right=0.90)
    vmax = 3.5
    pcm = ax.pcolormesh(blon, blat, np.ma.masked_invalid(change), cmap="RdBu_r",
                        vmin=-vmax, vmax=vmax, shading="auto")
    try:
        import geopandas as gpd
        prov = gpd.read_file(ROOT / "data" / "boundaries" / "ne_admin1" /
                             "ne_50m_admin_1_states_provinces.shp")
        ca = prov[prov.admin == "Canada"]
        ca.boundary.plot(ax=ax, color="#444", lw=.5, zorder=3)
    except Exception as e:
        print("boundary overlay skipped:", e)
    ax.set_aspect(1 / np.cos(np.deg2rad(float(np.nanmean(blat[blat < 75])))))
    ax.set_xlim(-142, -51); ax.set_ylim(41, 76)
    ax.set_axis_off()
    cb = fig.colorbar(pcm, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("Change in fire-season mean temperature, 1850→2025 (°C)")
    mean_chg = np.nanmean(change)
    ax.text(0.02, 0.06, f"Boreal-forest mean:\n+{mean_chg:.1f} °C", transform=ax.transAxes,
            fontsize=11, fontweight="bold", color=FIRE, va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=FIRE, lw=1.2))
    fig.suptitle("Fire-season warming across Canadian boreal forest since 1850",
                 y=0.955, fontsize=14.5, fontweight="bold", color=INK)
    fig.text(0.5, 0.895, "Change in May–Sep mean temperature (per-gridcell LOWESS 2025 minus 1850), "
             "Berkeley Earth.", ha="center", fontsize=9.6, color="#555")
    fig.text(0.006, 0.012, SRC, fontsize=6.4, color="#888")
    fig.savefig(FIG / "8_boreal_fireseason_warming_map_1850.png", dpi=200)
    plt.close(fig); print("wrote 8_boreal_fireseason_warming_map_1850.png")


if __name__ == "__main__":
    main()
