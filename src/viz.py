"""Vẽ 5 hình KPI + 1 hình đánh giá LLM vào figures/ (chỉ đọc kết quả có sẵn): python src/viz.py configs/cape_town.yaml"""
import sys
import textwrap
import matplotlib
import numpy as np
import pandas as pd
import yaml
from download import ROOT
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

P, FIG = ROOT / "data" / "processed", ROOT / "figures"
BG, INK, INK2, GRID, MUTED, DASH = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2", (0, (3, 2))
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]  # A01..A08, cố định
SEQ = matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
TIERS, SENT = ["#86b6ef", "#2a78d6", "#104281"], {"negative": "#e34948", "mixed": MUTED, "positive": SERIES[0]}
NAMES = {"llm": "LLM (Gemini)", "baseline": "VADER baseline", "floor": "Luôn đoán lớp phổ biến nhất"}
plt.rcParams.update({f"axes.{a}": v for a, v in dict(facecolor=BG, edgecolor=MUTED, linewidth=0.8, labelcolor=INK2,
    titlecolor=INK, titlesize=10, titleweight="bold", titlelocation="left", grid=True, axisbelow=True).items()} | {
    "figure.facecolor": BG, "savefig.facecolor": BG, "axes.spines.top": False, "axes.spines.right": False, "grid.color": GRID,
    "grid.linewidth": 0.8, "xtick.color": INK2, "ytick.color": INK2, "font.size": 8.5, "legend.frameon": False,
    "lines.linewidth": 2, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round"})

def kpi(name, level="analysis_area"):
    return (d := pd.read_csv(P / f"kpi_{name}.csv", dtype={"snapshot": str}))[d["level"] == level].copy()
def k(v, _=None):  # 83,400 -> 83k; dưới 10,000 giữ nguyên
    return f"{v / 1000:,.0f}k" if abs(v) >= 10_000 else f"{v:,.0f}"
def note(ax, s, xy, dx, dy=0, **kw):  # chữ lệch (dx, dy) điểm ảnh so với xy
    ax.annotate(s, xy, xytext=(dx, dy), textcoords="offset points", **{"fontsize": 8, "color": INK2, **kw})

def fig1_hibernation_heatmap(cfg):
    piv = kpi("hibernation_rate").pivot(index="group", columns="snapshot", values="value").sort_index() * 100
    (r, c), (f, ax) = piv.shape, plt.subplots(figsize=(7, 5))
    im = ax.imshow(piv.values, cmap=SEQ, aspect="auto", vmin=0, vmax=np.ceil(piv.values.max() / 5) * 5)
    for (i, j), v in np.ndenumerate(piv.values):
        ax.text(j, i, f"{v:.1f}%", ha="center", va="center", fontsize=8.5, color="white" if v > 0.55 * im.get_clim()[1] else INK)
    ax.set_xticks(range(c), piv.columns), ax.set_yticks(range(r), piv.index)
    ax.set_xticks(np.arange(c + 1) - 0.5, minor=True), ax.set_yticks(np.arange(r + 1) - 0.5, minor=True)
    ax.grid(False), ax.grid(which="minor", color=BG, linewidth=2), ax.tick_params(which="minor", length=0)  # khe 2px
    [s.set_visible(False) for s in ax.spines.values()]
    ax.set(xlabel="Mốc dữ liệu", ylabel="Vùng", title="KPI 1. Tỉ lệ listing \"ngủ đông\" theo vùng và mốc")
    (cb := f.colorbar(im, ax=ax, shrink=0.85)).set_label("Tỉ lệ ngủ đông (%)", color=INK2), cb.outline.set_visible(False)
    return f, ("Ngủ đông = estimated_occupancy_l365d bằng 0 đêm. Cột này Inside Airbnb ước tính từ số review, "
               "nên listing mới mở trong năm cũng bị tính là ngủ đông.")

def lines(cfg, d, title, ylabel, caption):  # KPI 2, 3: đường liền qua các mốc có dữ liệu
    snaps, (f, ax) = [str(s) for s in cfg["snapshots"]], plt.subplots(figsize=(8.6, 4.8))
    have, col = [s for s in snaps if s in set(d["snapshot"])], dict(zip(sorted(d["group"].unique()), SERIES))
    miss, last = [s for s in snaps if s not in have], d[d["snapshot"] == have[-1]].set_index("group")["value"]
    for g, v in last.sort_values(ascending=False).items():  # theo giá trị mốc cuối: chú giải khớp thứ tự đường
        ax.plot([snaps.index(s) for s in have], d[d["group"] == g].set_index("snapshot")["value"].reindex(have),
                color=col[g], marker="o", ms=6.3, mec=BG, mew=1.5, label=f"{g}  {k(v)}")
    ax.set_xticks(range(len(snaps)), [f"{s}\n(không có dữ liệu)" if s in miss else s for s in snaps])
    [t.set_color(MUTED) for t, s in zip(ax.get_xticklabels(), snaps) if s in miss], ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(k)), ax.set(xlabel="Mốc dữ liệu", ylabel=ylabel, title=title)
    ax.legend(title=f"Vùng (giá trị {have[-1]})", loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8,
              title_fontsize=8, alignment="left")
    return f, caption + (f" Mốc {', '.join(miss)} không có dữ liệu; đường nối qua mốc này chỉ thể hiện xu hướng giữa "
                         "hai mốc có dữ liệu, không phải giá trị mốc đó." if miss else "")

def fig4_net_sentiment(cfg):
    d, tot = kpi("net_sentiment").sort_values("value", ascending=False), kpi("net_sentiment", "all").iloc[0]["value"]
    area = pd.read_csv(P / "listings_clean.csv", dtype=str).drop_duplicates("id", keep="last").set_index("id")["analysis_area"]
    z = pd.read_csv(P / "llm_results.csv", dtype=str).query("status == 'ok'").merge(pd.read_csv(  # cùng phép nối như kpi.py
        P / "reviews_clean.csv", usecols=["id", "listing_id"], dtype=str), left_on="review_id", right_on="id")
    comp = (pd.crosstab(z["listing_id"].map(area), z["sentiment"], normalize="index").reindex(d["group"]).fillna(0) * 100
            ).reindex(columns=list(SENT), fill_value=0)
    f, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.6), gridspec_kw={"width_ratios": [1.35, 1]}, sharey=True)
    y, left = np.arange(len(d)), np.zeros(len(d))
    a1.hlines(y, d["ci_lo"], d["ci_hi"], color=SENT["positive"], lw=2.5, alpha=0.35)
    a1.scatter(d["value"], y, s=50, color=SENT["positive"], edgecolor=BG, linewidth=1.5, zorder=3)
    [note(a1, f"{v:.2f}  n={n}", (hi, i), 6, va="center") for i, (v, n, hi) in enumerate(zip(d["value"], d["n"], d["ci_hi"]))]
    a1.axvline(tot, color=INK2, lw=1, ls=DASH), a1.set_yticks(y, d["group"]), a1.set_ylim(len(d) - 0.5, -1.1)  # hàng trống trên
    note(a1, f"toàn mẫu {tot:.2f}", (tot, -0.8), 4, va="center"), a1.grid(axis="y", visible=False)
    a1.set(xlim=(min(0.6, d["ci_lo"].min() - 0.03), 1.1), xlabel="Cảm xúc ròng (−1 đến 1), trục đã phóng to",
           title="KPI 4. Cảm xúc ròng theo vùng, khoảng tin cậy 95%")
    for lab, c in SENT.items():  # viền màu nền = khe 2px giữa các đoạn
        a2.barh(y, comp[lab].to_numpy(), left=left, height=0.55, color=c, edgecolor=BG, linewidth=2, label=lab)
        left = left + comp[lab].to_numpy()
    [note(a2, f"{v:.0f}% neg", (100, i), 4, va="center") for i, v in enumerate(comp["negative"])]
    a2.set(xlim=(0, 112), xticks=range(0, 101, 20), xlabel="Tỉ lệ review (%)", title="Thành phần nhãn LLM")
    a2.grid(axis="y", visible=False), a2.legend(loc="upper center", bbox_to_anchor=(0.45, -0.14), ncols=3)
    return f, ("positive = +1, mixed = 0, negative = −1; trung bình trên review LLM gán nhãn thành công. Thanh ngang = "
               f"khoảng tin cậy 95% (bootstrap {cfg['eval']['bootstrap']} lần, lấy mẫu lại theo listing).\n"
               "Các khoảng chồng nhau nhiều: mẫu chưa đủ để xếp hạng chắc chắn mọi vùng.")

