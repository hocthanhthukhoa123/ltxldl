"""Chấm LLM, baseline và mức sàn (luôn đoán lớp phổ biến nhất) trên nhãn tay: python src/evaluate.py configs/cape_town.yaml
Chưa có tệp nhãn tay thì tạo bảng mẫu (cột label trống) rồi dừng. Quy ước: review mà phương pháp không trả nhãn hợp lệ (lỗi/rỗng) tính là SAI.
Ra: data/processed/eval_metrics.csv (method, group, metric, value, n), eval_confusion.csv, eval_errors.csv.
Người gán thứ hai (tuỳ chọn): python src/evaluate.py configs/cape_town.yaml --make-second-sheet tạo eval.labels_2 (cùng review,
cột label trống). Người thứ hai tự điền, KHÔNG xem nhãn của người thứ nhất; khi đủ nhãn, evaluate tính Cohen's kappa giữa hai người."""
import random
import sys

import numpy as np
import pandas as pd
import yaml

from download import ROOT
from llm import clean
from qa import load_refs

CLASSES, METHODS = ["positive", "mixed", "negative"], ["llm", "baseline", "floor"]
CI_NAMES = ["accuracy_ci_lo", "accuracy_ci_hi", "macro_f1_ci_lo", "macro_f1_ci_hi"]


def f1(y, p, c):
    """F1 của lớp c = 2TP / (số dự đoán c + số thật c)."""
    d = np.sum(p == c) + np.sum(y == c)
    return 2 * np.sum((y == c) & (p == c)) / d if d else 0.0


def macro_f1(y, p, classes=None):
    """Trung bình F1 trên các lớp có trong nhãn tay (classes: cố định danh sách lớp, dùng khi bootstrap)."""
    return float(np.mean([f1(y, p, c) for c in (np.unique(y) if classes is None else classes)]))


def metrics(y, p, full=False):
    """Các dòng (metric, value, n): accuracy, macro-F1; full=True thêm precision/recall/F1 từng lớp, n = số review thật của lớp."""
    rows = [("accuracy", np.mean(y == p), len(y)), ("macro_f1", macro_f1(y, p), len(y))]
    for c in np.unique(y) if full else []:
        tp, ns, npred = np.sum((y == c) & (p == c)), np.sum(y == c), np.sum(p == c)
        rows += [(f"precision_{c}", tp / npred if npred else 0.0, ns), (f"recall_{c}", tp / ns, ns), (f"f1_{c}", f1(y, p, c), ns)]
    return rows


def kappa(a, b):
    """Cohen's kappa: mức đồng thuận của a và b vượt trên mức ngẫu nhiên."""
    pe = sum(np.mean(a == c) * np.mean(b == c) for c in np.union1d(a, b))
    return float((np.mean(a == b) - pe) / (1 - pe)) if pe < 1 else 1.0


def boot(y, preds, B, seed):
    """Bootstrap B lần (mọi phương pháp dùng chung phép mẫu lại): CI 95% của accuracy, macro-F1 và chênh lệch llm - baseline."""
    idx, cls = np.random.default_rng(seed).integers(0, len(y), (B, len(y))), np.unique(y)  # lớp lấy từ cả mẫu, không đổi theo lần lấy lại
    st = {m: np.array([[np.mean(y[i] == p[i]), macro_f1(y[i], p[i], cls)] for i in idx]) for m, p in preds.items()}
    st["diff"] = st["llm"] - st["baseline"]
    return {m: np.percentile(v, [2.5, 97.5], axis=0).T.ravel() for m, v in st.items()}  # theo thứ tự CI_NAMES


def texts(cfg, ids):
    """Văn bản đã clean() của các review (cùng bước làm sạch với llm.py và baseline.py)."""
    rv = pd.read_csv(ROOT / "data" / "processed" / "reviews_clean.csv", usecols=["id", "comments"]).set_index("id")["comments"]
    return {i: clean(rv.get(i), cfg["llm"]["max_chars"]) for i in ids}


