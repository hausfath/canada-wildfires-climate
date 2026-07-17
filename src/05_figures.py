#!/usr/bin/env python3
"""
05_figures.py — Shareable chart thread on Canadian wildfire + climate.

Charts (outputs/figures/):
  1 hero_area_burned.png       National area burned 1959-2026 (smoke != area annotation)
  2 fire_season_weather.png    Canada Fire Season Weather (Rohde replica): temp x precip,
                               era-colored, marker size ~ area burned, quadrants
  3 provincial_relationship.png Per-province temp<->area correlation (r +/- bootstrap CI, %/degC)
  4 map_2023_fires.png         2023 large-fire footprints over Canada/boreal
  5 cause_split.png            Lightning vs human share of area burned (context)

Style: colorblind-safe, title/subtitle gap (suptitle y~0.99, subtitle y~0.95),
source + caveat footnotes on every chart.
"""
import pathlib, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAB = ROOT/"outputs"/"tables"; PROC = ROOT/"data"/"processed"
FIG = ROOT/"outputs"/"figures"; FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 200, "axes.grid": True,
                     "grid.alpha": .25, "axes.axisbelow": True})
FIRE = "#c0392b"; WARM = "#e67e22"; COOL = "#2c7fb8"; INK = "#222222"; GREY = "#9aa0a6"
SRC = "Data: NRCan CNFDB/NBAC & Nat. Forestry Database; CIFFC (2026, prelim.); ERA5-Land (ECMWF/Copernicus via Google Earth Engine)."


def _foot(fig, extra=""):
    fig.text(0.006, 0.020, SRC, fontsize=6.2, color="#888", ha="left", va="bottom")
    if extra:
        fig.text(0.006, 0.004, extra, fontsize=6.2, color="#888", ha="left", va="bottom")


def _titles(fig, title, sub, tsize=15.5):
    """Generous title/subtitle gap (memory: clear space between the two)."""
    fig.suptitle(title, y=0.972, fontsize=tsize, fontweight="bold", color=INK)
    fig.text(0.5, 0.905, sub, ha="center", fontsize=9.7, color="#555")


# ---------- 1. hero national area burned ----------
def fig_hero():
    nat = pd.read_csv(PROC/"area_burned_national.csv")
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    fig.subplots_adjust(top=0.83, bottom=0.14, left=0.09, right=0.97)
    # NBAC primary 1972-2025, point pre-1972 as context, 2026 partial hatched
    nb = nat[nat.total_ha_nbac.notna()]
    pre = nat[(nat.year < 1972)]
    ax.bar(pre.year, pre.total_ha_point/1e6, color="#b8b8b8", width=.85, label="1959–1971 (point-based, less complete)")
    ax.bar(nb.year, nb.total_ha_nbac/1e6, color=FIRE, width=.85, label="1972–2025 (NBAC satellite composite)")
    y26 = nat[nat.year == 2026]
    if len(y26):
        ax.bar(2026, float(y26.total_ha_point.iloc[0])/1e6, color=FIRE, width=.85,
               hatch="////", edgecolor="white", label="2026 (Jan–mid-Jul only, partial)")
    # long-term average line (full NBAC record 1972-2025)
    lt = nb.total_ha_nbac.mean()/1e6
    ax.axhline(lt, color=INK, ls="--", lw=1, alpha=.7)
    ax.text(1973, lt+.15, f"1972–2025 average ≈ {lt:.1f} Mha", fontsize=8.5, color=INK)
    # annotations
    v23 = float(nb[nb.year == 2023].total_ha_nbac.iloc[0])/1e6
    ax.annotate(f"2023: {v23:.1f} Mha\nall-time record (~2.5× prior)", xy=(2023, v23),
                xytext=(2007, 15.0), fontsize=9, fontweight="bold", color=FIRE, ha="left",
                arrowprops=dict(arrowstyle="->", color=FIRE))
    v25 = float(nb[nb.year == 2025].total_ha_nbac.iloc[0])/1e6
    ax.annotate(f"2025: {v25:.1f} Mha\n(2nd largest)", xy=(2025, v25), xytext=(2013.5, 9.6),
                fontsize=8.5, color=FIRE, ha="left", arrowprops=dict(arrowstyle="->", color=FIRE))
    v26 = float(y26.total_ha_point.iloc[0])/1e6
    ax.annotate("2026 to mid-July (~2.8 Mha, partial) is running at/above\nthe typical pace for this date — not a record-area year.\nThe air-quality crisis is about SMOKE transport, not hectares.",
                xy=(2026, v26+.1), xytext=(1996, 12.4), fontsize=8.4, color="#333",
                arrowprops=dict(arrowstyle="->", color="#777", connectionstyle="arc3,rad=0.15"),
                bbox=dict(boxstyle="round,pad=0.35", fc="#fff6e5", ec="#e0b060", lw=.8))
    ax.set_ylabel("Area burned (million hectares)"); ax.set_xlabel("Year")
    ax.set_xlim(1957.5, 2027.5); ax.set_ylim(0, 16.5)
    ax.legend(loc="upper left", fontsize=8.3, framealpha=.9)
    _titles(fig, "Canada's wildfire area burned has surged — 2023 shattered the record",
            "Annual forest area burned, 1959–2026.  2023 alone burned more than the previous record by ~2.5×.")
    _foot(fig, "NBAC = National Burned Area Composite (spatially mapped). Pre-1972 point-based totals are less complete.")
    fig.savefig(FIG/"1_hero_area_burned.png"); plt.close(fig); print("wrote 1_hero_area_burned.png")


