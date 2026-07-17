#!/usr/bin/env python3
"""
04_analysis.py — Temperature/precip vs area-burned relationships, robustly.

Design (per statistics review):
  - Response: log10(area burned, NBAC ha). Homogeneous satellite-era window 1972-2025.
  - Primary predictor: fire-season (May-Sep) mean temperature; also precip; and the
    PARTIAL correlation of area~temperature controlling for precip (hot<->dry confound).
  - THREE lenses reported together: raw, linearly detrended, first-differenced.
  - Autocorrelation-aware inference: effective sample size n_eff (Bretherton et al. 1999),
    moving-block bootstrap 95% CI for r, Durbin-Watson on OLS residuals.
  - Effect size: OLS slope of log10(area) on Tmean -> % change in area burned per deg C.
  - Robustness: leave-out 2023 & 2025 (high-leverage) refit.
  - Screening: only jurisdictions with >=20 nonzero NBAC years; Spearman reported for all.
  - BH-FDR across the powered-jurisdiction family. NO stats on spliced series.
  - National climate computed from saved ERA5-Land rasters (all-Canada burnable, cos-lat wt).

Outputs: outputs/tables/correlation_results.csv, merged_year_jurisdiction.csv,
         national_fire_season.csv
"""
import pathlib, numpy as np, pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.multitest import multipletests

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT/"data"/"processed"; RAS = ROOT/"data"/"era5_rasters"
OUT = ROOT/"outputs"/"tables"; OUT.mkdir(parents=True, exist_ok=True)
WIN = (1972, 2025)         # NBAC homogeneous window
MIN_NONZERO = 20
SEASON = "fire"
rng = np.random.default_rng(42)


def national_climate_from_rasters():
    """All-Canada burnable, cos-lat-weighted fire-season & jja means from saved rasters."""
    prov = np.load(RAS/"province_idx.npy"); burn = np.load(RAS/"burnable.npy")
    g = np.load(RAS/"grid.npz"); lat = g["lat"]
    wlat = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], prov.shape)
    mask = (prov > 0) & (burn > 0)                    # burnable land inside the 13 jurisdictions
    bands = [f"{s}_{m}" for s in ("fire", "jja") for m in ("tmean_c", "tmax_c", "precip_mm")]
    rows = []
    for f in sorted(RAS.glob("clim_*.npz")):
        y = int(f.stem.split("_")[1]); arr = np.load(f)["arr"]
        rec = {"year": y, "jurisdiction": "Canada", "code": "CANADA"}
        for s in ("fire", "jja"):
            for metric in ("tmean_c", "tmax_c", "precip_mm"):
                bi = bands.index(f"{s}_{metric}"); v = arr[bi]
                ok = mask & np.isfinite(v)
                rec[f"{s}_{metric}"] = np.sum(v[ok]*wlat[ok])/np.sum(wlat[ok])
        rows.append(rec)
    nat = pd.DataFrame(rows).sort_values("year")
    # rename fire_* -> tmean_c etc for the 'fire' season convenience columns
    nat = nat.rename(columns={"fire_tmean_c": "tmean_c", "fire_tmax_c": "tmax_c",
                              "fire_precip_mm": "precip_mm"})
    nat["season"] = SEASON
    return nat


def neff(x, y):
    """Effective sample size from lag-1 autocorrelation (Bretherton et al. 1999)."""
    n = len(x)
    def r1(z):
        z = z - z.mean()
        return np.corrcoef(z[:-1], z[1:])[0, 1] if n > 2 else 0.0
    rx, ry = r1(x), r1(y)
    f = (1 - rx*ry)/(1 + rx*ry)
    return max(3.0, n*np.clip(f, 0, 1))


def p_from_r(r, n_eff):
    if n_eff <= 3 or not np.isfinite(r): return np.nan
    t = r*np.sqrt((n_eff-2)/max(1e-9, 1-r**2))
    return 2*stats.t.sf(abs(t), df=n_eff-2)


def block_boot_r(x, y, nboot=2000, frac=None):
    n = len(x); L = max(2, int(round(n**0.5)))       # block length ~ sqrt(n)
    nb = int(np.ceil(n/L)); idx0 = np.arange(n)
    rs = []
    for _ in range(nboot):
        starts = rng.integers(0, n-L+1, size=nb)
        take = np.concatenate([idx0[s:s+L] for s in starts])[:n]
        xs, ys = x[take], y[take]
        if xs.std() > 0 and ys.std() > 0:
            rs.append(np.corrcoef(xs, ys)[0, 1])
    return (np.nanpercentile(rs, 2.5), np.nanpercentile(rs, 97.5)) if rs else (np.nan, np.nan)


def detrend(v):
    t = np.arange(len(v)); b = np.polyfit(t, v, 1); return v - np.polyval(b, t)


