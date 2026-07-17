#!/usr/bin/env python3
"""
06_build_artifact.py — assemble a single self-contained, shareable HTML page
with all figures embedded as base64 (no external files). -> outputs/canada_wildfires.html
"""
import base64, pathlib, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG = ROOT/"outputs"/"figures"; TAB = ROOT/"outputs"/"tables"
OUT = ROOT/"outputs"/"canada_wildfires.html"

def b64(p):
    return "data:image/png;base64," + base64.b64encode(pathlib.Path(p).read_bytes()).decode()

# figures in narrative order: (file, headline, takeaway)
FIGS = [
    ("1_hero_area_burned.png", "The record",
     "Canada's forest area burned has surged. 2023 burned <b>14.8 million hectares</b> (satellite-mapped, NBAC) — the all-time record, about 2.3× the next-biggest year. 2026 is <b>not</b> a record-area year — its burning is running at or above the typical pace for mid-July, but far below 2023/2025. The air-quality crisis is a <b>smoke-transport</b> story, not a function of total hectares."),
    ("6_fire_season_warming_map.png", "The driver: warming",
     "Canadian fire seasons (May–Sep) have warmed <b>≈ +2.2 °C</b> since 1959 — over +3 °C across the high Arctic and ~2–2.5 °C through the boreal. Warmer air pulls moisture from live and dead fuels, priming the landscape to burn."),
    ("2_fire_season_weather.png", "Hot &amp; dry burns the most",
     "Plotting each year by its fire-season temperature and precipitation, the biggest fire years — 2023, 2025 (black-outlined) — sit deep in the <b>Hot &amp; Dry</b> corner, and the recent era (red) has shifted measurably warmer. Adapted from Robert Rohde's California version."),
    ("3_provincial_relationship.png", "Quantified, by region",
     "Nationally, area burned rises <b>≈ +80% per +1 °C</b> of fire-season warming (r = 0.61). The relationship holds up under detrending, year-to-year differencing, and controlling for precipitation — so it isn't just two things drifting up together. It's strongest in the western and northern boreal and weaker in the east."),
    ("5_cause_split.png", "Lightning drives it",
     "About <b>71%</b> of area burned (1990–2023) is lightning-ignited — remote boreal megafires that are hard to suppress. Warming is expected to increase high-latitude lightning."),
    ("4_map_decade_active.png", "A decade of fire — and what's burning now",
     "Grey shows where large fires burned across the boreal over 2015–2024 (~39 Mha); red dots are 2026's <b>878 still-active fires</b> (sized by area), concentrated in the Northwest Territories, Prairies, Ontario and Quebec. These — not a record total area — are what's driving this summer's smoke."),
]

KEY = [
    ("14.8 Mha", "burned in 2023 — the all-time record (~2.3× the prior peak)"),
    ("+2.2 °C", "fire-season warming across Canada since 1959"),
    ("+80% / °C", "more area burned per degree of fire-season warming (r = 0.61)"),
    ("71%", "of area burned is lightning-ignited"),
]

