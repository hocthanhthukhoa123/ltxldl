"""Vẽ hình cho báo cáo từ kpi_*.csv, eval_*.csv và listings_clean.csv: python src/viz.py configs/cape_town.yaml
Chỉ đọc kết quả có sẵn (không tính lại KPI). Ra: figures/fig1_*.png ... fig8_*.png (matplotlib, backend Agg).
Màu: bảng màu tham chiếu đã kiểm tra mù màu (3 mốc dùng 3 màu đầu; độ lớn dùng một dải xanh sáng -> tối)."""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from download import ROOT  # noqa: E402
from qa import load_refs  # noqa: E402

P, FIG = ROOT / "data" / "processed", ROOT / "figures"
SURFACE, INK, INK2, GRID, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # 3 mốc: xanh, cam, xanh ngọc (đạt kiểm tra CVD cho mọi cặp)
BLUE = SERIES[0]
SEQ = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
NAMES = {"llm": "LLM (Gemini)", "baseline": "VADER baseline", "floor": "Majority class"}
CLASSES = ["positive", "mixed", "negative"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.8, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "xtick.color": INK2, "ytick.color": INK2, "font.size": 8.5,
    "legend.frameon": False, "lines.linewidth": 2, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
})


def kpi(name, level="analysis_area"):
    d = pd.read_csv(P / f"kpi_{name}.csv", dtype={"snapshot": str})
    return d[d["level"] == level].copy()


def money(v, _=None):
    return f"{v / 1000:,.0f}K" if abs(v) >= 10_000 else f"{v:,.0f}"


def dot_plot(ax, d, xlabel, fmt=money):
    """Mỗi vùng một hàng, mỗi mốc một chấm (màu theo mốc, cố định) nối bằng vạch xám: thấy cả mức lẫn thay đổi."""
    snaps = sorted(d["snapshot"].unique())
    order = d[d["snapshot"] == snaps[-1]].sort_values("value")["group"].tolist()
    order += sorted(set(d["group"]) - set(order))
    y = {g: i for i, g in enumerate(order)}
    for g, r in d.groupby("group"):
        ax.plot([r["value"].min(), r["value"].max()], [y[g]] * 2, color=GRID, lw=3, zorder=1)
    dodge = 0.16  # lệch dọc theo mốc + hình dấu khác nhau: hai mốc gần bằng nhau không che nhau
    for k, (s, c, mk) in enumerate(zip(snaps, SERIES, "osD")):
        r = d[d["snapshot"] == s]
        ax.scatter(r["value"], r["group"].map(y) + (k - (len(snaps) - 1) / 2) * dodge, s=42, marker=mk, color=c,
                   edgecolor=SURFACE, linewidth=1.5, zorder=3, label=s)
    ax.set_yticks(range(len(order)), order)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt))
    ax.set_xlabel(xlabel)
    ax.legend(title="Snapshot", loc="lower right", fontsize=7.5, title_fontsize=7.5, handletextpad=0.2)


def fig1_price_map(cfg):
    last = str(cfg["snapshots"][-1])
    L = pd.read_csv(P / "listings_clean.csv", dtype={"snapshot": str})
    L = L[L["snapshot"] == last].dropna(subset=["latitude", "longitude", "price"])
    A = load_refs(cfg)["area"].set_index("analysis_area")[["lon_min", "lat_min", "lon_max", "lat_max"]].astype(float)
    f, ax = plt.subplots(figsize=(7.2, 6.2))
    sc = ax.scatter(L["longitude"], L["latitude"], c=L["price"], cmap=SEQ, s=12, edgecolor=SURFACE, linewidth=0.4,
                    vmin=0, vmax=L["price"].quantile(0.95))
    for a, r in A.iterrows():
        ax.add_patch(Rectangle((r.lon_min, r.lat_min), r.lon_max - r.lon_min, r.lat_max - r.lat_min,
                               fill=False, ec=MUTED, lw=0.8))
    placed = []  # nhãn ở trung vị toạ độ listing; vùng nằm sát nhau thì đẩy nhãn ra và nối bằng đường dẫn mảnh
    for a, g in L.groupby("analysis_area"):
        x, y = g["longitude"].median(), g["latitude"].median()
        tx, ty, k = x, y, 0
        while any(abs(tx - px) < 0.05 and abs(ty - py) < 0.025 for px, py in placed):
            k += 1
            tx, ty = x - 0.07, y + 0.035 * (k if k % 2 else -k)
        placed.append((tx, ty))
        ax.annotate(a, (x, y), xytext=(tx, ty), fontsize=8, fontweight="bold", color=INK, ha="center", va="center",
                    path_effects=[pe.withStroke(linewidth=3, foreground=SURFACE)],
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.7, shrinkA=6, shrinkB=2) if k else None)
    ax.set_aspect(1 / np.cos(np.radians(L["latitude"].mean())))
    ax.grid(False)
    ax.set_xlabel("Longitude"), ax.set_ylabel("Latitude")
    ax.set_title(f"Nightly price by listing, snapshot {last} (n={len(L)})")
    cb = f.colorbar(sc, ax=ax, shrink=0.75, extend="max")
    cb.set_label(f"Price ({cfg['currency']}/night), capped at 95th percentile", color=INK2)
    cb.outline.set_visible(False)
    return f, "Where are the expensive listings? Labels sit at the median listing location of each area; grey boxes are the assigned area bounds."