# ---------- 2. Rohde-style fire-season weather ----------
def fig_weather(show_2026=False):
    nat = pd.read_csv(TAB/"national_fire_season.csv")            # year, tmean_c, precip_mm...
    ab = pd.read_csv(PROC/"area_burned_national.csv")[["year", "total_ha_nbac", "total_ha_point"]]
    d = nat.merge(ab, on="year").copy()
    d["area"] = d.total_ha_nbac.fillna(d.total_ha_point)
    d = d[d.year.between(1959, 2025)].dropna(subset=["tmean_c", "precip_mm", "area"])
    eras = [(1959,1971,"#000000","1959–71"),(1972,1984,"#1f78b4","1972–84"),
            (1985,1997,"#33a02c","1985–97"),(1998,2010,"#e6ab02","1998–2010"),
            (2011,2025,"#e31a1c","2011–25")]
    fig, ax = plt.subplots(figsize=(10.6, 8.0))
    fig.subplots_adjust(top=0.83, bottom=0.13, left=0.09, right=0.80)
    tmed, pmed = d.tmean_c.median(), d.precip_mm.median()
    ax.axvline(tmed, color="#888", lw=1); ax.axhline(pmed, color="#888", lw=1)
    smin, smax = d.area.min()/1e6, d.area.max()/1e6
    def msize(a):  # marker area scaled by Mha
        return 30 + 900*(a/1e6 - smin)/(smax - smin + 1e-9)
    top10 = set(d.nlargest(10, "area").year)                       # 10 largest fire years -> black border
    for y0,y1,c,lab in eras:
        s = d[d.year.between(y0,y1)]
        ec = ["black" if yr in top10 else "white" for yr in s.year]
        lw = [1.7 if yr in top10 else 0.6 for yr in s.year]
        ax.scatter(s.tmean_c, s.precip_mm, s=msize(s.area.values), c=c, alpha=.82,
                   edgecolor=ec, linewidth=lw, label=lab, zorder=3)
    # label the biggest three in black, BESIDE the dot (offset), not on top
    for _,r in d.nlargest(3, "area").iterrows():
        dx = -14 if r.tmean_c > tmed else 14
        ax.annotate(f"{int(r.year)}", (r.tmean_c, r.precip_mm), textcoords="offset points",
                    xytext=(dx, 0), ha="right" if dx < 0 else "left", va="center",
                    fontsize=10.5, fontweight="bold", color="black", zorder=5)
    # preliminary 2026 point: full season projected from year-to-date (see 08_project_2026.py).
    # Rendered as a normal 2011-25 (red) circle sized by projected area; black outline ONLY if
    # its projected area would rank in the all-time top 10.
    import json
    pj = ROOT/"data"/"processed"/"proj_2026.json"
    if show_2026 and pj.exists():
        p = json.loads(pj.read_text())
        thr10 = d.nlargest(10, "area").area.min()          # 10th-largest historical area
        in_top10 = p["area_ha"] > thr10
        ec = "black" if in_top10 else "white"
        lw = 1.7 if in_top10 else 0.5
        ax.errorbar(p["tmean_c"], p["precip_mm"], xerr=p["tmean_se"], yerr=p["precip_se"],
                    fmt="none", ecolor="#666", elinewidth=1.0, capsize=3, alpha=.8, zorder=6)
        ax.scatter([p["tmean_c"]], [p["precip_mm"]], s=msize(p["area_ha"]), marker="o",
                   c="#e31a1c", edgecolor=ec, linewidth=lw, alpha=.82, zorder=7)
        ax.annotate("2026 (projected)", (p["tmean_c"]+p["tmean_se"], p["precip_mm"]+p["precip_se"]),
                    textcoords="offset points", xytext=(10, 14), ha="left", va="bottom",
                    fontsize=9.5, fontweight="bold", color="#e31a1c", zorder=8)
    # quadrant labels
    xr, yr = ax.get_xlim(), ax.get_ylim()
    ax.text(xr[0]+.05*(xr[1]-xr[0]), yr[1]-.05*(yr[1]-yr[0]), "Cool & Wet", fontsize=10, color="#555", va="top")
    ax.text(xr[1]-.02*(xr[1]-xr[0]), yr[1]-.05*(yr[1]-yr[0]), "Hot & Wet", fontsize=10, color="#555", va="top", ha="right")
    ax.text(xr[0]+.05*(xr[1]-xr[0]), yr[0]+.03*(yr[1]-yr[0]), "Cool & Dry", fontsize=10, color="#555", va="bottom")
    ax.text(xr[1]-.02*(xr[1]-xr[0]), yr[0]+.03*(yr[1]-yr[0]), "Hot & Dry", fontsize=11, color=FIRE, va="bottom", ha="right", fontweight="bold")
    ax.set_xlabel("Fire-season (May–Sep) mean temperature over burnable land (°C)")
    ax.set_ylabel("Fire-season (May–Sep) total precipitation (mm)")
    # two legends OUTSIDE the plot (right) so quadrant corners stay clear.
    # Build era handles explicitly so the legend swatches don't inherit a per-point black edge.
    era_handles = [Line2D([], [], marker='o', ls='', mfc=c, mec='white', mew=.6, ms=10, label=lab)
                   for _, _, c, lab in eras]
    leg1 = ax.legend(handles=era_handles, title="Era", loc="upper left", bbox_to_anchor=(1.02, 1.0),
                     fontsize=9, framealpha=.95)
    ax.add_artist(leg1)
    size_handles = [Line2D([], [], marker='o', ls='', mfc="#aaa", mec="white",
                           ms=np.sqrt(msize(a*1e6)/np.pi), label=f"{a} Mha") for a in [2, 8, 15]]
    leg2 = ax.legend(handles=size_handles, loc="center left", bbox_to_anchor=(1.02, 0.46),
                     fontsize=8.5, title="Area burned\n(national)", framealpha=.95, labelspacing=1.4, borderpad=1.0)
    ax.add_artist(leg2)
    top10_handle = [Line2D([], [], marker='o', ls='', mfc="#bbb", mec="black", mew=1.6, ms=11,
                           label="10 largest\nfire years")]
    ax.legend(handles=top10_handle, loc="lower left", bbox_to_anchor=(1.02, 0.03),
              fontsize=8.5, framealpha=.95, handletextpad=.7, borderpad=.9)
    _titles(fig, "Canada Fire Season Weather",
            "Each dot is a year (1959–2025). Hotter, drier fire seasons — bottom-right — burn the most. Recent years (red) cluster there.")
    _foot(fig, "Temperature/precip: burnable-land area-weighted, forested provinces. Marker size ∝ national area burned (NBAC).")
    name = "2b_fire_season_weather_2026.png" if show_2026 else "2_fire_season_weather.png"
    fig.savefig(FIG/name); plt.close(fig); print("wrote", name)


