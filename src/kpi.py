"""Tính 5 KPI theo vùng: python src/kpi.py configs/cape_town.yaml  (chạy sau llm.py)
Vào: data/processed/{listings_clean,reviews_clean,llm_results}.csv; tham số ở mục `kpi:` của YAML.
Ra: data/processed/kpi_<tên>.csv. Dạng dài: kpi, snapshot, level, group, room_type, value, n (số mẫu), currency (tỉ lệ lưu dạng 0-1).
median_price tính trên mọi loại phòng gộp lại (room_type = "all").
net_sentiment có thêm ci_lo, ci_hi: khoảng tin cậy 95% bằng bootstrap theo cụm listing (review cùng listing không độc lập),
và một dòng level = "all" cho toàn mẫu; không tính review tự động (auto_generated)."""
import sys

import numpy as np
import pandas as pd

from common import PROC, run

S, OCC, REV = "snapshot", "estimated_occupancy_l365d", "estimated_revenue_l365d"
LEVELS = ["analysis_area", "neighbourhood_cleansed"]  # cấp vùng: khu vực được giao và phường
COLS = ["kpi", S, "level", "group", "room_type", "value", "n", "currency"]
CI = ["ci_lo", "ci_hi"]
SCORE = {"positive": 1, "mixed": 0, "negative": -1}
MONEY = {"median_price", "median_revenue"}  # KPI có đơn vị tiền tệ


def agg(d, col, fn, min_n, by=(S,)):
    """fn(col) theo từng cấp vùng (+ by); bỏ dòng thiếu col và nhóm dưới min_n quan sát."""
    d, parts = d.dropna(subset=[col]), []
    for lvl in LEVELS:
        t = d.groupby([*by, lvl])[col].agg(value=fn, n="size").round(4).reset_index()
        parts.append(t.rename(columns={lvl: "group"}).assign(level=lvl))
    out = pd.concat(parts)
    return out[out["n"] >= min_n]


def price_snapshots(df, cfg, verbose=False):
    """Mốc dùng cho KPI giá/doanh thu, chọn theo dữ liệu (không ghi cứng tháng): bỏ mốc có tỉ lệ listing có giá
    thấp hơn kpi.min_price_coverage. kpi.py và viz.py dùng chung."""
    cover = df.groupby(S)["price"].apply(lambda s: s.notna().mean())
    usable = cover[cover >= cfg["kpi"]["min_price_coverage"]].index
    if usable.empty:
        sys.exit("Không mốc nào có đủ listing có giá: hạ kpi.min_price_coverage hoặc xem qa_report.csv (rule price_empty).")
    for snap in cover.index.difference(usable) if verbose else []:
        print(f"Bỏ mốc {snap} khỏi KPI giá/doanh thu: chỉ {cover[snap]:.0%} listing có giá.")
    return [str(s) for s in usable]


def scored_reviews(df):
    """KPI 4 và hình cảm xúc: review (status ok, không phải review tự động) -> listing -> vùng ở mốc mới nhất, kèm điểm."""
    info = df.sort_values(S).drop_duplicates("id", keep="last").set_index("id")[LEVELS]  # mới nhất theo ngày, không theo thứ tự config
    info.index = info.index.astype(str)
    rv = pd.read_csv(PROC / "reviews_clean.csv", usecols=["id", "listing_id"], dtype=str)
    z = pd.read_csv(PROC / "llm_results.csv", dtype=str).query("status == 'ok' and auto_generated != 'True'")
    z = z.merge(rv, left_on="review_id", right_on="id")
    return z.join(info, on="listing_id").assign(score=lambda d: d["sentiment"].map(SCORE))


def cluster_ci(z, col, B, seed):
    """CI 95% của trung bình `col` theo từng vùng và toàn mẫu, lấy mẫu lại listing (cả cụm review) B lần."""
    rng, rows = np.random.default_rng(seed), []
    z = z.assign(all="all")
    for lvl in [*LEVELS, "all"]:
        for g, d in z.dropna(subset=[col, lvl]).groupby(lvl):
            s = d.groupby("listing_id")[col].agg(["sum", "count"])
            i = rng.integers(0, len(s), (B, len(s)))
            m = s["sum"].to_numpy()[i].sum(axis=1) / s["count"].to_numpy()[i].sum(axis=1)
            rows.append({"level": lvl, "group": g, **dict(zip(CI, np.percentile(m, [2.5, 97.5]).round(4)))})
    return pd.DataFrame(rows)


def overall(d, col):
    """Một dòng toàn mẫu (level = "all") cho KPI trung bình."""
    d = d.dropna(subset=[col])
    return pd.DataFrame([{"level": "all", "group": "all", "value": round(d[col].mean(), 4), "n": len(d)}])


def main(cfg):
    cur, n = cfg["currency"], cfg["kpi"]["min_n"]
    if not (PROC / "llm_results.csv").exists():
        sys.exit(f"Thiếu {PROC / 'llm_results.csv'}: chạy llm.py trước kpi.py.")
    df = pd.read_csv(PROC / "listings_clean.csv", dtype={S: str})
    sel = df[df[S].isin(price_snapshots(df, cfg, verbose=True))]
    z = scored_reviews(df)
    kpis = {
        "hibernation_rate": agg(df, OCC, lambda s: (s == 0).mean(), n),  # tỉ lệ listing có occupancy = 0
        "median_price": agg(sel, "price", "median", n).assign(room_type="all"),  # mọi loại phòng gộp lại
        "median_revenue": agg(sel, REV, "median", n),  # gồm cả listing doanh thu 0
        "median_occupied_nights": agg(df[df[OCC] > 0], OCC, "median", n),
        "net_sentiment": pd.concat([agg(z, "score", "mean", n, by=()), overall(z, "score")]).merge(
            cluster_ci(z, "score", cfg["eval"]["bootstrap"], cfg["seed"]), on=["level", "group"], how="left"),
    }
    for name, k in kpis.items():
        cols = COLS + [c for c in CI if c in k]
        k = k.assign(kpi=name, currency=cur if name in MONEY else "", **{S: k.get(S, "all")}).reindex(columns=cols)
        k.to_csv(PROC / f"kpi_{name}.csv", index=False)
        print(f"kpi_{name}.csv: {len(k)} dòng")


if __name__ == "__main__":
    run(main)
