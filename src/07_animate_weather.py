#!/usr/bin/env python3
"""
07_animate_weather.py — animated GIF of the Canada Fire Season Weather scatter.
Years appear cumulatively (1959->2025) so viewers watch the cloud drift toward Hot & Dry.
Tuned for a moderate, shareable file size (modest resolution + palette quantization).
Output: outputs/figures/2_fire_season_weather.gif
"""
import pathlib, io, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAB = ROOT/"outputs"/"tables"; PROC = ROOT/"data"/"processed"
FIG = ROOT/"outputs"/"figures"
FIRE = "#c0392b"; INK = "#222"
ERAS = [(1959,1971,"#000000","1959–71"),(1972,1984,"#1f78b4","1972–84"),
        (1985,1997,"#33a02c","1985–97"),(1998,2010,"#e6ab02","1998–2010"),
        (2011,2025,"#e31a1c","2011–25")]

def load():
    nat = pd.read_csv(TAB/"national_fire_season.csv")
    ab = pd.read_csv(PROC/"area_burned_national.csv")[["year","total_ha_nbac","total_ha_point"]]
    d = nat.merge(ab, on="year")
    d["area"] = d.total_ha_nbac.fillna(d.total_ha_point)
    return d[d.year.between(1959,2025)].dropna(subset=["tmean_c","precip_mm","area"]).sort_values("year").reset_index(drop=True)

def main():
    d = load()
    tmed, pmed = d.tmean_c.median(), d.precip_mm.median()
    smin, smax = d.area.min()/1e6, d.area.max()/1e6
    def msize(a): return 18 + 460*(a/1e6 - smin)/(smax - smin + 1e-9)   # smaller than static (smaller canvas)
    def col(y): return next(c for a,b,c,_ in ERAS if a<=y<=b)
    top10 = set(d.nlargest(10,"area").year)
    top3 = set(d.nlargest(3,"area").year)
    xlo,xhi = d.tmean_c.min()-0.3, d.tmean_c.max()+0.3
    ylo,yhi = d.precip_mm.min()-12, d.precip_mm.max()+12

    years = d.year.tolist()
    frames = []
    fig, ax = plt.subplots(figsize=(8.4, 6.7))
    fig.subplots_adjust(top=0.87, bottom=0.11, left=0.11, right=0.985)

    def draw(nyr):
        ax.clear()
        ax.set_xlim(xlo,xhi); ax.set_ylim(ylo,yhi)
        ax.grid(alpha=.25); ax.set_axisbelow(True)
        ax.axvline(tmed, color="#888", lw=1); ax.axhline(pmed, color="#888", lw=1)
        sub = d.iloc[:nyr]
        ax.scatter(sub.tmean_c, sub.precip_mm, s=[msize(a) for a in sub.area],
                   c=[col(y) for y in sub.year], alpha=.82,
                   edgecolor=["black" if y in top10 else "white" for y in sub.year],
                   linewidth=[1.3 if y in top10 else .5 for y in sub.year], zorder=3)
        # quadrant labels
        ax.text(xlo+.04*(xhi-xlo), yhi-.05*(yhi-ylo), "Cool & Wet", fontsize=9, color="#666", va="top")
        ax.text(xhi-.02*(xhi-xlo), yhi-.05*(yhi-ylo), "Hot & Wet", fontsize=9, color="#666", va="top", ha="right")
        ax.text(xlo+.04*(xhi-xlo), ylo+.03*(yhi-ylo), "Cool & Dry", fontsize=9, color="#666", va="bottom")
        ax.text(xhi-.02*(xhi-xlo), ylo+.03*(yhi-ylo), "Hot & Dry", fontsize=10.5, color=FIRE,
                va="bottom", ha="right", fontweight="bold")
        # running year counter
        cur = int(sub.year.iloc[-1]) if nyr>0 else years[0]
        ax.text(xlo+.03*(xhi-xlo), yhi-.13*(yhi-ylo), str(cur), fontsize=30, fontweight="bold",
                color="#ccc", va="top", zorder=1)
        # label each top-3 year AS ITS DOT APPEARS (and keep it thereafter)
        for _,r in sub[sub.year.isin(top3)].iterrows():
            dx = -12 if r.tmean_c>tmed else 12
            ax.annotate(f"{int(r.year)}", (r.tmean_c,r.precip_mm), textcoords="offset points",
                        xytext=(dx,0), ha="right" if dx<0 else "left", va="center",
                        fontsize=9.5, fontweight="bold", color="black", zorder=5)
        era_handles=[Line2D([],[],marker='o',ls='',mfc=c,mec='white',mew=.5,ms=8,label=l) for _,_,c,l in ERAS]
        era_handles.append(Line2D([],[],marker='o',ls='',mfc="#bbb",mec="black",mew=1.3,ms=8,label="10 largest yrs"))
        ax.legend(handles=era_handles, title="Era  (outline = top 10)", loc="upper right",
                  fontsize=7.5, framealpha=.9, title_fontsize=7.5)
        ax.set_xlabel("Fire-season (May–Sep) mean temperature over burnable land (°C)", fontsize=9)
        ax.set_ylabel("Fire-season total precipitation (mm)", fontsize=9)
        ax.tick_params(labelsize=8)
        fig.suptitle("Canada Fire Season Weather", y=0.965, fontsize=14, fontweight="bold", color=INK)
        fig.text(0.5, 0.905, "Each dot is a year. Hotter, drier seasons (bottom-right) burn the most — and recent years cluster there.",
                 ha="center", fontsize=8, color="#555")
        fig.text(0.011,0.012,"Marker size ∝ national area burned; black outline = 10 largest fire years. ERA5-Land + NRCan NBAC.",
                 fontsize=6, color="#999")
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()   # COPY: buffer is reused each draw
        return Image.fromarray(buf)                    # keep RGB; quantize later w/ shared palette

    # per-frame durations: half speed overall (190ms); half again (380ms) for the final decade;
    # 3-second pause on the final frame.
    durs = []
    for i in range(1, len(years)+1):
        frames.append(draw(i))
        y = years[i-1]
        durs.append(380 if y >= 2016 else 190)
    durs[-1] = 3000
    plt.close(fig)

    # ONE shared palette (from the fullest frame) -> clean GIF, small file, no palette-mismatch artifacts
    master = frames[-1].quantize(colors=128, method=Image.MEDIANCUT)
    pframes = [f.quantize(palette=master, dither=Image.NONE) for f in frames]

    out = FIG/"2_fire_season_weather.gif"
    pframes[0].save(out, save_all=True, append_images=pframes[1:], duration=durs,
                    loop=0, optimize=False, disposal=1)
    mb = out.stat().st_size/1e6
    print(f"wrote {out}  ({len(pframes)} frames, {mb:.1f} MB, {pframes[0].size})")

if __name__ == "__main__":
    main()