# ---------- 3. provincial relationship ----------
def fig_provincial():
    R = pd.read_csv(TAB/"correlation_results.csv")
    natl = R[R.jurisdiction == "Canada"].iloc[0]
    R = R[(R.powered) & (R.jurisdiction != "Canada")].copy()
    R["lo"] = R.ci_raw.str.extract(r"\[([-\d.]+),").astype(float)
    R["hi"] = R.ci_raw.str.extract(r",([-\d.]+)\]").astype(float)
    R["sig"] = R.p_raw_BH < 0.05
    R = R.sort_values("r_raw")
    fig, ax = plt.subplots(figsize=(10.0, 6.8))
    fig.subplots_adjust(top=0.82, bottom=0.11, left=0.24, right=0.95)
    y = np.arange(len(R))
    for yi, (_, r) in zip(y, R.iterrows()):
        c = FIRE if r.sig else GREY
        ax.hlines(yi, r.lo, r.hi, color=c, lw=2, alpha=.55, zorder=1)
        ax.scatter(r.r_raw, yi, s=80, color=c, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels(R.jurisdiction)
    ax.axvline(0, color=INK, lw=1)
    ax.set_xlabel("Correlation (r): fire-season temperature vs. log(annual area burned), 1972–2025")
    ax.set_xlim(-0.35, 0.95)
    # national effect-size callout
    ax.text(0.98, 0.045, f"Nationally, area burned rises\n≈ +{natl.pct_per_C:.0f}% per +1 °C of\nfire-season warming (r = {natl.r_raw:.2f})",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color=INK,
            bbox=dict(boxstyle="round,pad=0.4", fc="#fdecea", ec=FIRE, lw=1))
    leg = [Line2D([],[],marker='o',ls='',color=FIRE,label="significant (FDR<0.05)"),
           Line2D([],[],marker='o',ls='',color=GREY,label="not significant")]
    ax.legend(handles=leg, loc="upper left", fontsize=8.5, framealpha=.9)
    _titles(fig, "Hotter fire seasons see more area burned — strongest in the west & north",
            "Correlation of fire-season temperature with annual area burned by province/territory (95% block-bootstrap intervals).", tsize=14.5)
    _foot(fig, "NBAC 1972–2025. Bivariate association: temperature co-varies with drought/VPD. Eastern provinces (QC, NL, NB) weaker/non-significant.")
    fig.savefig(FIG/"3_provincial_relationship.png"); plt.close(fig); print("wrote 3_provincial_relationship.png")


# ---------- 3b. provincial diagnostic: scatter + fit per region ----------
def fig_provincial_diagnostic():
    import matplotlib.gridspec as gridspec
    m = pd.read_csv(TAB/"merged_year_jurisdiction.csv")
    R = pd.read_csv(TAB/"correlation_results.csv").set_index("jurisdiction")
    powered = [j for j in R.index if R.loc[j, "powered"]]
    # order: Canada first, then by r descending
    prov = [j for j in powered if j != "Canada"]
    prov = sorted(prov, key=lambda j: -R.loc[j, "r_raw"])
    order = (["Canada"] if "Canada" in powered else []) + prov
    ncol = 4; nrow = int(np.ceil(len(order)/ncol))
    fig = plt.figure(figsize=(12.5, 2.7*nrow + 1.3))
    fig.subplots_adjust(top=1-1.0/(2.7*nrow+1.3), bottom=0.09, left=0.07, right=0.985, hspace=0.5, wspace=0.28)
    gs = gridspec.GridSpec(nrow, ncol, figure=fig)
    for k, j in enumerate(order):
        ax = fig.add_subplot(gs[k//ncol, k % ncol])
        d = m[(m.jurisdiction == j) & (m.area_ha > 0)].dropna(subset=["tmean_c", "area_ha"])
        x, y = d.tmean_c.values, d.area_ha.values
        sig = bool(R.loc[j, "p_raw_BH"] < 0.05) if not pd.isna(R.loc[j, "p_raw_BH"]) else (j == "Canada")
        c = FIRE if sig else GREY
        ax.scatter(x, y, s=14, color=c, alpha=.6, edgecolor="none")
        # OLS fit in log10 space
        b = np.polyfit(x, np.log10(y), 1)
        xr = np.linspace(x.min(), x.max(), 50)
        ax.plot(xr, 10**np.polyval(b, xr), color=c, lw=1.8)
        ax.set_yscale("log")
        r = R.loc[j, "r_raw"]
        ax.set_title(f"{j}", fontsize=9.5, fontweight="bold")
        ax.text(0.04, 0.93, f"r = {r:.2f}", transform=ax.transAxes, fontsize=8.5, va="top",
                color=c, fontweight="bold")
        ax.tick_params(labelsize=7.5); ax.grid(alpha=.2, which="both")
    fig.suptitle("Fire-season temperature vs. area burned — the data behind the correlations",
                 y=0.985, fontsize=15, fontweight="bold", color=INK)
    fig.text(0.5, 0.955, "One point per year (1972–2025). Best-fit line in log space; red = FDR-significant, grey = not. Note log y-axis.",
             ha="center", fontsize=9.5, color="#555")
    fig.text(0.5, 0.028, "Fire-season (May–Sep) mean temperature over burnable land (°C)", ha="center", fontsize=10)
    fig.text(0.015, 0.5, "Area burned (hectares, log scale)", rotation=90, va="center", fontsize=10)
    _foot(fig, "NBAC 1972–2025; ERA5-Land. Association only — temperature co-varies with drought/VPD.")
    fig.savefig(FIG/"3b_provincial_diagnostic.png"); plt.close(fig); print("wrote 3b_provincial_diagnostic.png")


# ---------- 4. map of 2023 fires ----------
def fig_map():
    import geopandas as gpd, json
    from shapely.geometry import Point
    from matplotlib.patches import Patch
    decade = gpd.read_file(PROC/"large_fires_2015_2024.gpkg")
    crs = decade.crs
    prov = gpd.read_file(ROOT/"data"/"boundaries"/"ne_admin1"/"ne_50m_admin_1_states_provinces.shp")
    ca = prov[prov.admin == "Canada"].to_crs(crs)
    # 2026 active fires (stage of control != OUT) from CIFFC year-to-date feed
    d = json.load(open(ROOT/"data"/"ciffc_ytd_fires_2026.json"))
    recs = [(p["field_longitude"], p["field_latitude"], p.get("field_fire_size") or 0)
            for f in d["features"] for p in [f["properties"]]
            if p.get("field_stage_of_control_status") not in ("OUT", None)
            and p.get("field_latitude") and p.get("field_longitude")]
    af = gpd.GeoDataFrame({"size_ha": [r[2] for r in recs]},
                          geometry=[Point(r[0], r[1]) for r in recs], crs="EPSG:4326").to_crs(crs)

    fig, ax = plt.subplots(figsize=(10.8, 7.8))
    fig.subplots_adjust(top=0.86, bottom=0.05, left=0.03, right=0.97)
    ca.plot(ax=ax, color="#f4f2ee", zorder=0)
    ca.boundary.plot(ax=ax, color="#b0aca4", lw=.5, zorder=1)
    decade.plot(ax=ax, color="#5b5750", edgecolor="none", alpha=.55, zorder=2)   # past-decade burned
    s = (5 + np.sqrt(af.size_ha.clip(lower=0))*0.7) * 0.25      # 0.25x: don't overstate vs historical footprint
    ax.scatter(af.geometry.x, af.geometry.y, s=s.clip(lower=1.5, upper=110), color=FIRE, alpha=.8,
               edgecolor="white", linewidth=.25, zorder=4)
    ax.set_axis_off()
    dtot = decade.SIZE_HA.sum()/1e6; atot = af.size_ha.sum()/1e6
    leg = [Patch(fc="#5b5750", alpha=.55, label=f"Burned 2015–2024 ({dtot:.0f} Mha)"),
           Line2D([],[],marker='o',ls='',mfc=FIRE,mec='white',ms=9,label=f"2026 active fire ({len(af)}; size ∝ area)")]
    ax.legend(handles=leg, loc="lower left", fontsize=9, framealpha=.92)
    _titles(fig, "A decade of fire — and what's burning now",
            "Large-fire footprints across the boreal, 2015–2024 (grey), with 2026's still-active fires (red) that are driving this summer's smoke.")
    _foot(fig, "Burned area: NRCan CNFDB large-fire polygons (≥200 ha). Active fires: CIFFC year-to-date feed, 'not out' as of 2026-07-17. Lambert Conformal Conic.")
    fig.savefig(FIG/"4_map_decade_active.png"); plt.close(fig); print("wrote 4_map_decade_active.png")


# ---------- 5. cause split ----------
def fig_cause():
    c = pd.read_csv(PROC/"area_burned_by_cause.csv")
    g = c.groupby("Cause").area_ha.sum().sort_values(ascending=False)/1e6
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.17, right=0.96)
    top = g.head(4)[::-1]
    ax.barh(top.index, top.values, color=[COOL if i!=len(top)-1 else FIRE for i in range(len(top))])
    for i,(k,v) in enumerate(top.items()):
        ax.text(v+0.7, i, f"{v:.0f} Mha ({100*v/g.sum():.0f}%)", va="center", fontsize=9.5)
    ax.set_xlim(0, g.max()*1.16)
    ax.set_xlabel("Cumulative area burned 1990–2023 (million hectares)")
    _titles(fig, "Lightning drives most of Canada's burned area",
            "Area burned by cause, 1990–2023. Lightning-ignited fires in remote boreal forest dominate — and rise with warming.")
    _foot(fig, "National Forestry Database (agency-reported).")
    fig.savefig(FIG/"5_cause_split.png"); plt.close(fig); print("wrote 5_cause_split.png")


# ---------- 6. fire-season warming map (per-gridcell LOWESS) ----------
def fig_warming_map():
    import geopandas as gpd
    from rasterio.features import rasterize
    from affine import Affine
    from statsmodels.nonparametric.smoothers_lowess import lowess
    RAS = ROOT/"data"/"era5_rasters"
    cache = PROC/"fire_season_warming_1959_2025.npz"
    g = np.load(RAS/"grid.npz"); lat, lon = g["lat"], g["lon"]
    if cache.exists():
        z = np.load(cache); change = z["change"]
    else:
        files = sorted(RAS.glob("clim_*.npz"))
        years = np.array([int(f.stem.split("_")[1]) for f in files])
        cube = np.stack([np.load(f)["arr"][0] for f in files])          # band 0 = fire_tmean_c
        ny, H, W = cube.shape
        change = np.full((H, W), np.nan, np.float32)
        valid = np.isfinite(cube).all(0)                                 # land cells with full record
        ij = np.argwhere(valid)
        xf = years.astype(float)
        for (i, j) in ij:
            sm = lowess(cube[:, i, j], xf, frac=0.6, return_sorted=False)
            change[i, j] = sm[-1] - sm[0]
        np.savez_compressed(cache, change=change)
        print(f"  computed LOWESS warming for {len(ij)} cells")
    # Canada mask + boundaries
    prov = gpd.read_file(ROOT/"data"/"boundaries"/"ne_admin1"/"ne_50m_admin_1_states_provinces.shp")
    ca = prov[prov.admin == "Canada"]
    dx = float(lon[1]-lon[0]); dy = float(lat[1]-lat[0])
    transform = Affine.translation(float(lon[0])-dx/2, float(lat[0])-dy/2) * Affine.scale(dx, dy)
    camask = rasterize([(geom, 1) for geom in ca.geometry], out_shape=change.shape,
                       transform=transform, fill=0, dtype="uint8").astype(bool)
    ch = np.where(camask, change, np.nan)

    fig, ax = plt.subplots(figsize=(11.0, 7.8))
    fig.subplots_adjust(top=0.83, bottom=0.06, left=0.03, right=0.99)
    vmax = 3.5
    im = ax.pcolormesh(lon, lat, ch, cmap="RdBu_r", vmin=-vmax, vmax=vmax, shading="auto")
    ca.boundary.plot(ax=ax, color="#444", lw=.5, zorder=3)
    ax.set_aspect(1/np.cos(np.deg2rad(float(np.nanmean(lat)))))
    ax.set_xlim(lon.min(), lon.max()); ax.set_ylim(lat.min(), lat.max()); ax.set_axis_off()
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.01, label="Change in fire-season mean temperature (°C)")
    natl = np.nanmean(ch)
    ax.text(0.02, 0.06, f"Canada-wide mean:\n+{natl:.1f} °C", transform=ax.transAxes,
            fontsize=11, fontweight="bold", color=FIRE, va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=FIRE, lw=1))
    _titles(fig, "Canada's fire seasons have warmed sharply",
            "Change in May–Sep mean temperature, 1959→2025 (per-gridcell LOWESS trend), ERA5-Land.", tsize=15.5)
    _foot(fig, "ERA5-Land (ECMWF/Copernicus via Google Earth Engine). Change = smoothed 2025 minus smoothed 1959. Record starts 1959 to avoid ERA5-Land's warm 1950s bias.")
    fig.savefig(FIG/"6_fire_season_warming_map.png"); plt.close(fig); print("wrote 6_fire_season_warming_map.png")


