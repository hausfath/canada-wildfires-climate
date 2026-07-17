#!/usr/bin/env python3
"""
01_fetch_fire_data.py — Assemble Canadian area-burned records.

Primary source: CNFDB (NFDB) point summary stats workbook, which provides a
single-methodology national + per-agency series 1959-2025, including the more
spatially accurate NBAC (National Burned Area Composite, 1972-2025) "ADJUSTED HA".

Outputs (data/processed/):
  area_burned_national.csv    year, total_ha_point(1959-2025), total_ha_nbac(1972-2025),
                              fires, source  [+ 2026 partial from CIFFC]
  area_burned_provincial.csv  year, agency, jurisdiction, total_ha_point, total_ha_nbac, fires
                              (13 provinces/territories; excludes CANADA total & Parks Canada)
  area_burned_by_cause.csv    NFD agency by-cause 1990-2023 (lightning vs human split)

Provenance notes:
- 2023 area burned differs by product: NBAC ~14.8 Mha, NFD agency ~17.2 Mha,
  NFDB-point ~17.6 Mha. NBAC is the spatially-accurate standard; agency/point run higher.
- 2026 is a PARTIAL, PRELIMINARY reported total (CIFFC, as of 2026-07-17), flagged separately.
"""
import pandas as pd, numpy as np, pathlib

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "processed"; OUT.mkdir(parents=True, exist_ok=True)
XLSX = DATA / "NFDB_point_stats.xlsx"

PROV_NAMES = {  # agency code -> full name
    "AB":"Alberta","BC":"British Columbia","MB":"Manitoba","NB":"New Brunswick",
    "NL":"Newfoundland and Labrador","NS":"Nova Scotia","NT":"Northwest Territories",
    "NU":"Nunavut","ON":"Ontario","PEI":"Prince Edward Island","QC":"Quebec",
    "SK":"Saskatchewan","YT":"Yukon","PC":"Parks Canada","CANADA":"Canada",
}

# CIFFC-reported 2026 partial totals as of 2026-07-17 (CIFFC year-to-date WFS feed).
# PRELIMINARY — reported agency totals run high and are revised down later.
CIFFC_2026 = {"year":2026, "total_ha_point":2_752_000, "total_ha_nbac":np.nan,
              "fires":3586, "source":"CIFFC preliminary (2026-07-17, partial season)"}


def parse_national():
    raw = pd.read_excel(XLSX, sheet_name="NFDB_Summary_Stats", header=None)
    def isyear(x):
        try: return 1900 < int(float(x)) < 2100
        except: return False
    hdr = next(i for i in range(10) if isyear(raw.iloc[i, 0]))
    d = raw.iloc[hdr:].copy()
    d = d[d.iloc[:, 0].apply(isyear)]
    nat = pd.DataFrame({
        "year": d.iloc[:, 0].astype(float).astype(int),
        "fires": pd.to_numeric(d.iloc[:, 1], errors="coerce"),
        "total_ha_point": pd.to_numeric(d.iloc[:, 2], errors="coerce"),
        "total_ha_nbac": pd.to_numeric(d.iloc[:, 6], errors="coerce"),
    })
    nat["source"] = "NFDB point summary stats (CNFDB)"
    nat = nat.sort_values("year").reset_index(drop=True)
    # append 2026 partial
    nat = pd.concat([nat, pd.DataFrame([CIFFC_2026])], ignore_index=True).sort_values("year")
    return nat.reset_index(drop=True)