def tag(p, o):  # nhãn nguồn doanh thu theo độ lệch % của giá (p) và số đêm (o); |lệch| <= 10% là ngang mức chung
    hi_p, lo_p, hi_o, lo_o = p > 10, p < -10, o > 10, o < -10
    return ("giá + khách" if hi_p and hi_o else "giá cao, ít khách" if hi_p and lo_o else "nhờ giá" if hi_p else
            "đông khách" if hi_o else "yếu cả hai" if lo_p and lo_o else "ít khách" if lo_o else "giá thấp" if lo_p else
            "ngang mức chung")


def fig5_revenue_drivers(cfg):
    L = pd.read_csv(P / "listings_clean.csv", dtype={"snapshot": str}).query("estimated_occupancy_l365d > 0")
    snaps = [str(s) for s in cfg["snapshots"] if L.loc[L["snapshot"] == str(s), "price"].notna().any()]  # bỏ mốc không có giá
    rev = kpi("median_revenue")
    order = rev[rev["snapshot"] == snaps[-1]].sort_values("value", ascending=False)["group"].tolist()  # doanh thu cao ở trên
    f, axs = plt.subplots(1, len(snaps), figsize=(12, 5.4), sharey=True)
    tags = []  # nhãn của từng vùng ở từng mốc, để lấy nhãn chung theo đa số
    for ax, snap in zip(axs, snaps):
        d = L[L["snapshot"] == snap]
        g = d.groupby("analysis_area").agg(p=("price", "median"), o=("estimated_occupancy_l365d", "median")).reindex(order)
        g = pd.DataFrame({"p": g["p"] / d["price"].median() - 1, "o": g["o"] / d["estimated_occupancy_l365d"].median() - 1}) * 100
        y = np.arange(len(order))
        tags.append([tag(p, o) for p, o in zip(g["p"], g["o"])])
        ax.axvspan(-10, 10, color=GRID, alpha=0.6, lw=0, zorder=0), ax.axvline(0, color=INK, lw=1, zorder=1)
        ax.barh(y - 0.19, g["p"], height=0.36, color=SERIES[1], label="Giá", zorder=2)
        ax.barh(y + 0.19, g["o"], height=0.36, color=SERIES[0], label="Số đêm có khách", zorder=2)
        ax.set(yticks=y, yticklabels=order, xlim=(-55, 90), xticks=[-50, 0, 50], title=f"{snap[5:7]}/{snap[:4]}")
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0")), ax.grid(axis="y", visible=False)
    axs[0].invert_yaxis()
    for i, ts in enumerate(zip(*tags)):  # nhãn chung: nhãn xuất hiện ở ít nhất 2/3 mốc, ghi kèm số mốc; không có thì "không ổn định"
        top = max(set(ts), key=ts.count)
        note(axs[-1], f"{top} ({ts.count(top)}/{len(ts)})" if ts.count(top) * 2 > len(ts) else "không ổn định", (90, i), 8,
             va="center", fontsize=8.5, color=INK)
    note(axs[-1], f"Nguồn doanh thu ({len(snaps)} mốc)", (90, -0.75), 8, va="center", color=MUTED)
    h, lab = axs[0].get_legend_handles_labels()  # dòng trống trong tiêu đề chừa chỗ cho chú giải, không đè tiêu đề mốc
    f.suptitle("KPI 5. Giá và số đêm có khách trung vị của từng vùng, lệch bao nhiêu % so với mức chung cùng mốc\n ",
               x=0.01, ha="left", va="top", fontsize=10, fontweight="bold", color=INK, linespacing=2.2)
    f.legend(h + [plt.Rectangle((0, 0), 1, 1, color=GRID, alpha=0.6)], lab + ["Vùng ±10%: ngang mức chung"], ncols=3,
             loc="upper left", bbox_to_anchor=(0.005, 0.935), fontsize=8.5).set_in_layout(False)
    mid = L[L["snapshot"] == snaps[-1]]
    return f, ("Chỉ tính listing có estimated_occupancy_l365d > 0; mức chung mốc "
               f"{snaps[-1]}: {mid['price'].median():,.0f} {cfg['currency']}/đêm và {mid['estimated_occupancy_l365d'].median():.0f} đêm/năm. "
               "Vùng xếp theo doanh thu trung vị (KPI 3) mốc cuối, cao nhất ở trên. Mốc 12/2025 không có giá nên không so được. "
               "Nhãn bên phải: ở mỗi mốc, cột lệch quá ±10% mới tính là cao hoặc thấp; nhãn chung là nhãn "
               f"xuất hiện ở đa số mốc, kèm số mốc (vd 2/{len(snaps)}); không có đa số thì ghi \"không ổn định\".")


