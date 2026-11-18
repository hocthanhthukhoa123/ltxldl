"""Vẽ hình cho báo cáo theo dạng biểu đồ nhóm đã chọn: python src/viz.py configs/cape_town.yaml
Chỉ đọc kết quả có sẵn (kpi_*.csv, eval_metrics.csv, llm_results.csv, reviews_clean.csv, listings_clean.csv), không tính lại KPI.
Ra: figures/
  fig1_hibernation_heatmap.png   KPI 1  tỉ lệ ngủ đông: heatmap vùng x mốc
  fig2_median_price.png          KPI 2  giá trung vị (mọi loại phòng): biểu đồ chấm nối theo mốc
  fig3_median_revenue.png        KPI 3  doanh thu ước tính mỗi listing mỗi năm: biểu đồ chấm nối theo mốc
  fig4_net_sentiment.png         KPI 4  cảm xúc ròng (LLM): chấm + khoảng tin cậy 95%, kèm thành phần nhãn
  fig5_occupied_nights_bubble.png KPI 5 số đêm có khách trung vị x giá trung vị, bóng = doanh thu (mốc mới nhất)
  fig6_llm_vs_baseline.png       đánh giá LLM, VADER và mức sàn trên nhãn tay
Màu: bảng màu tham chiếu đã kiểm tra mù màu; nền sáng để in báo cáo."""
import sys
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from download import ROOT  # noqa: E402

P, FIG = ROOT / "data" / "processed", ROOT / "figures"
SURFACE, INK, INK2, GRID, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]  # A01..A08, thứ tự cố định
SEQ = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
TIERS = ["#86b6ef", "#2a78d6", "#104281"]  # 3 nhóm doanh thu: một dải xanh sáng -> tối (thứ bậc, không phải danh mục)
POS, MIX, NEG = "#2a78d6", "#b9b8b2", "#e34948"  # cảm xúc: xanh / xám trung tính / đỏ
NAMES = {"llm": "LLM (Gemini)", "baseline": "VADER baseline", "floor": "Luôn đoán lớp phổ biến nhất"}
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


def k(v, _=None):
    """Số tiền gọn: 83,400 -> 83k; dưới 10,000 giữ nguyên có dấu phẩy."""
    return f"{v / 1000:,.0f}k" if abs(v) >= 10_000 else f"{v:,.0f}"


def colors(groups):
    return {g: SERIES[i % len(SERIES)] for i, g in enumerate(sorted(groups))}


def fig1_hibernation_heatmap(cfg):
    piv = kpi("hibernation_rate").pivot(index="group", columns="snapshot", values="value").sort_index() * 100
    f, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(piv.values, cmap=SEQ, aspect="auto", vmin=0, vmax=np.ceil(piv.values.max() / 5) * 5)
    for (i, j), v in np.ndenumerate(piv.values):
        ax.text(j, i, f"{v:.1f}%", ha="center", va="center", fontsize=8.5,
                color="white" if v > 0.55 * im.get_clim()[1] else INK)
    ax.set_xticks(range(piv.shape[1]), piv.columns), ax.set_yticks(range(piv.shape[0]), piv.index)
    ax.set_xticks(np.arange(piv.shape[1] + 1) - 0.5, minor=True), ax.set_yticks(np.arange(piv.shape[0] + 1) - 0.5, minor=True)
    ax.grid(False)
    ax.grid(which="minor", color=SURFACE, linewidth=2)  # khe 2px giữa các ô
    ax.tick_params(which="minor", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel("Mốc dữ liệu"), ax.set_ylabel("Vùng")
    ax.set_title("KPI 1. Tỉ lệ listing \"ngủ đông\" theo vùng và mốc")
    cb = f.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label("Tỉ lệ ngủ đông (%)", color=INK2)
    cb.outline.set_visible(False)
    return f, ("Ngủ đông = estimated_occupancy_l365d bằng 0 đêm. Cột này Inside Airbnb ước tính từ số review, "
               "nên listing mới mở trong năm cũng bị tính là ngủ đông.")


def connected_dots(d, title, ylabel, cfg, note):
    """Mỗi vùng một đường nối các mốc; mốc thiếu dữ liệu vẫn có vạch trên trục, đoạn nối qua nó vẽ nét đứt."""
    snaps = [str(s) for s in cfg["snapshots"]]
    x = {s: i for i, s in enumerate(snaps)}
    have = [s for s in snaps if s in set(d["snapshot"])]
    miss = [s for s in snaps if s not in have]
    col = colors(d["group"].unique())
    f, ax = plt.subplots(figsize=(8.6, 4.8))
    last = d[d["snapshot"] == have[-1]].set_index("group")["value"].sort_values(ascending=False)
    for g in last.index:  # vẽ theo thứ tự giá trị mốc cuối để chú giải khớp thứ tự đường từ trên xuống
        r = d[d["group"] == g].set_index("snapshot")["value"].reindex(have)
        for a, b in zip(have, have[1:]):
            gap = x[b] - x[a] > 1
            ax.plot([x[a], x[b]], [r[a], r[b]], color=col[g], ls=(0, (3, 2)) if gap else "-",
                    lw=1.6 if gap else 2, alpha=0.7 if gap else 1, zorder=2)
        ax.scatter([x[s] for s in have], r.values, s=40, color=col[g], edgecolor=SURFACE, linewidth=1.5, zorder=3)
    labels = [f"{s}\n(không có dữ liệu)" if s in miss else s for s in snaps]
    ax.set_xticks(range(len(snaps)), labels)
    for t, s in zip(ax.get_xticklabels(), snaps):
        if s in miss:
            t.set_color(MUTED)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(k))
    ax.set_xlabel("Mốc dữ liệu"), ax.set_ylabel(ylabel)
    ax.set_title(title)
    handles = [Line2D([], [], color=col[g], ls="-", marker="o", markeredgecolor=SURFACE, label=f"{g}  {k(v)}") for g, v in last.items()]
    ax.legend(handles=handles, title=f"Vùng (giá trị {have[-1]})", loc="upper left", bbox_to_anchor=(1.01, 1),
              fontsize=8, title_fontsize=8, alignment="left")
    gap_note = f" Mốc {', '.join(miss)} không có dữ liệu; nét đứt chỉ nối hai mốc có dữ liệu, không phải giá trị mốc đó." if miss else ""
    return f, note + gap_note


