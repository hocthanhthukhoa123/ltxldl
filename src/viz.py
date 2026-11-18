"""Vẽ 5 hình KPI + 1 hình đánh giá LLM vào figures/ (chỉ đọc kết quả có sẵn): python src/viz.py configs/cape_town.yaml"""
import sys
import textwrap

import matplotlib
import numpy as np
import pandas as pd
import yaml
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

from download import ROOT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

P, FIG = ROOT / "data" / "processed", ROOT / "figures"
BG, INK, INK2, GRID, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]  # A01..A08, cố định
SEQ = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
TIERS = ["#86b6ef", "#2a78d6", "#104281"]  # 3 nhóm doanh thu: xanh sáng -> tối
SENT = {"negative": "#e34948", "mixed": MUTED, "positive": SERIES[0]}
NAMES = {"llm": "LLM (Gemini)", "baseline": "VADER baseline", "floor": "Luôn đoán lớp phổ biến nhất"}
DASH = (0, (3, 2))
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "axes.edgecolor": MUTED, "axes.linewidth": 0.8,
    "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "xtick.color": INK2, "ytick.color": INK2,
    "font.size": 8.5, "legend.frameon": False, "lines.linewidth": 2, "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round"})


def kpi(name, level="analysis_area"):
    d = pd.read_csv(P / f"kpi_{name}.csv", dtype={"snapshot": str})
    return d[d["level"] == level].copy()


def k(v, _=None):  # 83,400 -> 83k; dưới 10,000 giữ nguyên
    return f"{v / 1000:,.0f}k" if abs(v) >= 10_000 else f"{v:,.0f}"


def note(ax, s, xy, dx, dy=0, **kw):  # chữ lệch (dx, dy) điểm ảnh so với xy
    ax.annotate(s, xy, xytext=(dx, dy), textcoords="offset points", **{"fontsize": 8, "color": INK2, **kw})


def fig1_hibernation_heatmap(cfg):
    piv = kpi("hibernation_rate").pivot(index="group", columns="snapshot", values="value").sort_index() * 100
    f, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(piv.values, cmap=SEQ, aspect="auto", vmin=0, vmax=np.ceil(piv.values.max() / 5) * 5)
    for (i, j), v in np.ndenumerate(piv.values):
        ax.text(j, i, f"{v:.1f}%", ha="center", va="center", fontsize=8.5, color="white" if v > 0.55 * im.get_clim()[1] else INK)
    r, c = piv.shape
    ax.set_xticks(range(c), piv.columns), ax.set_yticks(range(r), piv.index)
    ax.set_xticks(np.arange(c + 1) - 0.5, minor=True), ax.set_yticks(np.arange(r + 1) - 0.5, minor=True)
    ax.grid(False), ax.grid(which="minor", color=BG, linewidth=2), ax.tick_params(which="minor", length=0)  # khe 2px
    [s.set_visible(False) for s in ax.spines.values()]
    ax.set(xlabel="Mốc dữ liệu", ylabel="Vùng", title="KPI 1. Tỉ lệ listing \"ngủ đông\" theo vùng và mốc")
    cb = f.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label("Tỉ lệ ngủ đông (%)", color=INK2), cb.outline.set_visible(False)
    return f, ("Ngủ đông = estimated_occupancy_l365d bằng 0 đêm. Cột này Inside Airbnb ước tính từ số review, "
               "nên listing mới mở trong năm cũng bị tính là ngủ đông.")