# ---------- 7. long-term / paleo context (honest: only real data plotted) ----------
def fig_longcontext():
    import matplotlib.gridspec as gridspec
    nat = pd.read_csv(PROC/"area_burned_national.csv")
    nb = nat[nat.total_ha_nbac.notna()]
    fig = plt.figure(figsize=(12.2, 6.6))
    fig.subplots_adjust(top=0.82, bottom=0.13, left=0.035, right=0.975, wspace=0.12)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.02, 1.25], figure=fig)

    # LEFT: cited paleo/historical context (text only — no fabricated proxy values)
    axl = fig.add_subplot(gs[0]); axl.axis("off")
    axl.text(0.0, 1.0, "Before the satellites: what the longer record says",
             fontsize=11.5, fontweight="bold", color=INK, va="top")
    blocks = [
        ("~10,000 years  (charcoal in lake sediments — a PROXY, not hectares)",
         "In parts of the North American boreal, recent burning RATES appear to exceed anything "
         "in the last ~10,000 years (Kelly et al. 2013, Alaska). Warm past intervals (e.g. the "
         "Medieval Climate Anomaly) also burned — so 'unprecedented' is a rate/regional claim."),
        ("~1900–1980  (fire suppression era)",
         "Active suppression held burned area BELOW what climate alone implied — a 20th-century "
         "'fire deficit' (Marlon et al. 2012). Part of the recent rise is a rebound from that "
         "artificially low baseline."),
        ("Regional heterogeneity",
         "Fire rose in the west/northwest but DECLINED in parts of the eastern boreal over recent "
         "centuries (Girardin, Ali, Bergeron et al.). There is no single national paleo-trend."),
    ]
    import textwrap
    y = 0.90
    for head, body in blocks:
        axl.text(0.0, y, textwrap.fill(head, 46), fontsize=9.2, fontweight="bold", color=FIRE, va="top")
        axl.text(0.0, y-0.085, textwrap.fill(body, 58), fontsize=8.6, color="#333", va="top", linespacing=1.35)
        y -= 0.30
    axl.set_xlim(0, 1); axl.set_ylim(0, 1)

    # RIGHT: the real MEASURED record
    axr = fig.add_subplot(gs[1])
    axr.bar(nb.year, nb.total_ha_nbac/1e6, color=FIRE, width=.85)
    v23 = float(nb[nb.year == 2023].total_ha_nbac.iloc[0])/1e6
    axr.annotate(f"2023\n{v23:.1f} Mha", xy=(2023, v23), xytext=(1998, v23-1.6),
                 fontsize=9, fontweight="bold", color=FIRE, ha="center",
                 arrowprops=dict(arrowstyle="->", color=FIRE))
    axr.set_xlabel("Year"); axr.set_ylabel("Area burned (Mha)")
    axr.set_title("The measured record (NBAC, 1972–2025)", fontsize=10, color=INK)
    axr.set_ylim(0, 16.5); axr.grid(alpha=.25)

    fig.suptitle("Is 2023 unprecedented?  The long view", y=0.965, fontsize=15.5, fontweight="bold", color=INK)
    fig.text(0.5, 0.90,
             "Yes in the 65-yr measured record and by any modern measure — but the deeper past is proxy-based, "
             "regionally mixed, and shaped by past suppression.",
             ha="center", fontsize=9.5, color="#555")
    _foot(fig, "Charcoal/paleofire is a proxy and is NOT directly comparable to modern mapped hectares. See literature/synthesis.md for citations.")
    fig.savefig(FIG/"7_long_context.png"); plt.close(fig); print("wrote 7_long_context.png")


if __name__ == "__main__":
    fig_hero(); fig_weather(); fig_weather(show_2026=True); fig_provincial(); fig_provincial_diagnostic()
    fig_map(); fig_cause(); fig_warming_map()
    print("\nAll figures ->", FIG)
