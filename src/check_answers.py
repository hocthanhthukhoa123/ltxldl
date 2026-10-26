"""Print the facts needed to answer the 5 questions of the data-check report.

    python src/check_answers.py --config configs/cape_town.yaml

Run AFTER src/download.py and src/qa.py. Reads data/raw/ and the ID files in
data/samples/ (from sheet «Phân công»), prints:
  Q1  download / read problems and schema differences between snapshots
  Q2  how many LLM-sample and manual-label reviews were found per snapshot
  Q3  listings columns with >= 90% NaN, per snapshot (after filtering)
  Q4  % missing of the columns the team plans to use for KPIs
  +   the self-checks from sheet «Hướng dẫn»
"""
import argparse

import pandas as pd

from download import FILES, ROOT, load_config, raw_file, read_manifest

KPI_COLUMNS = ["price", "estimated_revenue_l365d", "estimated_occupancy_l365d", "availability_365",
               "number_of_reviews", "review_scores_rating", "neighbourhood_cleansed",
               "neighbourhood_group_cleansed", "bedrooms", "host_is_superhost"]
CHUNK = 500_000


def pct(x):
    return f"{x * 100:.1f}%"


def main(cfg):
    snaps = cfg["snapshots"]
    manifest = read_manifest(ROOT / "reports" / "download_manifest.csv")
    ids = pd.read_csv(ROOT / cfg["listing_ids"])
    rev_ids = pd.read_csv(ROOT / cfg["review_ids"])
    keep = set(ids["listing_id"])

    print("=== Q1: download / read problems")
    for snap in snaps:
        for name in FILES:
            r = manifest.get((snap, name), {})
            flag = "" if r.get("status") == "ok" else f"  <-- {r.get('status')}: {r.get('message')}"
            print(f"  {snap} {name:<15} action={r.get('action', '?'):<10}{flag}")
    print("  (a 'missing columns' error here means the file was read fine but its columns changed)")
    columns = {s: list(pd.read_csv(raw_file(cfg, s, "listings"), nrows=0).columns) for s in snaps}
    union = set().union(*columns.values())
    for s in snaps:
        cal = list(pd.read_csv(raw_file(cfg, s, "calendar"), nrows=0).columns)
        print(f"  {s}: listings {len(columns[s])} cols, missing vs other snapshots: "
              f"{sorted(union - set(columns[s])) or '-'}; calendar cols: {cal}")

    expected_no_review = [50, 30, 25, 25]
    for i, s in enumerate(snaps):
        print(f"\n=== {s}")
        L = pd.read_csv(raw_file(cfg, s, "listings"), low_memory=False)
        L = L[L["id"].isin(keep)].merge(ids, left_on="id", right_on="listing_id")
        R = pd.read_csv(raw_file(cfg, s, "reviews"))
        R = R[R["id"].isin(rev_ids["review_id"])].merge(rev_ids, left_on="id", right_on="review_id")
        cal_rows = sum(int(c["listing_id"].isin(keep).sum())
                       for c in pd.read_csv(raw_file(cfg, s, "calendar"), usecols=["listing_id"], chunksize=CHUNK))

        print(f"  Q2: LLM sample found {int(R['llm_sample'].sum())}/1000, manual labels found "
              f"{int(R['manual_label'].sum())}/100 (inside LLM sample: "
              f"{int((R['llm_sample'] & R['manual_label']).sum())}); reviews {len(R)}/5000, "
              f"empty comments {int(R['comments'].isna().sum())}, duplicate ids {int(R['id'].duplicated().sum())}")

        na = L.isna().mean()
        nan90 = na[na >= 0.9].index.tolist()
        print(f"  Q3: {len(nan90)} columns with >=90% NaN: {', '.join(sorted(nan90))}")
        print("  Q4: missing in KPI columns: " +
              ", ".join(f"{c}={pct(na[c])}" if c in na else f"{c}=ABSENT" for c in KPI_COLUMNS))

        rooms = L["room_type"].value_counts()
        checks = {
            "listings = 1000": len(L) == 1000,
            "calendar = 365000": cal_rows == 365_000,
            "reviews = 5000": len(R) == 5000,
            "875 Entire home/apt": rooms.get("Entire home/apt", 0) == 875,
            "125 Private room": rooms.get("Private room", 0) == 125,
            f"{expected_no_review[i]} without reviews": int((L["number_of_reviews"] == 0).sum()) == expected_no_review[i],
            "120-130 listings per area": L["analysis_area"].value_counts().between(120, 130).all(),
        }
        if i == len(snaps) - 1:
            checks["20 missing price (last snapshot)"] = int(L["price"].isna().sum()) == 20
        print("  self-check: " + ", ".join(f"{k} {'OK' if v else 'FAIL'}" for k, v in checks.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facts for the 5 report questions.")
    parser.add_argument("--config", required=True, help="e.g. configs/cape_town.yaml")
    main(load_config(parser.parse_args().config))