def fig2_price_by_area(cfg):
    d = kpi("median_price")
    room = d.groupby("room_type")["n"].sum().idxmax()
    f, ax = plt.subplots(figsize=(7, 4.4))
    dot_plot(ax, d[d["room_type"] == room], f"Median nightly price ({cfg['currency']})")
    ax.set_title(f"Median price by area, {room}")
    return f, "Which areas are priciest? Price is missing for every listing in the 2025-12-29 snapshot, so it is excluded."


def fig3_revenue_by_area(cfg):
    f, ax = plt.subplots(figsize=(7, 4.4))
    dot_plot(ax, kpi("median_revenue"), f"Median estimated revenue, last 365 days ({cfg['currency']})")
    ax.set_title("Median estimated revenue per listing by area")
    return f, "Which areas earn most? estimated_revenue_l365d from Inside Airbnb (a model estimate); listings with 0 revenue included."


def small_multiples(d, ylabel, fmt):
    """Một ô mỗi vùng: đường của vùng (xanh) trên nền các vùng khác (xám) - tránh 8 đường chồng nhau."""
    piv = d.pivot(index="snapshot", columns="group", values="value").sort_index()
    areas, x = list(piv.columns), range(len(piv))
    f, axs = plt.subplots(2, (len(areas) + 1) // 2, figsize=(9, 4.6), sharex=True, sharey=True)
    for ax, a in zip(axs.flat, areas):
        for o in areas:
            if o != a:
                ax.plot(x, piv[o], color=GRID, lw=1.2, zorder=1)
        ax.plot(x, piv[a], color=BLUE, zorder=3)
        ax.scatter(x, piv[a], s=26, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=4)
        ax.annotate(fmt(piv[a].iloc[-1]), (x[-1], piv[a].iloc[-1]), xytext=(4, 6), textcoords="offset points",
                    fontsize=7.5, color=INK, ha="right")
        ax.set_title(a, fontsize=9)
        ax.set_xticks(list(x), [s[2:7] for s in piv.index], fontsize=7)
        ax.grid(axis="x", visible=False)
    for ax in axs.flat[len(areas):]:
        ax.set_visible(False)
    f.supylabel(ylabel, fontsize=8.5, color=INK2)
    return f


def fig4_hibernation(cfg):
    f = small_multiples(kpi("hibernation_rate").assign(value=lambda d: d["value"] * 100), "Hibernating listings (%)",
                        lambda v: f"{v:.0f}%")
    f.suptitle("Hibernation rate by area (estimated occupancy = 0 nights in last 365 days)", x=0.01, ha="left",
               fontsize=10, fontweight="bold", color=INK)
    return f, "Which areas have idle listings? Occupancy is estimated from reviews, so listings opened in the last year also count as 0."


def fig5_occupied_nights(cfg):
    f = small_multiples(kpi("median_occupied_nights"), "Median occupied nights", lambda v: f"{v:.0f}")
    f.suptitle("Median occupied nights per active listing (last 365 days)", x=0.01, ha="left",
               fontsize=10, fontweight="bold", color=INK)
    return f, "How busy are active listings? Median of estimated_occupancy_l365d over listings with occupancy > 0."


def fig6_net_sentiment(cfg):
    d = kpi("net_sentiment").sort_values("value")
    f, ax = plt.subplots(figsize=(7, 4.2))
    y = range(len(d))
    ax.hlines(y, d["ci_lo"], d["ci_hi"], color=BLUE, lw=2, alpha=0.35)
    ax.scatter(d["value"], y, s=46, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for i, (v, n) in enumerate(zip(d["value"], d["n"])):
        ax.annotate(f"{v:.2f}  (n={n})", (d["ci_hi"].iloc[i], i), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(list(y), d["group"])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(min(0.5, d["ci_lo"].min() - 0.05), 1.12)
    ax.set_xlabel("Net sentiment (+1 positive, 0 mixed, -1 negative)")
    ax.set_title("Net sentiment of guest reviews by area, LLM sample (95% CI)")
    return f, "Where are guests happiest? CI from a bootstrap that resamples listings; overlapping intervals are not clear differences."


def fig7_llm_vs_baseline(cfg):
    e = pd.read_csv(P / "eval_metrics.csv")
    e = e[(e["group"] == "all") & e["method"].isin(NAMES)].pivot(index="method", columns="metric", values="value")
    n = int(pd.read_csv(P / "eval_metrics.csv").query("group == 'all' and metric == 'accuracy'")["n"].max())
    f, ax = plt.subplots(figsize=(7, 3.6))
    order = list(NAMES)
    for j, (k, c) in enumerate(zip(("accuracy", "macro_f1"), SERIES)):
        y = np.arange(len(order)) + (0.17 if j == 0 else -0.17)
        v = e.loc[order, k]
        ax.hlines(y, e.loc[order, f"{k}_ci_lo"], e.loc[order, f"{k}_ci_hi"], color=c, lw=2, alpha=0.4)
        ax.scatter(v, y, s=46, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3, label=k.replace("_", "-"))
        for yy, vv in zip(y, v):
            ax.annotate(f"{vv:.2f}", (vv, yy), xytext=(0, 6), textcoords="offset points", ha="center",
                        fontsize=7.5, color=INK)
    ax.set_yticks(range(len(order)), [NAMES[m] for m in order])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Score on hand labels (dot = estimate, line = 95% bootstrap CI)")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=2)
    ax.set_title(f"Sentiment labelling vs {n} hand labels")
    return f, "Is the LLM better than simple baselines? Hand labels are 97% positive, so macro-F1 rests on 3 non-positive reviews."


def fig8_confusion(cfg):
    C = pd.read_csv(P / "eval_confusion.csv")
    ms = ["llm", "baseline"]
    f, axs = plt.subplots(1, 2, figsize=(8, 3.6))
    for ax, m in zip(axs, ms):
        t = C[C["method"] == m].pivot_table(index="label", columns="pred", values="count", aggfunc="sum", fill_value=0)
        cols = CLASSES + (["none"] if "none" in t.columns else [])
        t = t.reindex(index=CLASSES, columns=cols, fill_value=0)
        ax.imshow(np.log1p(t.values), cmap=SEQ, vmin=0, vmax=np.log1p(t.values.max()))
        for (i, j), v in np.ndenumerate(t.values):
            ax.text(j, i, int(v), ha="center", va="center", fontsize=9,
                    color="white" if np.log1p(v) > 0.6 * np.log1p(t.values.max()) else INK)
        ax.set_xticks(range(len(cols)), cols), ax.set_yticks(range(3), CLASSES)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel("Prediction"), ax.set_ylabel("Hand label"), ax.set_title(NAMES[m])
    return f, "Where does each method go wrong? Rows = hand label. Colour is log-scaled so small cells stay visible."


def main(config_path):
    with open(config_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    FIG.mkdir(exist_ok=True)
    s = cfg["snapshots"]
    src = f"Source: Inside Airbnb (CC BY 4.0), {cfg['city'].replace('_', ' ').title()}, snapshots {s[0]} to {s[-1]}; group sample."
    for fn in (fig1_price_map, fig2_price_by_area, fig3_revenue_by_area, fig4_hibernation, fig5_occupied_nights,
               fig6_net_sentiment, fig7_llm_vs_baseline, fig8_confusion):
        f, caption = fn(cfg)
        f.text(0.01, 0.01, f"{caption}\n{src}", fontsize=6.5, va="bottom", color=INK2)
        f.tight_layout(rect=(0, 0.07, 1, 1))
        f.savefig(FIG / f"{fn.__name__}.png", dpi=200)
        plt.close(f)
        print(f"[ok]   figures/{fn.__name__}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "configs/cape_town.yaml"))
