# Bài tập lớn cuối kỳ — Inside Airbnb (Nhóm 04, Cape Town)

**Môn học:** Lập trình xử lý dữ liệu (UET.DSE2049), học kỳ 1, năm học 2026–2027.

**Đề bài chính thức:** [Bài tập lớn Inside Airbnb](https://courses.iaidev.com/programming-for-data-processing/2627-1/projects/project_airbnb.html). Yêu cầu, thời hạn và rubric áp dụng theo thông báo mới nhất trên Canvas.

## Thông tin nhóm

- **Mã lớp:** DSE2049_4
- **Tên/mã nhóm:** Nhóm 04 — mã dữ liệu `DSE2049-C04-G04-cape-town`
- **Thành phố được phân công:** Cape Town (tiền tệ ZAR), 8 khu vực phân tích `A01`–`A08`
- **Bên đặt hàng phân tích:** TODO — nhóm điền
- **Bốn mốc dữ liệu:** `2025-09-28`, `2025-12-29`, `2026-03-30`, `2026-06-29`

| Họ tên | MSSV | GitHub username | Công việc phụ trách |
|---|---|---|---|
| Nguyễn Quốc Huy | 25022873 | 25022873-dev | TODO |
| Hoàng Ngọc Hưng | 25022878 | ProgrammingShell | TODO |
| Nguyễn Tiến Lĩnh | 25022914 | TODO | TODO |
| Khổng Nam Khánh | 25022898 | TODO | TODO |
| Lương Trường Giang | 25022840 | TODO | TODO |

Mỗi thành viên cần hiểu và giải thích được toàn bộ sản phẩm của nhóm.

## Cài đặt

Đã kiểm thử trên bản clone mới với **Python 3.12.3** (Linux); `.python-version` ghi đúng bản này (`3.12.3`).

```bash
git clone https://github.com/25022873-dev/2627---LTXLDL---Airbnb---GOAT.git
cd 2627---LTXLDL---Airbnb---GOAT
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # mọi thư viện đều ghim phiên bản
```

**Khoá API (chỉ cần khi phải gọi LLM):** nhà cung cấp Google Gemini, biến môi trường `GEMINI_API_KEY`. Đặt một trong hai cách:

```bash
export GEMINI_API_KEY="khoá-của-bạn"               # cách 1: biến môi trường
cp .env.example .env    # cách 2: điền khoá vào .env (đã nằm trong .gitignore, run_pipeline.py tự nạp)
```

Kết quả LLM của 1000 review «Mẫu LLM» đã có trong `data/processed/llm_cache.jsonl`. Khi model và prompt không đổi, pipeline dùng lại cache và **không cần khoá**. Không có khoá thì bước `llm` tự chuyển sang chỉ dùng cache (như `--skip-llm`) và không nạp SDK Gemini; nếu cache được tạo bởi model/prompt khác config hiện tại thì in cảnh báo. Đổi model hoặc sửa prompt mà muốn gán nhãn lại thì cần khoá.

**Tệp Excel phân công không cần thiết:** ID và khu vực của nhóm đã được cache ở `data/processed/refs/`. Chỉ khi xoá thư mục này mới phải đặt tệp Excel tại đường dẫn `ids_file` trong config.

## Chạy toàn bộ pipeline (một lệnh, gồm cả LLM)

```bash
python run_pipeline.py --config configs/cape_town.yaml
```

Lệnh này chạy lần lượt 7 bước dưới đây. Dữ liệu thô (khoảng 440MB) được tải về `data/raw/` (không commit). Tệp đã có và hợp lệ thì bỏ qua. Lần đầu mất khoảng 1–2 phút cộng thời gian tải; LLM dùng cache nên vài giây.

| Bước | Script | Việc làm | Ra |
|---|---|---|---|
| 1 | `src/download.py` | Tải `listings`, `calendar`, `reviews` của 4 mốc, kiểm tra gzip và cột khoá, thử lại 3 lần | `data/raw/<data_root>/<mốc>/*.csv.gz` |
| 2 | `src/qa.py` | Lọc ID của nhóm, ép kiểu, loại dòng trùng/xung đột khoá, gắn cờ, so với số liệu kỳ vọng, khảo sát cấu trúc cả 3 tệp (gồm calendar) | `data/processed/listings_clean.csv`, `reviews_clean.csv`, `rejected_*.csv`, `reports/qa_report.csv` |
| 3 | `src/llm.py` | Gán nhãn cảm xúc, ngôn ngữ và khía cạnh cho 1000 review «Mẫu LLM» bằng Gemini (theo lô, có cache, chạy dở chạy tiếp được) | `llm_cache.jsonl`, `llm_results.csv`, `llm_usage.json` |
| 4 | `src/baseline.py` | Đối chứng không dùng LLM: VADER và luật ngưỡng cố định | `baseline_results.csv` |
| 5 | `src/kpi.py` | 5 KPI theo khu vực và phường (tham số ở mục `kpi:` của YAML) | `kpi_*.csv` |
| 6 | `src/viz.py` | Vẽ 5 hình KPI (đúng dạng nhóm chọn) | `figures/fig1_*.png` … `fig5_*.png` |
| 7 | `src/evaluate.py` | Chấm LLM, baseline và mức sàn trên 100 nhãn tay (bootstrap CI), rồi vẽ hình đánh giá LLM | `eval_metrics.csv`, `eval_confusion.csv`, `eval_errors.csv`, `figures/fig6_llm_vs_baseline.png` |

`viz` chạy trước `evaluate` nên nếu tệp nhãn tay thiếu hoặc lỗi, 5 hình KPI vẫn được vẽ; pipeline chỉ dừng ở bước cuối.

Tuỳ chọn hay dùng:

```bash
python run_pipeline.py --config configs/cape_town.yaml --skip-llm     # không gọi API, chỉ dùng cache LLM
python run_pipeline.py --config configs/cape_town.yaml --from kpi     # chạy lại từ bước kpi trở đi (sau khi sửa KPI hoặc hình)
python run_pipeline.py --config configs/cape_town.yaml --only qa viz  # chỉ chạy vài bước
python src/qa.py configs/cape_town.yaml                                # mỗi bước vẫn chạy riêng được
```

Một bước lỗi thì pipeline dừng ngay, in tên bước và lệnh để chạy tiếp.

## Cấu hình

Mọi tham số nằm trong `configs/cape_town.yaml`:

- `data_root`, `snapshots`, `currency`, `group_code`: thành phố và 4 mốc (đổi mốc thì sửa danh sách `snapshots`).
- `qa.expected`: số liệu kỳ vọng của đề (1000 listing, 365000 dòng calendar, 5000 review, số loại phòng, số listing 0 review, số listing thiếu giá, 120–130 listing mỗi khu vực). `qa.iqr_k`: hệ số IQR cho cờ ngoại lai.
- `llm`: model (`gemini-3.1-flash-lite`), tên biến khoá, `batch_size`, `rpm`, `retries`, `max_chars`, danh sách khía cạnh, giá token dùng để ước tính chi phí (ghi ngày tra giá).
- `kpi`: `min_n` (nhóm dưới số quan sát này thì không báo cáo, mặc định 10) và `min_price_coverage` (mốc có dưới tỉ lệ này listing có giá bị loại khỏi KPI giá và doanh thu, mặc định 0.5). Mốc dùng cho KPI tiền tệ được chọn theo dữ liệu, không ghi cứng tháng trong mã.
- `baseline`: ngưỡng VADER, cố định trước, không chỉnh theo nhãn tay.
- `eval`: tệp nhãn tay, số nhãn, số lần bootstrap, tệp của người gán thứ hai (tuỳ chọn).
- `seed`: 42, dùng cho mọi bước ngẫu nhiên.

## Các tệp kết quả để đối chiếu

| Nhóm | Tệp |
|---|---|
| Tham chiếu | `data/processed/refs/{listing,review,area}_DSE2049-C04-G04-cape-town.csv` |
| Dữ liệu sau QA | `data/processed/listings_clean.csv` (4000 dòng = 1000 listing × 4 mốc), `reviews_clean.csv` (5000 review), `rejected_listings.csv`, `rejected_reviews.csv` |
| Báo cáo QA | `reports/qa_report.csv`: quy tắc, điều kiện, lý do, hành động, số dòng, trung vị trước/sau, kỳ vọng ok/error |
| LLM | `data/processed/llm_cache.jsonl`, `llm_results.csv`, `llm_usage.json` (token, tỉ lệ lỗi, ước tính chi phí cả thành phố) |
| Đối chứng | `data/processed/baseline_results.csv` |
| KPI | `data/processed/kpi_hibernation_rate.csv`, `kpi_median_price.csv`, `kpi_median_revenue.csv`, `kpi_median_occupied_nights.csv`, `kpi_net_sentiment.csv` |
| Đánh giá | `data/processed/eval_metrics.csv`, `eval_confusion.csv`, `eval_errors.csv` |
| Hình | `figures/fig1_hibernation_heatmap.png` (KPI 1), `fig2_median_price.png` (KPI 2), `fig3_median_revenue.png` (KPI 3), `fig4_net_sentiment.png` (KPI 4), `fig5_revenue_drivers.png` (KPI 5), `fig6_llm_vs_baseline.png` (đánh giá LLM, do `evaluate.py` vẽ) |

Chạy lại pipeline trên bản clone mới cho ra đúng các tệp này (thứ tự dòng cố định). `git status` sau khi chạy chỉ được thấy `data/raw/` bị bỏ qua.

## Định nghĩa KPI và biểu đồ

Mọi KPI được tính theo `analysis_area` (A01–A08) và `neighbourhood_cleansed`. Nhóm có dưới `kpi.min_n` (10) quan sát thì không báo cáo. KPI 2 và 3 chỉ dùng các mốc có ít nhất `kpi.min_price_coverage` (50%) listing có giá; với dữ liệu hiện tại là 09/2025, 03/2026, 06/2026 (mốc 12/2025 có 0% listing có giá).

| KPI | Mốc | Công thức | Biểu đồ |
|---|---|---|---|
| 1. Tỉ lệ "ngủ đông" | cả 4 | số listing có `estimated_occupancy_l365d = 0` / số listing có giá trị occupancy | heatmap vùng × mốc |
| 2. Giá trung vị theo khu vực | các mốc đủ giá | trung vị `price` khác rỗng trên mọi loại phòng gộp lại (`room_type = all`); hình dùng đúng số liệu này | chấm nối theo mốc, mỗi vùng một đường |
| 3. Doanh thu ước tính mỗi listing mỗi năm | các mốc đủ giá | trung vị `estimated_revenue_l365d`, tính cả listing có doanh thu 0 | chấm nối theo mốc, mỗi vùng một đường |
| 4. Cảm xúc ròng theo khu vực (LLM) | mẫu LLM | trung bình +1 (positive) / 0 (mixed) / −1 (negative) trên review có `status = ok`, không tính review tự động (`auto_generated`); kèm CI 95% bootstrap theo cụm listing và một dòng toàn mẫu (`level = all`) | chấm + khoảng tin cậy, kèm thanh thành phần nhãn |
| 5. Số đêm có khách trung vị (listing đang hoạt động) | cả 4 (hình dùng 3 mốc có giá) | trung vị `estimated_occupancy_l365d` trên các listing có occupancy > 0 | thanh lệch %: giá và số đêm trung vị của mỗi vùng lệch bao nhiêu % so với mức chung cùng mốc, 3 mốc cạnh nhau |

**Hình KPI 5 (nguồn doanh thu).** Doanh thu ≈ giá × số đêm, nên hình tách doanh thu của mỗi vùng thành hai phần: giá trung vị và số đêm có khách trung vị, mỗi phần tính bằng % lệch so với trung vị toàn mẫu cùng mốc. Chỉ tính listing có occupancy > 0, nên mức chung mốc 2026-06-29 là 1,655 ZAR/đêm (khác 1,683.5 của KPI 2, vốn tính mọi listing có giá) và 54 đêm/năm. Vùng xếp theo doanh thu trung vị (KPI 3) ở mốc cuối.

Nhãn bên phải là kết luận chung cho cả 3 mốc. Ở mỗi mốc, mỗi cột lệch quá +10% là cao, dưới −10% là thấp, còn lại là ngang mức chung; từ đó gán một nhãn: "giá + khách" (cả hai cao), "đông khách" (số đêm cao), "nhờ giá" (giá cao), "giá cao, ít khách", "ít khách", "giá thấp", "yếu cả hai" hoặc "ngang mức chung". Nhãn chung là nhãn xuất hiện ở đa số mốc (ít nhất 2/3), ghi kèm số mốc; nếu cả 3 mốc khác nhau thì ghi "không ổn định". Kết quả: A02 giá + khách (3/3); A06 giá + khách (2/3); A05 đông khách (2/3); A01 giá cao, ít khách (2/3); A07 ít khách (2/3); A03 ít khách (2/3); A04 và A08 yếu cả hai (3/3). Nhãn 2/3 của A06 và A07 nằm sát ngưỡng 10% nên kém chắc hơn. Số đêm là số 365 ngày trước mỗi mốc nên khung thời gian các mốc chồng nhau; "3/3" không phải 3 lần đo độc lập.

## Hạn chế đã biết (cần nêu trong báo cáo)

- **Giá thiếu ở mốc 2025-12-29:** `price` và `estimated_revenue_l365d` trống ở cả 1000 listing, nên quy tắc `kpi.min_price_coverage` tự loại mốc này và hai KPI tiền tệ chỉ dùng 3 mốc.
- **Calendar không dùng cho KPI:** calendar chỉ được khảo sát trong QA (đủ 365000 dòng, mỗi listing đủ 365 ngày; mốc 09/2025 có 7 cột, các mốc sau còn 5 vì bỏ cột giá). KPI lấp đầy dùng `estimated_occupancy_l365d`. Cột này Inside Airbnb ước tính từ số review, nên listing mới mở trong năm cũng có occupancy 0 và bị tính vào "hibernation".
- **Mùa vụ:** `price` là giá tại thời điểm chụp; mốc 03 là cuối mùa hè ở Cape Town nên giá cao hơn, không phải xu hướng tăng thuần.
- **Đánh giá LLM:** nhãn tay lệch mạnh (97 positive, 2 negative, 1 mixed). Accuracy: LLM 0.90, baseline 0.95, mức sàn (luôn đoán positive) 0.97. LLM gán "mixed" cho 10 review mà người gán coi là positive (có một lời chê nhỏ). Macro-F1 dựa vào 3 review không phải positive nên khoảng tin cậy rất rộng. Không được chỉnh prompt dựa trên chính 100 nhãn này (sẽ làm kết quả lạc quan giả).
- **Người gán thứ hai (khuyến nghị):** `python src/evaluate.py configs/cape_town.yaml --make-second-sheet` tạo `data/samples/hand_labels_2.csv` cùng 100 review, cột `label` trống. Người thứ hai tự điền mà không xem nhãn của người thứ nhất; lần chạy sau `evaluate.py` tự tính Cohen's kappa giữa hai người (`hand_vs_hand2` trong `eval_metrics.csv`).
- **Không mở tệp nhãn tay bằng Excel:** Excel làm hỏng `review_id` 19 chữ số (thành `7.74432E+17`). Dùng VS Code, hoặc Excel > Data > From Text/CSV và đặt cột `review_id` là Text.

## Cấu trúc repo

```
run_pipeline.py          # một lệnh chạy cả pipeline
configs/cape_town.yaml   # mọi tham số
src/                     # common (dùng chung), download, qa, llm, baseline, kpi, viz, evaluate
data/raw/                # dữ liệu thô tải về (không commit)
data/processed/          # dữ liệu sau QA, kết quả LLM, KPI, đánh giá, refs/
data/samples/            # nhãn tay
reports/qa_report.csv    # báo cáo QA
figures/                 # hình cho báo cáo
AI_USAGE.md              # minh bạch việc dùng AI
```

## Nộp bài

Sau khi hoàn tất sản phẩm, cập nhật báo cáo và đẩy commit cuối lên GitHub, tạo tag theo đề bài:

```bash
git tag final
git push origin final
git rev-parse final      # ghi SHA này vào báo cáo
```

Thời hạn, cách đăng ký và lịch vấn đáp xem tại đề bài và Canvas.