def parse_provincial():
    raw = pd.read_excel(XLSX, sheet_name="NFDB_Summary_Stats_By_Agency", header=None)
    agencies = raw.iloc[2].ffill()
    subcols = raw.iloc[4]
    data = raw.iloc[5:].reset_index(drop=True)
    year = pd.to_numeric(data.iloc[:, 0], errors="coerce")
    recs = []
    for ag in pd.unique(agencies.dropna()):
        ag = str(ag).strip()
        if ag in ("nan", "CANADA", "PC"):   # exclude national total & Parks Canada from provincial
            continue
        cols = {str(subcols[j]).strip(): j for j in range(raw.shape[1])
                if str(agencies[j]).strip() == ag}
        def col(name):
            j = cols.get(name)
            return pd.to_numeric(data.iloc[:, j], errors="coerce") if j is not None else np.nan
        recs.append(pd.DataFrame({
            "year": year, "agency": ag, "jurisdiction": PROV_NAMES.get(ag, ag),
            "total_ha_point": col("TOTAL_HA"), "total_ha_nbac": col("ADJUSTED HA"),
            "fires": col("FIRES"),
        }))
    prov = pd.concat(recs).dropna(subset=["year"])
    prov["year"] = prov["year"].astype(int)
    return prov.sort_values(["agency", "year"]).reset_index(drop=True)


def parse_by_cause():
    df = pd.read_csv(DATA / "nfd_area_burned_by_cause.csv", encoding="latin-1")
    df = df.rename(columns={"Area (hectares)": "area_ha", "Jurisdiction": "jurisdiction"})
    keep = df[["Year", "jurisdiction", "Cause", "area_ha"]].rename(columns={"Year": "year"})
    return keep


def main():
    nat = parse_national()
    prov = parse_provincial()
    cause = parse_by_cause()

    nat.to_csv(OUT / "area_burned_national.csv", index=False)
    prov.to_csv(OUT / "area_burned_provincial.csv", index=False)
    cause.to_csv(OUT / "area_burned_by_cause.csv", index=False)

    # ---- verification ----
    print("=== NATIONAL ===")
    print("years:", nat.year.min(), "-", nat.year.max())
    show = nat[nat.year.isin([1959, 1980, 1989, 1995, 2020, 2023, 2024, 2025, 2026])]
    for _, r in show.iterrows():
        p = r.total_ha_point/1e6; n = r.total_ha_nbac/1e6
        print(f"  {int(r.year)}: point={p:5.2f} Mha  nbac={n:5.2f} Mha  fires={r.fires:.0f}")
    print("  top-5 point years:", [(int(y), round(v/1e6,1)) for y,v in
          nat.nlargest(5,'total_ha_point')[['year','total_ha_point']].itertuples(index=False)])

    print("\n=== PROVINCIAL (NBAC where available) ===")
    print("agencies:", sorted(prov.agency.unique()), "| years:", prov.year.min(), "-", prov.year.max())
    # cross-check: sum of provinces vs national (2023), expect provinces < national (PC excluded)
    for y in [2023, 2025]:
        ps = prov[prov.year==y].total_ha_point.sum()/1e6
        ns = nat.loc[nat.year==y,"total_ha_point"].iloc[0]/1e6
        print(f"  {y}: sum(provinces)={ps:.2f} Mha  national={ns:.2f} Mha  (diff = PC + rounding = {ns-ps:.2f})")
    # informative-year screen for regression fitness (nonzero NBAC years, 1972+)
    print("\n  nonzero-NBAC-year counts (regression fitness, 1972-2025):")
    nb = prov[(prov.year>=1972)].copy()
    cnt = nb.assign(nz=nb.total_ha_nbac.fillna(0)>0).groupby("jurisdiction").nz.sum().sort_values()
    for j,c in cnt.items(): print(f"    {j:28s} {int(c):2d} nonzero yrs")

    print("\n=== BY CAUSE (1990-2023) ===  national lightning vs human share:")
    c = cause.groupby("Cause").area_ha.sum().sort_values(ascending=False)
    tot = c.sum()
    for k,v in c.items(): print(f"  {k:16s} {v/1e6:7.2f} Mha  ({100*v/tot:4.1f}%)")
    print("\nWrote:", *[str(p.name) for p in OUT.glob('area_burned_*.csv')])


if __name__ == "__main__":
    main()