def connected_dots(d, title, ylabel, cfg, caption):
    """Mỗi vùng một đường; mốc thiếu dữ liệu vẫn có vạch trên trục, đoạn nối qua nó vẽ nét đứt."""
    snaps = [str(s) for s in cfg["snapshots"]]
    have = [s for s in snaps if s in set(d["snapshot"])]
    miss = [s for s in snaps if s not in have]
    col = {g: SERIES[i % len(SERIES)] for i, g in enumerate(sorted(d["group"].unique()))}
    f, ax = plt.subplots(figsize=(8.6, 4.8))
    last = d[d["snapshot"] == have[-1]].set_index("group")["value"].sort_values(ascending=False)
    for g in last.index:  # thứ tự theo giá trị mốc cuối: chú giải khớp thứ tự đường
        r = d[d["group"] == g].set_index("snapshot")["value"].reindex(have)
        for a, b in zip(have, have[1:]):
            gap = snaps.index(b) - snaps.index(a) > 1
            ax.plot([snaps.index(a), snaps.index(b)], [r[a], r[b]], color=col[g], ls=DASH if gap else "-",
                    lw=1.6 if gap else 2, alpha=0.7 if gap else 1, zorder=2)
        ax.scatter([snaps.index(s) for s in have], r.values, s=40, color=col[g], edgecolor=BG, linewidth=1.5, zorder=3)
    ax.set_xticks(range(len(snaps)), [f"{s}\n(không có dữ liệu)" if s in miss else s for s in snaps])
    [t.set_color(MUTED) for t, s in zip(ax.get_xticklabels(), snaps) if s in miss]
    ax.grid(axis="x", visible=False), ax.yaxis.set_major_formatter(plt.FuncFormatter(k))
    ax.set(xlabel="Mốc dữ liệu", ylabel=ylabel, title=title)
    ax.legend(handles=[Line2D([], [], color=col[g], ls="-", marker="o", markeredgecolor=BG, label=f"{g}  {k(v)}")
                       for g, v in last.items()], title=f"Vùng (giá trị {have[-1]})", loc="upper left",
              bbox_to_anchor=(1.01, 1), fontsize=8, title_fontsize=8, alignment="left")
    return f, caption + (f" Mốc {', '.join(miss)} không có dữ liệu; nét đứt chỉ nối hai mốc có dữ liệu, "
                         "không phải giá trị mốc đó." if miss else "")


def fig2_median_price(cfg):
    d = kpi("median_price")
    return connected_dots(d[d["room_type"] == "all"], "KPI 2. Giá trung vị theo vùng (mọi loại phòng)",
                          f"Giá trung vị ({cfg['currency']}/đêm)", cfg, "Trung vị price khác rỗng. Mốc 03 là cuối mùa hè "
                          "ở Cape Town nên giá cao hơn; kpi_median_price.csv có thêm số liệu theo từng loại phòng.")


def fig3_median_revenue(cfg):
    return connected_dots(kpi("median_revenue"), "KPI 3. Doanh thu ước tính trung vị mỗi listing mỗi năm",
                          f"Doanh thu trung vị ({cfg['currency']}/năm)", cfg,
                          "Trung vị estimated_revenue_l365d (ước tính của Inside Airbnb), tính cả listing doanh thu 0.")


def fig4_net_sentiment(cfg):
    d, tot = kpi("net_sentiment").sort_values("value", ascending=False), kpi("net_sentiment", "all").iloc[0]["value"]
    area = pd.read_csv(P / "listings_clean.csv", dtype=str).drop_duplicates("id", keep="last").set_index("id")["analysis_area"]
    rv = pd.read_csv(P / "reviews_clean.csv", usecols=["id", "listing_id"], dtype=str)  # cùng phép nối như kpi.py
    z = pd.read_csv(P / "llm_results.csv", dtype=str).query("status == 'ok'").merge(rv, left_on="review_id", right_on="id")
    comp = pd.crosstab(z["listing_id"].map(area), z["sentiment"], normalize="index").reindex(d["group"]).fillna(0) * 100
    comp = comp.reindex(columns=list(SENT), fill_value=0)
    f, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.6), gridspec_kw={"width_ratios": [1.35, 1]}, sharey=True)
    y = np.arange(len(d))
    a1.hlines(y, d["ci_lo"], d["ci_hi"], color=SENT["positive"], lw=2.5, alpha=0.35)
    a1.scatter(d["value"], y, s=50, color=SENT["positive"], edgecolor=BG, linewidth=1.5, zorder=3)
    for i, (v, n, hi) in enumerate(zip(d["value"], d["n"], d["ci_hi"])):
        note(a1, f"{v:.2f}  n={n}", (hi, i), 6, va="center")
    a1.axvline(tot, color=INK2, lw=1, ls=DASH)
    a1.set_yticks(y, d["group"]), a1.set_ylim(len(d) - 0.5, -1.1)  # hàng trống phía trên cho nhãn toàn mẫu
    note(a1, f"toàn mẫu {tot:.2f}", (tot, -0.8), 4, va="center"), a1.grid(axis="y", visible=False)
    a1.set(xlim=(min(0.6, d["ci_lo"].min() - 0.03), 1.1), xlabel="Cảm xúc ròng (−1 đến 1), trục đã phóng to",
           title="KPI 4. Cảm xúc ròng theo vùng, khoảng tin cậy 95%")
    left = np.zeros(len(d))
    for lab, c in SENT.items():  # viền màu nền = khe 2px giữa các đoạn
        a2.barh(y, comp[lab].to_numpy(), left=left, height=0.55, color=c, edgecolor=BG, linewidth=2, label=lab)
        left = left + comp[lab].to_numpy()
    for i, v in enumerate(comp["negative"]):
        note(a2, f"{v:.0f}% neg", (100, i), 4, va="center")
    a2.set(xlim=(0, 112), xticks=range(0, 101, 20), xlabel="Tỉ lệ review (%)", title="Thành phần nhãn LLM")
    a2.grid(axis="y", visible=False), a2.legend(loc="upper center", bbox_to_anchor=(0.45, -0.14), ncols=3)
    return f, ("positive = +1, mixed = 0, negative = −1; trung bình trên review LLM gán nhãn thành công. Thanh ngang = "
               f"khoảng tin cậy 95% (bootstrap {cfg['eval']['bootstrap']} lần, lấy mẫu lại theo listing).\n"
               "Các khoảng chồng nhau nhiều: mẫu chưa đủ để xếp hạng chắc chắn mọi vùng.")


