"""Download the team's ID lists from the «Phân công» Google Sheet.

    python src/fetch_ids.py --config configs/cape_town.yaml [--xlsx path/to/sheet.xlsx]

The sheet (shared by the instructor, "anyone with the link can view") has one tab
per kind of ID. We keep only the rows whose «Mã dữ liệu» is our `ma_du_lieu`:

  tab «Listing» -> data/samples/listing_ids.csv     listing_id, analysis_area   (1,000 rows)
  tab «Review»  -> data/samples/review_ids.csv      review_id, listing_id,
                                                    llm_sample, manual_label   (5,000 rows)
  tab «Vùng»    -> data/samples/analysis_areas.csv  analysis_area, lon/lat box (8 rows)

«Mẫu LLM» / «Nhãn tay» hold an "x" for the 1,000 LLM reviews / 100 hand-labelled
reviews; we turn them into True/False.

The whole spreadsheet is fetched once as .xlsx (Google's export URL) and every
cell is read as text, so 19-digit IDs are never rounded to floats.
Use --xlsx to read a file you downloaded yourself (File > Download > .xlsx).
"""
import argparse
import io
import sys
import urllib.request

import pandas as pd

from download import ROOT, load_config

EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
CODE_COL = "Mã dữ liệu"

# expected rows per team, from sheet «Hướng dẫn»
EXPECTED = {"listing": 1000, "review": 5000, "llm_sample": 1000, "manual_label": 100, "areas": 8}


def fetch_xlsx(sheet_id):
    url = EXPORT_URL.format(sheet_id=sheet_id)
    request = urllib.request.Request(url, headers={"User-Agent": "uet-dse2049-student-project"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"PK"):  # an .xlsx is a zip; anything else is a login / error page
        raise SystemExit(f"Could not download the sheet as .xlsx from {url} "
                         "(is it shared as 'anyone with the link can view'?)")
    return io.BytesIO(data)


def read_tabs(source, tabs):
    sheets = pd.read_excel(source, sheet_name=list(tabs.values()), dtype=str)
    return {key: sheets[name] for key, name in tabs.items()}


def x_flag(series):
    """'x' -> True, empty -> False."""
    return series.fillna("").str.strip().str.lower().eq("x")


def build(cfg, tabs):
    code = cfg["ma_du_lieu"]
    listing = tabs["listing"][tabs["listing"][CODE_COL] == code]
    review = tabs["review"][tabs["review"][CODE_COL] == code]
    city = tabs["assignment"].loc[tabs["assignment"][CODE_COL] == code, "Thành phố"]
    if listing.empty or review.empty or city.empty:
        raise SystemExit(f"No rows for ma_du_lieu={code!r} in the sheet")
    areas = tabs["areas"][tabs["areas"]["Thành phố"] == city.iloc[0]]

    listing = listing[["listing_id", "analysis_area"]]
    review = pd.DataFrame({
        "review_id": review["review_id"],
        "listing_id": review["listing_id"],
        "llm_sample": x_flag(review["Mẫu LLM"]),
        "manual_label": x_flag(review["Nhãn tay"]),
    })
    areas = areas.drop(columns="Thành phố")
    return listing, review, areas


def check(listing, review, areas):
    """Compare with the counts in sheet «Hướng dẫn». Returns a list of problems."""
    found = {
        "listing": listing["listing_id"].nunique(),
        "review": review["review_id"].nunique(),
        "llm_sample": int(review["llm_sample"].sum()),
        "manual_label": int(review["manual_label"].sum()),
        "areas": len(areas),
    }
    problems = [f"{k}: expected {EXPECTED[k]}, found {v}" for k, v in found.items() if v != EXPECTED[k]]
    outside = int((review["manual_label"] & ~review["llm_sample"]).sum())
    if outside:
        problems.append(f"{outside} hand-labelled reviews are not in the LLM sample")
    unknown = int((~review["listing_id"].isin(listing["listing_id"])).sum())
    if unknown:
        problems.append(f"{unknown} reviews belong to a listing that is not in our listing list")
    print("  " + ", ".join(f"{k}={v}" for k, v in found.items()))
    return problems


def run(cfg, xlsx=None):
    source = xlsx or fetch_xlsx(cfg["assignment_sheet"]["id"])
    tabs = read_tabs(source, cfg["assignment_sheet"]["tabs"])
    listing, review, areas = build(cfg, tabs)
    problems = check(listing, review, areas)

    outputs = {"listing_ids": listing, "review_ids": review, "analysis_areas": areas}
    for key, df in outputs.items():
        path = ROOT / cfg[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        print(f"  wrote {path.relative_to(ROOT)} ({len(df)} rows)")
    for p in problems:
        print(f"  PROBLEM: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download the team's ID lists from the «Phân công» sheet.")
    parser.add_argument("--config", required=True, help="e.g. configs/cape_town.yaml")
    parser.add_argument("--xlsx", help="read a downloaded copy of the sheet instead of fetching it")
    args = parser.parse_args()
    sys.exit(run(load_config(args.config), args.xlsx))