def fig2_median_price(cfg):
    d = kpi("median_price")
    return connected_dots(d[d["room_type"] == "all"], "KPI 2. Giá trung vị theo vùng (mọi loại phòng)",
                          f"Giá trung vị ({cfg['currency']}/đêm)", cfg,
                          "Trung vị price khác rỗng. Mốc 03 là cuối mùa hè ở Cape Town nên giá cao hơn; "
                          "kpi_median_price.csv có thêm số liệu theo từng loại phòng.")


def fig3_median_revenue(cfg):
    return connected_dots(kpi("median_revenue"), "KPI 3. Doanh thu ước tính trung vị mỗi listing mỗi năm",
                          f"Doanh thu trung vị ({cfg['currency']}/năm)", cfg,
                          "Trung vị estimated_revenue_l365d (ước tính của Inside Airbnb), tính cả listing doanh thu 0.")


def fig4_net_sentiment(cfg):
    d = kpi("net_sentiment").sort_values("value", ascending=False)
    tot = kpi("net_sentiment", "all").iloc[0]
    # thành phần nhãn theo vùng: cùng phép nối review -> listing -> vùng như kpi.py
    L = pd.read_csv(P / "listings_clean.csv", dtype=str).drop_duplicates("id", keep="last").set_index("id")["analysis_area"]
    rv = pd.read_csv(P / "reviews_clean.csv", usecols=["id", "listing_id"], dtype=str)
    z = pd.read_csv(P / "llm_results.csv", dtype=str).query("status == 'ok'").merge(rv, left_on="review_id", right_on="id")
    comp = pd.crosstab(z["listing_id"].map(L), z["sentiment"], normalize="index").reindex(d["group"]).fillna(0) * 100
    f, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.6), gridspec_kw={"width_ratios": [1.35, 1]}, sharey=True)
    y = np.arange(len(d))
    a1.hlines(y, d["ci_lo"], d["ci_hi"], color=POS, lw=2.5, alpha=0.35)
    a1.scatter(d["value"], y, s=50, color=POS, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for i, (v, n, hi) in enumerate(zip(d["value"], d["n"], d["ci_hi"])):
        a1.annotate(f"{v:.2f}  n={n}", (hi, i), xytext=(6, 0), textcoords="offset points", va="center", fontsize=8, color=INK2)
    a1.axvline(tot["value"], color=INK2, lw=1, ls=(0, (3, 2)))
    a1.set_yticks(y, d["group"]), a1.set_ylim(len(d) - 0.5, -1.1)  # chừa một hàng trống phía trên cho nhãn toàn mẫu
    a1.annotate(f"toàn mẫu {tot['value']:.2f}", (tot["value"], -0.8), xytext=(4, 0), textcoords="offset points",
                fontsize=8, color=INK2, va="center")
    a1.grid(axis="y", visible=False)
    a1.set_xlim(min(0.6, d["ci_lo"].min() - 0.03), 1.1)
    a1.set_xlabel("Cảm xúc ròng (−1 đến 1), trục đã phóng to")
    a1.set_title("KPI 4. Cảm xúc ròng theo vùng, khoảng tin cậy 95%")
    left = np.zeros(len(d))
    for lab, c in (("negative", NEG), ("mixed", MIX), ("positive", POS)):
        v = comp.get(lab, pd.Series(0, index=comp.index)).to_numpy()
        a2.barh(y, v, left=left, height=0.55, color=c, edgecolor=SURFACE, linewidth=2, label=lab)  # viền nền = khe 2px
        left += v
    for i, v in enumerate(comp.get("negative", pd.Series(0, index=comp.index))):
        a2.annotate(f"{v:.0f}% neg", (100, i), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color=INK2)
    a2.set_xlim(0, 112), a2.set_xticks(range(0, 101, 20))
    a2.grid(axis="y", visible=False)
    a2.set_xlabel("Tỉ lệ review (%)")
    a2.set_title("Thành phần nhãn LLM")
    a2.legend(loc="upper center", bbox_to_anchor=(0.45, -0.14), ncols=3)
    return f, ("positive = +1, mixed = 0, negative = −1; trung bình trên review LLM gán nhãn thành công. "
               f"Thanh ngang = khoảng tin cậy 95% (bootstrap {cfg['eval']['bootstrap']} lần, lấy mẫu lại theo listing).\n"
               "Các khoảng chồng nhau nhiều: mẫu chưa đủ để xếp hạng chắc chắn mọi vùng.")


def revenue_tiers(t):
    """KPI 5: D = (Tmax - Tmin)/3; nhóm 1: T < Tmin + D; nhóm 2: Tmin + D <= T <= Tmax - D; nhóm 3: T > Tmax - D."""
    lo, hi = t.min(), t.max()
    d = (hi - lo) / 3
    c1, c2 = lo + d, hi - d
    return pd.Series(np.where(t < c1, 0, np.where(t <= c2, 1, 2)), index=t.index), (c1, c2)


def fig5_occupied_nights_bubble(cfg):
    last = str(cfg["snapshots"][-1])
    pick = lambda d: d[d["snapshot"] == last].set_index("group")["value"]  # noqa: E731
    pr = kpi("median_price")
    m = pd.DataFrame({"nights": pick(kpi("median_occupied_nights")), "price": pick(pr[pr["room_type"] == "all"]),
                      "rev": pick(kpi("median_revenue"))}).dropna()
    tier, (c1, c2) = revenue_tiers(m["rev"])
    L = pd.read_csv(P / "listings_clean.csv", dtype={"snapshot": str})
    L = L[L["snapshot"] == last]
    ref_x = L.loc[L["estimated_occupancy_l365d"] > 0, "estimated_occupancy_l365d"].median()  # trung vị toàn mẫu
    ref_y = L["price"].median()
    f, ax = plt.subplots(figsize=(8.6, 5.6))
    size = 2600 * m["rev"] / m["rev"].max()  # diện tích bóng tỉ lệ với doanh thu
    ax.scatter(m["nights"], m["price"], s=size, c=[TIERS[t] for t in tier], alpha=0.85, edgecolor=SURFACE, linewidth=2, zorder=3)
    for g, r in m.iterrows():
        rad = np.sqrt(2600 * r["rev"] / m["rev"].max() / np.pi)  # bán kính (điểm ảnh) để đặt nhãn sát mép bóng
        ax.annotate(f"{g}", (r["nights"], r["price"]), xytext=(rad + 3, 4), textcoords="offset points",
                    fontsize=9, fontweight="bold", color=INK, va="bottom")
        ax.annotate(f"{k(r['rev'])}/năm", (r["nights"], r["price"]), xytext=(rad + 3, -2), textcoords="offset points",
                    fontsize=8, color=INK2, va="top")
    ax.axvline(ref_x, color=INK2, lw=1, ls=(0, (3, 2)), zorder=1)
    ax.axhline(ref_y, color=INK2, lw=1, ls=(0, (3, 2)), zorder=1)
    ax.set_xlim(20, max(105, m["nights"].max() + 15))
    ax.set_ylim(min(900, m["price"].min() - 250), max(3200, m["price"].max() + 300))
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    for tx, ty, ha, va, s in ((x0, y1, "left", "top", "Giá cao, ít đêm"), (x1, y1, "right", "top", "Giá cao, nhiều đêm"),
                              (x0, y0, "left", "bottom", "Giá thấp, ít đêm"), (x1, y0, "right", "bottom", "Giá thấp, nhiều đêm")):
        ax.annotate(s, (tx, ty), xytext=(6 if ha == "left" else -6, -6 if va == "top" else 6), textcoords="offset points",
                    ha=ha, va=va, fontsize=8, color=MUTED)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(k))
    ax.set_xlabel("Số đêm có khách trung vị (đêm/năm, listing đang hoạt động)")
    ax.set_ylabel(f"Giá trung vị ({cfg['currency']}/đêm)")
    ax.set_title(f"KPI 5. Số đêm có khách, giá và doanh thu theo vùng, mốc {last}")
    names = [f"Doanh thu < {k(c1)}/năm", f"Doanh thu {k(c1)} – {k(c2)}/năm", f"Doanh thu > {k(c2)}/năm"]
    ax.legend(handles=[Line2D([], [], ls="", marker="o", markersize=9, color=c, label=n) for c, n in zip(TIERS, names)],
              loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=3, fontsize=8, handletextpad=0.3)
    return f, (f"Kích thước bóng tỉ lệ với doanh thu trung vị. Nhóm màu: D = (Tmax − Tmin)/3, T = doanh thu trung vị của vùng; "
               f"nhóm 1: T < Tmin + D ({k(c1)}); nhóm 2: Tmin + D ≤ T ≤ Tmax − D ({k(c2)}); nhóm 3: T > Tmax − D.\n"
               f"Đường nét đứt: trung vị toàn mẫu ({ref_x:.0f} đêm; {ref_y:,.0f} {cfg['currency']}/đêm, mọi loại phòng).")