def fig6_llm_vs_baseline(cfg):
    raw, (f, ax) = pd.read_csv(P / "eval_metrics.csv").query("group == 'all'"), plt.subplots(figsize=(7.4, 3.8))
    e = raw[raw["method"].isin(NAMES)].pivot(index="method", columns="metric", values="value").loc[list(NAMES)]
    for dy, key, c in ((-0.17, "accuracy", SERIES[0]), (0.17, "macro_f1", SERIES[1])):
        ax.hlines(y := np.arange(len(NAMES)) + dy, e[f"{key}_ci_lo"], e[f"{key}_ci_hi"], color=c, lw=2.5, alpha=0.4)
        ax.scatter(e[key], y, s=46, color=c, edgecolor=BG, linewidth=1.5, zorder=3, label=key.replace("_", "-"))
        [note(ax, f"{vv:.2f}", (vv, yy), 0, 6, ha="center", color=INK) for yy, vv in zip(y, e[key])]
    ax.set_yticks(range(len(NAMES)), list(NAMES.values())), ax.invert_yaxis(), ax.grid(axis="y", visible=False)
    ax.set(xlim=(0, 1.02), xlabel="Điểm trên nhãn tay (chấm = ước lượng, vạch = khoảng tin cậy 95% bootstrap)",
           title=f"Gán nhãn cảm xúc so với {int(raw.loc[raw['metric'] == 'accuracy', 'n'].max())} nhãn tay")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=2)
    return f, "Nhãn tay 97% positive nên macro-F1 chỉ dựa vào 3 review không phải positive; khoảng tin cậy rất rộng."