def revenue_tiers(t):
    """D = (Tmax - Tmin)/3; nhóm 1: T < Tmin + D; nhóm 2: Tmin + D <= T <= Tmax - D; nhóm 3: T > Tmax - D."""
    d = (t.max() - t.min()) / 3
    c1, c2 = t.min() + d, t.max() - d
    return np.where(t < c1, 0, np.where(t <= c2, 1, 2)), c1, c2


def fig5_occupied_nights_bubble(cfg):
    last, pr = str(cfg["snapshots"][-1]), kpi("median_price")
    m = pd.DataFrame({c: d[d["snapshot"] == last].set_index("group")["value"] for c, d in
                      (("nights", kpi("median_occupied_nights")), ("price", pr[pr["room_type"] == "all"]),
                       ("rev", kpi("median_revenue")))}).dropna()
    tier, c1, c2 = revenue_tiers(m["rev"])
    L = pd.read_csv(P / "listings_clean.csv", dtype={"snapshot": str}).query("snapshot == @last")
    ref_x = L.loc[L["estimated_occupancy_l365d"] > 0, "estimated_occupancy_l365d"].median()  # trung vị toàn mẫu
    ref_y = L["price"].median()
    f, ax = plt.subplots(figsize=(8.6, 5.6))
    size = 2600 * m["rev"] / m["rev"].max()  # diện tích bóng tỉ lệ với doanh thu
    ax.scatter(m["nights"], m["price"], s=size, c=[TIERS[t] for t in tier], alpha=0.85, edgecolor=BG, linewidth=2, zorder=3)
    for (g, r), s in zip(m.iterrows(), size):
        rad = np.sqrt(s / np.pi)  # bán kính (điểm ảnh): nhãn sát mép bóng
        note(ax, g, (r["nights"], r["price"]), rad + 3, 4, fontsize=9, fontweight="bold", color=INK, va="bottom")
        note(ax, f"{k(r['rev'])}/năm", (r["nights"], r["price"]), rad + 3, -2, va="top")
    ax.axvline(ref_x, color=INK2, lw=1, ls=DASH, zorder=1), ax.axhline(ref_y, color=INK2, lw=1, ls=DASH, zorder=1)
    ax.set(xlim=(20, max(105, m["nights"].max() + 15)),
           ylim=(min(900, m["price"].min() - 250), max(3200, m["price"].max() + 300)))
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    for x, y, s in ((x0, y1, "Giá cao, ít đêm"), (x1, y1, "Giá cao, nhiều đêm"), (x0, y0, "Giá thấp, ít đêm"),
                    (x1, y0, "Giá thấp, nhiều đêm")):
        note(ax, s, (x, y), 6 if x == x0 else -6, -6 if y == y1 else 6, ha="left" if x == x0 else "right",
             va="top" if y == y1 else "bottom", color=MUTED)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(k)), ax.set(xlabel="Số đêm có khách trung vị (đêm/năm, listing đang hoạt động)", ylabel=f"Giá trung vị ({cfg['currency']}/đêm)",
           title=f"KPI 5. Số đêm có khách, giá và doanh thu theo vùng, mốc {last}")
    names = [f"Doanh thu < {k(c1)}/năm", f"Doanh thu {k(c1)} – {k(c2)}/năm", f"Doanh thu > {k(c2)}/năm"]
    ax.legend(handles=[Line2D([], [], ls="", marker="o", markersize=9, color=c, label=n) for c, n in zip(TIERS, names)],
              loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=3, fontsize=8, handletextpad=0.3)
    return f, (f"Kích thước bóng tỉ lệ với doanh thu trung vị. Nhóm màu: D = (Tmax − Tmin)/3, T = doanh thu trung vị của vùng; "
               f"nhóm 1: T < Tmin + D ({k(c1)}); nhóm 2: Tmin + D ≤ T ≤ Tmax − D ({k(c2)}); nhóm 3: T > Tmax − D.\n"
               f"Đường nét đứt: trung vị toàn mẫu ({ref_x:.0f} đêm; {ref_y:,.0f} {cfg['currency']}/đêm, mọi loại phòng).")