def fig6_llm_vs_baseline(cfg):
    raw = pd.read_csv(P / "eval_metrics.csv")
    e = raw[(raw["group"] == "all") & raw["method"].isin(NAMES)].pivot(index="method", columns="metric", values="value")
    n = int(raw.query("group == 'all' and metric == 'accuracy'")["n"].max())
    f, ax = plt.subplots(figsize=(7.4, 3.8))
    order = list(NAMES)
    for j, (key, c) in enumerate(zip(("accuracy", "macro_f1"), SERIES)):
        y = np.arange(len(order)) + (-0.17 if j == 0 else 0.17)
        v = e.loc[order, key]
        ax.hlines(y, e.loc[order, f"{key}_ci_lo"], e.loc[order, f"{key}_ci_hi"], color=c, lw=2.5, alpha=0.4)
        ax.scatter(v, y, s=46, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3, label=key.replace("_", "-"))
        for yy, vv in zip(y, v):
            ax.annotate(f"{vv:.2f}", (vv, yy), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=8, color=INK)
    ax.set_yticks(range(len(order)), [NAMES[m] for m in order])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Điểm trên nhãn tay (chấm = ước lượng, vạch = khoảng tin cậy 95% bootstrap)")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=2)
    ax.set_title(f"Gán nhãn cảm xúc so với {n} nhãn tay")
    return f, "Nhãn tay 97% positive nên macro-F1 chỉ dựa vào 3 review không phải positive; khoảng tin cậy rất rộng."


