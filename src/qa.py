"""Clean the downloaded Inside Airbnb snapshots and write the check report.

    python src/qa.py --config configs/cape_town.yaml [--code DSE2049-C01-G01-cape_town]

Output: reports/check_<ma_du_lieu>.csv  (4 rows, one per snapshot, 16 fields).
Empty cells mean "not available" (NaN), e.g. when the download failed.

All counts are computed AFTER filtering to the team's IDs (sheet «Phân công»):
  listings  -> id in config `listing_ids` (1,000 per snapshot)
  calendar  -> listing_id in config `listing_ids` (365,000 per snapshot)
  reviews   -> id in config `review_ids` (5,000 per snapshot)
Without those config keys the whole files are used.
"""
import argparse
import re
import sys

import pandas as pd

from download import ROOT, load_config, raw_file, read_manifest

FIELDS = ["ma_du_lieu", "moc", "ngay", "tai_ve_ok",
          "listings_bytes", "calendar_bytes", "reviews_bytes",
          "listings_dong", "calendar_dong", "reviews_dong",
          "entire_home", "private_room", "khong_co_review", "thieu_price",
          "so_cot_listings", "so_cot_nan_90"]
NEEDED = ("listings", "calendar", "reviews")
CHUNK = 500_000


def download_status(cfg, snap, manifest):
    """'co' if all 3 files were downloaded, else an HTTP code (e.g. '403') or a short reason.

    Only a failed DOWNLOAD counts here. A file that downloaded fine but has a data
    problem (e.g. a missing column) is still 'co'; the problem stays in the manifest.
    """
    for name in NEEDED:
        row = manifest.get((snap, name))
        if row and row.get("action") == "failed":
            m = re.search(r"HTTP (\d{3})", row.get("message", ""))
            return m.group(1) if m else "loi"
        if not raw_file(cfg, snap, name).exists():
            return "thieu_tep"
        if row and row.get("status") == "error":
            print(f"  note: {snap}/{name} has a data problem: {row.get('message', '')}")
    return "co"


def to_price(series):
    """'$1,234.00' -> 1234.0 ; empty / unparsable -> NaN."""
    return pd.to_numeric(series.astype("string").str.replace(r"[^0-9.]", "", regex=True),
                         errors="coerce")


def load_ids(cfg, key, column):
    """Set of int IDs from the CSV named in the config, or None if the key is absent."""
    if not cfg.get(key):
        return None
    ids = pd.read_csv(ROOT / cfg[key], dtype=str)[column]
    return set(pd.to_numeric(ids, errors="raise").astype("int64"))


def clean_listings(path, keep_ids=None):
    """Read listings, keep only the team's ids, drop duplicate ids, sort by id, make price numeric.
    Returns (dataframe, number of columns, number of columns with >=90% NaN)."""
    df = pd.read_csv(path, low_memory=False)
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df = df.dropna(subset=["id"]).astype({"id": "int64"})
    if keep_ids is not None:
        df = df[df["id"].isin(keep_ids)]
    df = df.drop_duplicates(subset="id").sort_values("id").reset_index(drop=True)
    nan90 = df.columns[df.isna().mean() >= 0.9].tolist() if len(df) else list(df.columns)
    n_nan90 = len(nan90)
    print(f"  listings columns with >=90% NaN ({n_nan90}): {', '.join(nan90)}")
    n_cols = df.shape[1]
    if "price" in df.columns:
        df["price"] = to_price(df["price"])
    if "room_type" in df.columns:
        df["room_type"] = df["room_type"].astype("string").str.strip()
    return df, n_cols, n_nan90


def count_rows(path, column, keep_ids=None):
    """Count data rows of a big csv.gz without loading it all (only rows whose `column` is in keep_ids)."""
    total = 0
    for chunk in pd.read_csv(path, usecols=[column], chunksize=CHUNK):
        ids = pd.to_numeric(chunk[column], errors="coerce")
        total += int(ids.isin(keep_ids).sum()) if keep_ids is not None else len(chunk)
    return total


def check_snapshot(cfg, code, index, snap, manifest, listing_ids=None, review_ids=None):
    row = dict.fromkeys(FIELDS, "")
    row.update(ma_du_lieu=code, moc=index, ngay=snap, tai_ve_ok=download_status(cfg, snap, manifest))
    if row["tai_ve_ok"] != "co":
        return row

    paths = {n: raw_file(cfg, snap, n) for n in NEEDED}
    for n in NEEDED:
        row[f"{n}_bytes"] = paths[n].stat().st_size

    df, n_cols, n_nan90 = clean_listings(paths["listings"], listing_ids)
    row["listings_dong"] = len(df)
    row["calendar_dong"] = count_rows(paths["calendar"], "listing_id", listing_ids)
    row["reviews_dong"] = count_rows(paths["reviews"], "id", review_ids)
    row["so_cot_listings"] = n_cols
    row["so_cot_nan_90"] = n_nan90

    if "room_type" in df.columns:
        row["entire_home"] = int((df["room_type"] == "Entire home/apt").sum())
        row["private_room"] = int((df["room_type"] == "Private room").sum())
    if "number_of_reviews" in df.columns:
        row["khong_co_review"] = int((pd.to_numeric(df["number_of_reviews"], errors="coerce") == 0).sum())
    if "price" in df.columns:
        row["thieu_price"] = int(df["price"].isna().sum())
    return row


def run(cfg, code=None):
    code = code or cfg.get("ma_du_lieu") or cfg["city"]
    reports = ROOT / cfg.get("reports_dir", "reports")
    manifest = read_manifest(reports / "download_manifest.csv")

    listing_ids = load_ids(cfg, "listing_ids", "listing_id")
    review_ids = load_ids(cfg, "review_ids", "review_id")
    if listing_ids is None:
        print("note: no listing_ids in config -> using the whole files")

    rows = []
    for i, snap in enumerate(cfg["snapshots"], start=1):
        print(f"checking {snap} ...")
        rows.append(check_snapshot(cfg, code, i, snap, manifest, listing_ids, review_ids))

    reports.mkdir(parents=True, exist_ok=True)
    out = reports / f"check_{code}.csv"
    pd.DataFrame(rows, columns=FIELDS).to_csv(out, index=False)
    print(f"report: {out}")
    return 0 if all(r["tai_ve_ok"] == "co" for r in rows) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean snapshots and write check_<ma_du_lieu>.csv.")
    parser.add_argument("--config", required=True, help="e.g. configs/cape_town.yaml")
    parser.add_argument("--code", help="ma_du_lieu from the 'Phân công' sheet (default: config ma_du_lieu, else city)")
    args = parser.parse_args()
    sys.exit(run(load_config(args.config), args.code))