def analyze(df, label):
    """df: columns year, logA, tmean_c, precip_mm (already windowed, sorted, complete)."""
    d = df.dropna(subset=["logA", "tmean_c", "precip_mm"]).sort_values("year")
    n = len(d)
    if n < 10: return None
    A, T, P, yr = d.logA.values, d.tmean_c.values, d.precip_mm.values, d.year.values
    res = {"jurisdiction": label, "n": n, "year0": int(yr.min()), "year1": int(yr.max())}

    # --- raw / detrended / first-difference Pearson (area ~ temperature) ---
    for name, (a, t) in {"raw": (A, T),
                         "detrend": (detrend(A), detrend(T)),
                         "fdiff": (np.diff(A), np.diff(T))}.items():
        r = np.corrcoef(a, t)[0, 1]
        ne = neff(a, t)
        lo, hi = block_boot_r(a, t)
        res[f"r_{name}"] = r
        res[f"p_{name}"] = p_from_r(r, ne)
        res[f"ci_{name}"] = f"[{lo:.2f},{hi:.2f}]"
        res[f"neff_{name}"] = round(ne, 1)
    res["rho_spearman"] = stats.spearmanr(A, T).statistic
    res["r_precip_raw"] = np.corrcoef(A, P)[0, 1]

    # --- partial correlation area~temp | precip (raw) ---
    def resid(y, X):
        X = sm.add_constant(X); return y - sm.OLS(y, X).fit().predict(X)
    rA, rT = resid(A, P), resid(T, P)
    res["r_partial_T|P"] = np.corrcoef(rA, rT)[0, 1]

    # --- OLS slope -> %/degC, Durbin-Watson ---
    X = sm.add_constant(T); m = sm.OLS(A, X).fit()
    slope = m.params[1]
    res["pct_per_C"] = (10**slope - 1)*100
    res["slope_log10_perC"] = slope
    res["durbin_watson"] = durbin_watson(m.resid)

    # --- leave-out high-fire years ---
    keep = ~np.isin(yr, [2023, 2025])
    if keep.sum() >= 10:
        res["r_raw_no2023_25"] = np.corrcoef(A[keep], T[keep])[0, 1]
    return res


def main():
    clim = pd.read_csv(PROC/"era5land_forested_seasonal.csv")
    clim = clim[clim.season == SEASON]
    nat_clim = national_climate_from_rasters()

    prov = pd.read_csv(PROC/"area_burned_provincial.csv")   # year, jurisdiction, total_ha_nbac...
    natb = pd.read_csv(PROC/"area_burned_national.csv")

    # provincial merge
    m = prov.merge(clim, on=["year", "jurisdiction"], how="inner")
    m = m[m.year.between(*WIN)].copy()
    m["area_ha"] = m["total_ha_nbac"]
    # national merge
    nb = natb[["year", "total_ha_nbac"]].rename(columns={"total_ha_nbac": "area_ha"})
    nat = nb.merge(nat_clim[["year", "tmean_c", "tmax_c", "precip_mm"]], on="year", how="inner")
    nat["jurisdiction"] = "Canada"
    nat = nat[nat.year.between(*WIN)]

    allrows = pd.concat([m[["year", "jurisdiction", "area_ha", "tmean_c", "tmax_c", "precip_mm"]],
                         nat[["year", "jurisdiction", "area_ha", "tmean_c", "tmax_c", "precip_mm"]]],
                        ignore_index=True)
    allrows.to_csv(OUT/"merged_year_jurisdiction.csv", index=False)
    nat_clim.to_csv(OUT/"national_fire_season.csv", index=False)

    # log response with data-driven offset (only matters near zero; big provinces have none)
    pos = allrows[allrows.area_ha > 0].area_ha
    offset = 0.5*pos.min()
    allrows["logA"] = np.log10(allrows.area_ha.fillna(0) + offset)

    # screen jurisdictions
    nz = allrows[allrows.year.between(*WIN)].assign(nz=allrows.area_ha.fillna(0) > 0)\
             .groupby("jurisdiction").nz.sum()
    powered = [j for j in nz.index if nz[j] >= MIN_NONZERO]
    print("powered jurisdictions (>=%d nonzero yrs):" % MIN_NONZERO, sorted(powered))

    results = []
    for j in sorted(allrows.jurisdiction.unique()):
        r = analyze(allrows[allrows.jurisdiction == j], j)
        if r:
            r["powered"] = j in powered
            results.append(r)
    R = pd.DataFrame(results)

    # BH-FDR across powered provinces (exclude national from the family)
    fam = R[(R.powered) & (R.jurisdiction != "Canada")].copy()
    ok = fam.p_raw.notna()
    fam.loc[ok, "p_raw_BH"] = multipletests(fam.loc[ok, "p_raw"], method="fdr_bh")[1]
    R = R.merge(fam[["jurisdiction", "p_raw_BH"]], on="jurisdiction", how="left")

    cols = ["jurisdiction","powered","n","year0","year1","r_raw","p_raw","p_raw_BH","ci_raw",
            "neff_raw","rho_spearman","r_detrend","p_detrend","r_fdiff","p_fdiff",
            "r_precip_raw","r_partial_T|P","pct_per_C","durbin_watson","r_raw_no2023_25"]
    R = R[[c for c in cols if c in R.columns]].sort_values(
        ["powered","r_raw"], ascending=[False, False])
    R.to_csv(OUT/"correlation_results.csv", index=False)

    pd.set_option("display.width", 200, "display.max_columns", 30)
    show = R[R.powered][["jurisdiction","n","r_raw","p_raw_BH","r_detrend","r_fdiff",
                         "r_partial_T|P","r_precip_raw","pct_per_C"]].round(3)
    print("\n=== Fire-season Tmean vs log10(area burned), NBAC %d-%d ===" % WIN)
    print(show.to_string(index=False))
    print("\nWrote", OUT/"correlation_results.csv")


if __name__ == "__main__":
    main()