FIGS = (fig1_hibernation_heatmap, fig2_median_price, fig3_median_revenue, fig4_net_sentiment,
        fig5_occupied_nights_bubble, fig6_llm_vs_baseline)


def main(config_path):
    with open(config_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    FIG.mkdir(exist_ok=True)
    keep = {f"{fn.__name__}.png" for fn in FIGS}
    for old in FIG.glob("fig*.png"):  # xoá hình cũ không còn sinh ra, để figures/ khớp đúng với code
        if old.name not in keep:
            old.unlink()
    s = cfg["snapshots"]
    src = f"Nguồn: Inside Airbnb (CC BY 4.0), Cape Town, mốc {s[0]} đến {s[-1]}; mẫu 1000 listing của nhóm {cfg['group_code']}."
    for fn in FIGS:
        f, caption = fn(cfg)
        width = int(f.get_figwidth() * 19)  # số ký tự vừa một dòng ở cỡ chữ 6.8pt
        text = "\n".join(textwrap.fill(t, width) for t in f"{caption}\n{src}".split("\n"))
        lines = text.count("\n") + 1
        f.text(0.01, 0.01, text, fontsize=6.8, va="bottom", color=INK2)
        f.tight_layout(rect=(0, (lines * 0.135 + 0.05) / f.get_figheight(), 1, 1))
        f.savefig(FIG / f"{fn.__name__}.png", dpi=200)
        plt.close(f)
        print(f"[ok]   figures/{fn.__name__}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "configs/cape_town.yaml"))