def make_sheet(cfg, path):
    """Tạo bảng nhãn tay: ưu tiên các review đánh dấu «Nhãn tay» trong Excel; không có thì lấy ngẫu nhiên (seed cố định) từ «Mẫu LLM»."""
    ref = load_refs(cfg)["review"]
    sample, marked = (ref.loc[ref[c].str.lower().eq("x"), "review_id"].astype(int).tolist() for c in ("Mẫu LLM", "Nhãn tay"))
    text = texts(cfg, sorted(marked or sample))
    ok = [i for i, t in text.items() if t]
    ids = random.Random(cfg["seed"]).sample(ok, min(cfg["eval"]["n_labels"], len(ok)))
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"review_id": ids, "comments": [text[i] for i in ids], "label": ""}).to_csv(path, index=False, encoding="utf-8-sig")


def second_annotator(E):
    """Cohen's kappa giữa hai người gán nhãn nếu tệp eval.labels_2 có đủ nhãn hợp lệ; không thì trả về []."""
    p2 = ROOT / E["labels_2"] if E.get("labels_2") else None
    if not p2 or not p2.exists():
        return []
    a = pd.read_csv(ROOT / E["labels"], dtype=str, usecols=["review_id", "label"], encoding="utf-8-sig")
    b = pd.read_csv(p2, dtype=str, usecols=["review_id", "label"], encoding="utf-8-sig")
    d = a.merge(b, on="review_id", suffixes=("_1", "_2"))
    for c in ("label_1", "label_2"):
        d[c] = d[c].fillna("").str.strip().str.lower()
    d = d[d["label_1"].isin(CLASSES) & d["label_2"].isin(CLASSES)]
    if len(d) < len(a):
        print(f"{p2.name}: mới có {len(d)}/{len(a)} nhãn hợp lệ, chưa tính kappa giữa hai người gán.")
        return []
    y1, y2 = d["label_1"].to_numpy(), d["label_2"].to_numpy()
    return [("hand_vs_hand2", "all", "agreement", np.mean(y1 == y2), len(d)),
            ("hand_vs_hand2", "all", "cohen_kappa", kappa(y1, y2), len(d))]


def make_second_sheet(E):
    """Tạo tệp cho người gán thứ hai: cùng review_id và văn bản, cột label để trống."""
    p2 = ROOT / E["labels_2"]
    if p2.exists():
        sys.exit(f"{p2} đã có, không ghi đè.")
    pd.read_csv(ROOT / E["labels"], dtype=str, encoding="utf-8-sig").assign(label="").to_csv(p2, index=False, encoding="utf-8-sig")
    print(f"Đã tạo {p2}: người thứ hai điền cột label, không xem {E['labels']}.")