def fig6_llm_vs_baseline(cfg):
    raw = pd.read_csv(P / "eval_metrics.csv").query("group == 'all'")
    e = raw[raw["method"].isin(NAMES)].pivot(index="method", columns="metric", values="value").loc[list(NAMES)]
    n = int(raw.loc[raw["metric"] == "accuracy", "n"].max())
    f, ax = plt.subplots(figsize=(7.4, 3.8))
    for j, (key, c) in enumerate(zip(("accuracy", "macro_f1"), SERIES)):
        y = np.arange(len(NAMES)) + (-0.17 if j == 0 else 0.17)
        ax.hlines(y, e[f"{key}_ci_lo"], e[f"{key}_ci_hi"], color=c, lw=2.5, alpha=0.4)
        ax.scatter(e[key], y, s=46, color=c, edgecolor=BG, linewidth=1.5, zorder=3, label=key.replace("_", "-"))
        for yy, vv in zip(y, e[key]):
            note(ax, f"{vv:.2f}", (vv, yy), 0, 6, ha="center", color=INK)
    ax.set_yticks(range(len(NAMES)), list(NAMES.values())), ax.invert_yaxis(), ax.grid(axis="y", visible=False)
    ax.set(xlim=(0, 1.02), xlabel="Điểm trên nhãn tay (chấm = ước lượng, vạch = khoảng tin cậy 95% bootstrap)",
           title=f"Gán nhãn cảm xúc so với {n} nhãn tay")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=2)
    return f, "Nhãn tay 97% positive nên macro-F1 chỉ dựa vào 3 review không phải positive; khoảng tin cậy rất rộng."


FIGS = (fig1_hibernation_heatmap, fig2_median_price, fig3_median_revenue, fig4_net_sentiment,
        fig5_occupied_nights_bubble, fig6_llm_vs_baseline)


def main(config_path):
    with open(config_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    FIG.mkdir(exist_ok=True)
    [p.unlink() for p in FIG.glob("fig*.png") if p.stem not in {fn.__name__ for fn in FIGS}]  # bỏ hình cũ không còn sinh ra
    s = cfg["snapshots"]
    src = f"Nguồn: Inside Airbnb (CC BY 4.0), Cape Town, mốc {s[0]} đến {s[-1]}; mẫu 1000 listing của nhóm {cfg['group_code']}."
    for fn in FIGS:
        f, caption = fn(cfg)
        text = "\n".join(textwrap.fill(t, int(f.get_figwidth() * 19)) for t in f"{caption}\n{src}".split("\n"))
        f.text(0.01, 0.01, text, fontsize=6.8, va="bottom", color=INK2)
        f.tight_layout(rect=(0, ((text.count("\n") + 1) * 0.135 + 0.05) / f.get_figheight(), 1, 1))
        f.savefig(FIG / f"{fn.__name__}.png", dpi=200), plt.close(f), print(f"[ok]   figures/{fn.__name__}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "configs/cape_town.yaml"))