FIGS = {fn.__name__: fn for fn in (fig1_hibernation_heatmap, fig4_net_sentiment, fig5_revenue_drivers,
                                   fig6_llm_vs_baseline)} | {"fig2_median_price": lambda cfg: lines(
    cfg, kpi("median_price").query("room_type == 'all'"), "KPI 2. Giá trung vị theo vùng (mọi loại phòng)", f"Giá trung vị "
    f"({cfg['currency']}/đêm)", "Trung vị price khác rỗng. Mốc 03 là cuối mùa hè ở Cape Town nên giá cao hơn; "
    "kpi_median_price.csv có thêm số liệu theo từng loại phòng."), "fig3_median_revenue": lambda cfg: lines(
    cfg, kpi("median_revenue"), "KPI 3. Doanh thu ước tính trung vị mỗi listing mỗi năm", f"Doanh thu trung vị ({cfg['currency']}"
    "/năm)", "Trung vị estimated_revenue_l365d (ước tính của Inside Airbnb), tính cả listing doanh thu 0.")}

def main(config_path):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    FIG.mkdir(exist_ok=True), [p.unlink() for p in FIG.glob("fig*.png") if p.stem not in FIGS]  # bỏ hình cũ không còn sinh ra
    src = (f"Nguồn: Inside Airbnb (CC BY 4.0), Cape Town, mốc {cfg['snapshots'][0]} đến {cfg['snapshots'][-1]}; "
           f"mẫu 1000 listing của nhóm {cfg['group_code']}.")
    for name, fn in FIGS.items():
        f, caption = fn(cfg)
        text = "\n".join(textwrap.fill(t, int(f.get_figwidth() * 19)) for t in f"{caption}\n{src}".split("\n"))
        f.text(0.01, 0.01, text, fontsize=6.8, va="bottom", color=INK2)
        f.tight_layout(rect=(0, ((text.count("\n") + 1) * 0.135 + 0.05) / f.get_figheight(), 1, 1))
        f.savefig(FIG / f"{name}.png", dpi=200), plt.close(f), print(f"[ok]   figures/{name}.png")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "configs/cape_town.yaml")