def main(config_path):
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    E, proc = cfg["eval"], ROOT / "data" / "processed"
    path = ROOT / E["labels"]
    if not path.exists():
        make_sheet(cfg, path)
        sys.exit(f"Đã tạo {path}. Điền cột label ({'/'.join(CLASSES)}) rồi chạy lại.\nĐừng mở thẳng bằng Excel: nó làm hỏng review_id "
                 "19 chữ số (dùng VS Code, hoặc Excel > Data > From Text/CSV và đặt cột review_id là Text).")
    hand = pd.read_csv(path, dtype=str, usecols=["review_id", "label"], encoding="utf-8-sig")
    hand["label"] = hand["label"].fillna("").str.strip().str.lower()
    if hand["review_id"].duplicated().any() or not hand["label"].isin(CLASSES).all():
        sys.exit(f"{path.name}: review_id trùng, hoặc còn {int((~hand['label'].isin(CLASSES)).sum())} nhãn trống/ngoài {CLASSES}.")
    llm, base = (pd.read_csv(proc / f, dtype=str) for f in ("llm_results.csv", "baseline_results.csv"))
    llm["llm"], base["baseline"] = (x["sentiment"].where(x["status"] == "ok") for x in (llm, base))  # lỗi/rỗng: không có nhãn
    s = llm[["review_id", "llm", "language", "auto_generated"]].merge(base[["review_id", "baseline"]], on="review_id")
    if not hand["review_id"].isin(s["review_id"]).all():
        sys.exit("Có review_id nhãn tay không thuộc mẫu LLM (Excel hay làm hỏng ID 19 chữ số: mở lại tệp bằng VS Code).")
    d = hand.merge(s, on="review_id")
    if len(d) < E["n_labels"]:
        print(f"Cảnh báo: mới có {len(d)}/{E['n_labels']} nhãn tay.")
    y = d["label"].to_numpy()
    d["floor"] = pd.Series(y).mode()[0]  # mức sàn: luôn đoán lớp phổ biến nhất của nhãn tay
    preds = {m: d[m].fillna("none").to_numpy() for m in METHODS}  # không có nhãn = đoán sai
    for m in ("llm", "baseline"):
        print(f"{m}: lỗi/thiếu {int(d[m].isna().sum())}/{len(d)} review (tính là sai)")
    txt = pd.Series(list(texts(cfg, d["review_id"].astype(int)).values()), index=d.index)
    d["lang"] = np.where(d["language"].eq("en"), "en", "other")
    d["length"] = pd.cut(txt.str.len(), [-1, 150, 400, 1e9], labels=["short", "mid", "long"]).astype(str)
    d["auto"] = np.where(d["auto_generated"].eq("True"), "yes", "no")
    groups = {"all": np.ones(len(d), bool), **{f"{c}={v}": (d[c] == v).to_numpy()
                                               for c in ("lang", "length", "auto") for v in sorted(d[c].unique())}}
    ci, rows, n = boot(y, preds, E["bootstrap"], cfg["seed"]), [], len(y)
    for m, p in preds.items():
        for g, k in groups.items():
            rows += [(m, g, *r) for r in metrics(y[k], p[k], g == "all")]
        rows += [(m, "all", name, v, n) for name, v in zip(CI_NAMES, ci[m])]
    pt = lambda m: (np.mean(y == preds[m]), macro_f1(y, preds[m]))
    rows += [("llm_minus_baseline", "all", k, v, n) for k, v in zip(("accuracy", "macro_f1"), np.subtract(pt("llm"), pt("baseline")))]
    rows += [("llm_minus_baseline", "all", name, v, n) for name, v in zip(CI_NAMES, ci["diff"])]
    r1, r2 = preds["llm"] == y, preds["baseline"] == y  # bảng bất đồng: ai đúng, ai sai
    rows += [("llm_vs_baseline", "all", k, int(v.sum()), n) for k, v in
             {"both_right": r1 & r2, "only_llm_right": r1 & ~r2, "only_baseline_right": ~r1 & r2, "both_wrong": ~r1 & ~r2}.items()]
    both = s.dropna(subset=["llm", "baseline"])  # độ đồng thuận tính trên cả mẫu LLM, không cần nhãn tay
    a, b = both["llm"].to_numpy(), both["baseline"].to_numpy()
    rows += [("llm_vs_baseline", "full_sample", "agreement", np.mean(a == b), len(a)),
             ("llm_vs_baseline", "full_sample", "cohen_kappa", kappa(a, b), len(a))]
    rows += [(f"{m}_vs_hand", "all", "cohen_kappa", kappa(y, preds[m]), n) for m in ("llm", "baseline")]
    rows += second_annotator(E)
    pd.DataFrame(rows, columns=["method", "group", "metric", "value", "n"]).round(4).to_csv(proc / "eval_metrics.csv", index=False)
    conf = [pd.DataFrame({"method": m, "label": y, "pred": p}).value_counts().reset_index(name="count") for m, p in preds.items()]
    pd.concat(conf).to_csv(proc / "eval_confusion.csv", index=False)
    wrong = pd.DataFrame({m: preds[m] != y for m in ("llm", "baseline")}, index=d.index)
    err = d.assign(llm=preds["llm"], baseline=preds["baseline"], excerpt=txt.str[:200],
                   wrong_in=wrong.apply(lambda r: "+".join(m for m in wrong if r[m]), axis=1))[wrong.any(axis=1)]
    err[["review_id", "label", "llm", "baseline", "wrong_in", "lang", "length", "auto", "excerpt"]].to_csv(proc / "eval_errors.csv", index=False)
    print(f"{len(rows)} số đo, {len(err)} review sai -> eval_metrics.csv, eval_confusion.csv, eval_errors.csv")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cfg_path = args[0] if args else "configs/cape_town.yaml"
    if "--make-second-sheet" in sys.argv:
        with open(cfg_path, encoding="utf-8") as f:
            make_second_sheet(yaml.safe_load(f)["eval"])
    else:
        main(cfg_path)