def main():
    cards = "".join(
        f'<div class="kv"><div class="kv-n">{n}</div><div class="kv-l">{l}</div></div>' for n,l in KEY)
    figs = "".join(
        f'<section class="fig"><h2>{i+1}. {h}</h2><img src="{b64(FIG/f)}" alt="{h}"><p>{t}</p></section>'
        for i,(f,h,t) in enumerate(FIGS))
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canada's Wildfires: Climate, Area Burned &amp; the 2026 Smoke Event</title>
<style>
  :root{{--fire:#c0392b;--ink:#1a1a1a;--mut:#666;--bg:#faf9f7;--card:#fff;}}
  *{{box-sizing:border-box}} html{{-webkit-text-size-adjust:100%}}
  body{{margin:0;background:var(--bg);color:var(--ink);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       line-height:1.55}}
  .wrap{{max-width:900px;margin:0 auto;padding:32px 20px 60px}}
  header h1{{font-size:2.0rem;line-height:1.15;margin:0 0 .3em}}
  .dek{{font-size:1.12rem;color:var(--mut);margin:0 0 1.2em}}
  .meta{{font-size:.8rem;color:var(--mut);border-top:1px solid #e5e2dc;border-bottom:1px solid #e5e2dc;
        padding:8px 0;margin-bottom:24px}}
  .lede{{font-size:1.05rem}}
  .lede b{{color:var(--fire)}}
  .keys{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:26px 0}}
  .kv{{background:var(--card);border:1px solid #eceae4;border-radius:12px;padding:16px}}
  .kv-n{{font-size:1.6rem;font-weight:800;color:var(--fire)}}
  .kv-l{{font-size:.85rem;color:var(--mut);margin-top:4px}}
  .fig{{background:var(--card);border:1px solid #eceae4;border-radius:14px;padding:20px;margin:22px 0;
       box-shadow:0 1px 3px rgba(0,0,0,.04)}}
  .fig h2{{font-size:1.25rem;margin:0 0 12px}}
  .fig img{{width:100%;height:auto;border-radius:8px;display:block}}
  .fig p{{color:#333;font-size:.98rem;margin:14px 0 0}}
  .note{{background:#fff6e5;border:1px solid #e6cf92;border-radius:12px;padding:16px 18px;margin:26px 0;
        font-size:.92rem}}
  footer{{font-size:.78rem;color:var(--mut);margin-top:34px;border-top:1px solid #e5e2dc;padding-top:16px}}
  a{{color:var(--fire)}}
</style></head><body><div class="wrap">
<header>
  <h1>Canada's Wildfires: Climate, Area Burned &amp; the 2026 Smoke Event</h1>
  <p class="dek">How the fires got bigger, what warming has to do with it, and why 2026's smoke is worse than its hectares.</p>
  <div class="meta">Analysis as of 16 July 2026 · Data: NRCan CNFDB/NBAC &amp; National Forestry Database · CIFFC (2026, preliminary) · ERA5-Land (ECMWF/Copernicus via Google Earth Engine)</div>
</header>
<p class="lede">In mid-July 2026, smoke from Canadian wildfires again choked cities across Canada and the northern U.S. — Toronto briefly had the <b>worst air quality of any major city on Earth</b>. Yet 2026 is <b>not</b> a record-area fire year — nationally it is running at roughly the typical pace for mid-July, far below 2023 or 2025. That is the key distinction this analysis makes: <b>area burned</b> is the climate-driven trend, while whether a given city chokes on smoke depends on where fires burn, how high the plumes rise, the winds, and who lives downwind. Below, the long-term record, the warming behind it, and the temperature&ndash;fire relationship &mdash; quantified and stress-tested.</p>
<div class="keys">{cards}</div>
{figs}
<div class="note"><b>How to read this honestly.</b> Temperature here is an <i>integrated indicator</i> of hot, dry fire weather (it co-varies with drought and vapor-pressure deficit), so the correlations are strong associations, not an isolated causal knob. Area-burned estimates differ by product: the satellite-mapped NBAC total for 2023 (14.8 Mha) is more conservative than the ~17–18 Mha agency/CIFFC figure. Statistics use the homogeneous 1972–2025 satellite record and never span data-source changes.</div>
<footer>
  Sources: NRCan Canadian National Fire Database &amp; National Burned Area Composite; National Forestry Database; CIFFC; ERA5-Land (ECMWF/Copernicus) via Google Earth Engine; World Weather Attribution (2023); Jones et al. 2024 (ESSD). Full citations and caveats in the accompanying literature synthesis.<br><br>
  Fire-season weather chart adapted from Robert A. Rohde / Berkeley Earth's "California Fire Season Weather." Built for public sharing; verify load-bearing figures before republication.
</footer>
</div></body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print("wrote", OUT, f"({OUT.stat().st_size/1e6:.1f} MB, self-contained)")

if __name__ == "__main__":
    main()
