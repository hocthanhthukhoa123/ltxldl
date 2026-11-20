"""Phương pháp đối chứng không LLM (VADER): python src/baseline.py configs/cape_town.yaml
Ra: data/processed/baseline_results.csv (review_id, sentiment, status). Ngưỡng đọc từ mục `baseline:` của YAML, cố định trước, không chỉnh trên nhãn tay."""
import re

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from common import PROC, review_texts, run

VADER = SentimentIntensityAnalyzer()  # từ điển có sẵn: không huấn luyện, không cần mạng
CLAUSE = re.compile(r"(?<=[.!?])\s+|\b(?:but|however|although|though|except)\b", re.I)  # tách câu (giữ dấu câu) và mệnh đề đối lập


def score(text):
    """Điểm tổng hợp (compound) của VADER, từ -1 đến +1."""
    return VADER.polarity_scores(text)["compound"]


def label(text, B):
    """mixed nếu có mệnh đề khen rõ (>= mixed_min) và mệnh đề chê rõ (<= -mixed_min); không thì so điểm cả văn bản với thr."""
    s = [score(c) for c in CLAUSE.split(text) if c.strip()]  # không có mệnh đề nào chấm được: s rỗng, không lỗi
    if max(s, default=0) >= B["mixed_min"] and min(s, default=0) <= -B["mixed_min"]:
        return "mixed"
    t = score(text)
    return "positive" if t >= B["thr"] else "negative" if t <= -B["thr"] else B["default"]  # không có tín hiệu: nhãn mặc định


def main(cfg):
    texts = review_texts(cfg)  # cùng mẫu «Mẫu LLM» và cùng clean() như llm.py; review không có -> rỗng
    rows = [{"review_id": i, "sentiment": label(t, cfg["baseline"]) if t else None, "status": "ok" if t else "empty"}
            for i, t in texts.items()]
    out = pd.DataFrame(rows)
    out.to_csv(PROC / "baseline_results.csv", index=False)
    print(f"{len(out)} review -> baseline_results.csv; {out['sentiment'].value_counts().to_dict()}")


if __name__ == "__main__":
    run(main)
