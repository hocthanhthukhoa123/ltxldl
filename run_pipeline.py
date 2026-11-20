"""Chạy toàn bộ pipeline bằng một lệnh: python run_pipeline.py --config configs/cape_town.yaml [tuỳ chọn]

Thứ tự: download -> qa -> llm -> baseline -> kpi -> viz -> evaluate (mỗi bước là một script trong src/).
viz vẽ 5 hình KPI trước; evaluate chấm trên nhãn tay rồi vẽ hình 6, nên lỗi ở nhãn tay không chặn các hình KPI.
Khoá API: đọc biến môi trường GEMINI_API_KEY (tên đặt ở llm.api_key_env); có tệp .env ở gốc repo thì nạp
tự động (không ghi đè biến đã có). Review đã có trong data/processed/llm_cache.jsonl thì không gọi lại API;
không có khoá thì bước llm tự dùng cache.

Tuỳ chọn:
  --config YAML      tệp cấu hình (mặc định configs/cape_town.yaml; vẫn nhận dạng cũ: python run_pipeline.py YAML)
  --skip-llm         không gọi API (không cần khoá): dùng kết quả trong cache
  --from BƯỚC        bắt đầu từ bước này (ví dụ --from kpi khi chỉ sửa KPI/hình)
  --only BƯỚC ...    chỉ chạy các bước liệt kê
Dừng ngay khi một bước lỗi (mã thoát khác 0) và in tên bước đó."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["download", "qa", "llm", "baseline", "kpi", "viz", "evaluate"]


def load_dotenv(path):
    """Nạp KEY=VALUE từ .env (bỏ dòng trống/chú thích, bỏ dấu nháy); biến đã đặt trong shell được giữ nguyên."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            key, val = key.removeprefix("export ").strip(), val.strip().strip("'\"")
            if val:
                os.environ.setdefault(key, val)


def main():
    ap = argparse.ArgumentParser(description="Chạy toàn bộ pipeline Inside Airbnb.")
    ap.add_argument("--config", help="tệp YAML, ví dụ configs/cape_town.yaml")
    ap.add_argument("config_pos", nargs="?", metavar="config", help=argparse.SUPPRESS)  # dạng cũ: tham số vị trí
    ap.add_argument("--skip-llm", action="store_true", help="không gọi API, chỉ dùng cache LLM")
    ap.add_argument("--from", dest="start", choices=STEPS, default=STEPS[0], help="bắt đầu từ bước này")
    ap.add_argument("--only", nargs="+", choices=STEPS, help="chỉ chạy các bước này")
    a = ap.parse_args()
    if a.config and a.config_pos and a.config != a.config_pos:
        ap.error("chỉ đưa một tệp cấu hình: --config hoặc tham số vị trí")
    a.config = a.config or a.config_pos or "configs/cape_town.yaml"
    load_dotenv(ROOT / ".env")
    steps = a.only or STEPS[STEPS.index(a.start):]
    config = str((ROOT / a.config).resolve()) if not Path(a.config).is_absolute() else a.config
    t0 = time.monotonic()
    for step in [s for s in STEPS if s in steps]:  # luôn đúng thứ tự phụ thuộc
        cmd = [sys.executable, str(ROOT / "src" / f"{step}.py"), config]
        if step == "llm" and a.skip_llm:
            cmd.append("--skip-llm")
        print(f"\n=== [{step}] {' '.join(cmd[1:])}", flush=True)
        t = time.monotonic()
        code = subprocess.call(cmd, cwd=ROOT)
        if code:
            sys.exit(f"\nDừng ở bước '{step}' (mã thoát {code}). Sửa lỗi rồi chạy lại: python run_pipeline.py --config {a.config} --from {step}")
        print(f"=== [{step}] xong sau {time.monotonic() - t:.1f}s", flush=True)
    print(f"\nHoàn tất {len(steps)} bước sau {time.monotonic() - t0:.1f}s. Kết quả: data/processed/, reports/, figures/")


if __name__ == "__main__":
    main()
