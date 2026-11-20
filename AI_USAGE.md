# AI_USAGE.md

## Công cụ đã dùng (vào việc gì)
Claude: viết code; hỗ trợ lựa chọn các cột cần lọc và gắn cờ trong qa.py dựa trên 5 KPI nhóm đề ra

## Prompt then chốt (5-10): bước nào, vào tệp nào

- prompt cho download.py:

    write me download.py that do the following:
        build URLs formatted as in the excel file: baseURL/snapshots/data/file
        build path so it stay in data/raw/data_root/snapshots/file
        check if files are corrupted and check key columns
        fetch those builts URLs and download the files
        If a file downloads unsuccessfully, retry up to 3 times
        Do not download neighbourhoods.geojson.
        No matter what kind of mistake the download run into, just let it retry.

- prompt cho qa.py:
    write me qa.py that do the following:

1. listings id, reviews id: Cast to integer. Rows with a null key, exact duplicates or key conflicts are removed. Only the group's IDs are read.
2. neighbourhood_cleansed, room_type: Cast to text. Empty becomes NA. Flagged if the text looks mis-encoded.
3. analysis_area: Merged in from the reference sheet. Flagged if a listing has no area.
4. price: Currency symbol and commas stripped, then cast to float. Empty, sentinel, unparseable or below 0.01 becomes NA. Zeros are counted before blanking. IQR outlier flag on log1p, per room type.
5. estimated_occupancy_l365d: Cast to float. Outside 0–365 becomes NA. Zero is kept.
6. estimated_revenue_l365d: Cast to float (or the price type). Below 0 becomes NA. Zero is kept. Optional IQR flag.
7. number_of_reviews: Cast to integer, must be ≥ 0.
8. latitude, longitude: Cast to float, range-checked. Flagged if outside the area's box.
9. reviews listing_id: Cast to integer. Flagged if it's an orphan or differs from the sheet.
10. reviews comments: Cast to text. Empty becomes NA (the LLM stage marks it empty). Encoding flag.

- prompt cho llm.py:

write me llm.py that has the following functions:

1. PROMPT, HINTS: The instructions sent to Gemini: the sentiment rules, allowed aspects with short hints, language code, and a guard that treats review text as data, never as commands. It includes examples, one of them an injection attempt.
2. AUTO: A pattern that spots auto-generated reviews (host cancellations and similar) so they can be flagged.
3. make_schema: Defines the structured output: sentiment limited to positive, mixed or negative, a language code, and aspects limited to your configured names, each positive or negative.
4. clean: Strips HTML, collapses whitespace and truncates to the character limit. baseline.py and evaluate.py reuse it, so every method sees the same text.
5. label: Sends one batch to the API. It paces calls to the rate limit, retries on rate-limit or server errors with growing waits, stops immediately on errors retrying can't fix, and re-sends any items missing or invalid in the answer. It also counts tokens.
6. main: Runs everything else. It loads the sample, builds the cache key from the model and a hash of the prompt, and reads the cache so finished reviews aren't re-sent. It also processes the remaining reviews in batches, writes each result to the cache immediately, and aborts cleanly if the API keeps failing. At the end it writes llm_results.csv and llm_usage.json with the whole-city cost estimate.

- prompt cho kpi.py:
 here the list of KPIs format as KPI: source: Formula

    Hibernation rate: all 4 snashots: listings with occupancy = 0 / listings with non-missing occupancy, per area
    Median price: Sep, Mar, Jun: median of non-missing price, per area * room type
    Median revenue per listing: Sep, Mar, Jun: median of non-missing estimated_revenue_l365d, zeros included, per area
    Median occupied nights: all 4 snapshots: median of occupancy over listings with occupancy > 0, per area
    Net sentiment: LLM sample: mean of +1 (positive), 0 (mixed), −1 (negative) over reviews with status ok, per area
write me kpi.py according to that.

- prompt cho baseline.py:
write me baseline.py using vaderSentiment, here the functions you need and their purposes:

1. VADER, CLAUSE: VADER is the sentiment scorer, with no model training and no network. CLAUSE is a pattern that splits a review into sentences and contrasting clauses, so praise and complaints can be scored separately.
2. score: Returns VADER's overall score for a piece of text, from −1 to +1.
3. label: Turns a review into positive, mixed or negative. It says mixed if some clause is clearly positive and another clearly negative. Otherwise it compares the whole-text score to a threshold, and falls back to a default label when there's no signal. A text with no scoreable clause no longer crashes it.
4. main: Loads the same "Mẫu LLM" sample as llm.py, cleans each review with the same clean, labels it, and writes baseline_results.csv with review_id, sentiment and status. Empty text gets status empty.
keep the code as short as under 50 lines

- prompt cho evaluate.py:
    write me evaluate.py
        Functions and purposes:

        f1, macro_f1: F1 for one class, and the average over the classes that actually appear in your hand labels.
        metrics: Accuracy and macro-F1 for a group of reviews. For the full sample it also gives precision, recall and F1 per class, with the real class counts.
        kappa: Cohen's kappa, the agreement between LLM and baseline beyond chance.
        make_sheet: If the hand-label file doesn't exist, it draws a random sample from the "Mẫu LLM" reviews, fixed by the seed, writes it with an empty label column and stops so you can fill it in.
## AI sai ở đâu (ví dụ thật)
1. qa.py, quy tắc lỗi mã hoá: Claude đặt `\ufffd` trong chuỗi thô (raw string). Với pandas 3 (chuỗi dùng Arrow) mã báo `ArrowInvalid` và dừng. Phát hiện khi cho Claude chạy thử trên dữ liệu giả; đã sửa thành chuỗi thường.
2. qa.py, cờ ngoại lai của doanh thu: quy tắc IQR trên log1p gắn cờ "ngoại lai" cho mọi listing có doanh thu 0 (14-16% listing trên dữ liệu thật, 46/480 trong bản thử). Số 0 là giá trị hợp lệ và là tử số của KPI "ngủ đông". Đã sửa: bỏ số 0 trước khi tính tứ phân vị.
3. evaluate.py và nhãn tay: Excel làm hỏng review_id 19 chữ số (ký hiệu khoa học). Mã cũ không phát hiện, chỉ in "thiếu/lỗi 78/100" làm số liệu trông vô lý. Nhóm đối chiếu tệp nhãn tay với tệp gốc, khôi phục ID từ tệp gốc. Mã mới kiểm tra ID và dừng với thông báo rõ.
4. Đề bài: Claude nói đề "bắt buộc" xử lý calendar trong QA. Nhóm hỏi lại "đề nói ở đâu", Claude đọc lại trang đề và thừa nhận đề chỉ yêu cầu khảo sát cấu trúc từng tệp và ghi vào phần QA.
5. kpi.py, mốc cho KPI giá: lần sửa đầu của Claude chỉ chuyển danh sách tháng 09, 03, 06 từ code sang YAML. Nhóm chỉ ra rằng như vậy vẫn là hard-code và sẽ sai khi chạy data set khác. Đã thay bằng quy tắc theo dữ liệu: mốc nào có dưới 50% listing có giá (kpi.min_price_coverage) thì bị loại khỏi KPI giá và doanh thu. Chạy thật vẫn loại đúng mốc 12/2025 (0% listing có giá).
6. run_pipeline.py, tham số --config: bản của Claude dùng đường dẫn vị trí, còn đề dùng --config. Lệnh theo đề chỉ chạy vì mã bỏ qua cờ và lấy tham số kế tiếp. --config=x.yaml bị bỏ qua mà không báo gì. Nhóm phát hiện khi đối chiếu với đề, rồi sửa bằng argparse.
7. Cờ auto_generated: mã do Claude viết có tính cờ này nhưng không nơi nào dùng. Review tự động vẫn bị tính vào KPI cảm xúc ròng. Cả bản code gốc lẫn lần rà soát đầu của Claude đều bỏ sót. Nhóm phát hiện và thêm bộ lọc trong kpi.py (và viz.py dùng chung hàm scored_reviews nên biểu đồ tự khớp).
## Nhóm kiểm chứng thế nào
- Chạy lại toàn bộ quy trình trên dữ liệu thật sau mỗi lần sửa, và đọc các tệp kết quả (qa_report.csv, kpi_*.csv, eval_*.csv) thay vì tin lời AI.
- Trước khi chọn KPI, đo % thiếu của từng cột ở cả 4 mốc và kiểm tra cột estimated_* trong tệp thô. Nhờ đó biết price và doanh thu trống 100% ở mốc 12/2025, nên KPI giá và doanh thu chỉ lấy 3 mốc.
- Cho AI chạy thử trên dữ liệu giả có cài sẵn lỗi (dòng trùng, khoá rỗng, giá "N/A", occupancy > 365, doanh thu âm, toạ độ ngoài hộp, lỗi mã hoá): bắt được lỗi 1 và 2 ở trên.
- Tự gán 100 nhãn tay (không dùng AI) rồi chấm LLM và baseline VADER, kèm khoảng tin cậy bootstrap.
- Khi AI khẳng định điều gì về đề bài, đối chiếu lại với trang đề.
## Đợt rà soát 18/11/2026 (Claude, claude.ai)

**Công cụ, vào việc gì:** Claude đọc toàn repo (cả 3 nhánh), chạy lại pipeline trên bản clone mới, liệt kê lỗi; sau đó viết `run_pipeline.py`, viết lại `src/viz.py`, sửa `qa.py`, `llm.py`, `kpi.py`, `evaluate.py`, viết lại README.

**Prompt then chốt:**
- "đọc repo git này (bài cuối kì của nhóm 4) và phân tích lỗi cũng như là các việc cần làm" (rà soát toàn repo).
- "run_pipeline.py: it doesn't exist yet, and it's required. README: it must match the new commands. and fix all detected problems" (dẫn tới các thay đổi dưới đây).
- Gửi ảnh mẫu 5 biểu đồ KPI của nhóm và công thức nhóm màu doanh thu cho KPI 5.
- "thay hình đó cho hình cũ ở kpi5": thay bubble bằng biểu đồ thanh lệch % giá và số đêm theo 3 mốc (theo ảnh mẫu của nhóm).
- Hỏi nhãn cột cuối nên là kết luận chung cho cả 3 mốc không, cách nào hợp lý nhất; nhóm chốt cách đa số 2/3 mốc, ghi kèm số mốc, không có đa số thì ghi "không ổn định".

**Thay đổi theo từng tệp:**
- `run_pipeline.py` (mới): một lệnh chạy 7 bước, nạp `.env`, có `--skip-llm`, `--from`, `--only`, dừng khi một bước lỗi.
- `src/viz.py` (viết lại): 5 hình KPI theo đúng dạng biểu đồ nhóm chọn (heatmap ngủ đông, hai biểu đồ chấm nối cho giá và doanh thu, cảm xúc ròng kèm thành phần nhãn, KPI 5 ban đầu là bubble với nhóm màu D = (Tmax − Tmin)/3, sau thay bằng biểu đồ thanh lệch % "nguồn doanh thu" theo mẫu của nhóm) và 1 hình LLM vs baseline; bảng màu đã kiểm tra mù màu, nền sáng.
- `src/kpi.py`: KPI giá có thêm mức mọi loại phòng (`room_type = all`) bên cạnh từng loại phòng, vì hình của nhóm dùng mức này; net sentiment có thêm dòng toàn mẫu.
- `src/qa.py`: khảo sát cấu trúc cả 3 tệp (số dòng/cột, calendar đủ 365000 dòng và 365 ngày/listing); sắp xếp ổn định (`kind="stable"`) để `reviews_clean.csv` giống hệt nhau mỗi lần chạy; cờ ngoại lai IQR tính theo mốc × loại phòng (trước đây gộp 4 mốc, một listing bị đếm 4 lần).
- `src/llm.py`: thêm `--skip-llm`; ước tính chi phí không còn bắt buộc phải có tệp thô.
- `src/kpi.py`: net sentiment có CI 95% bằng bootstrap theo cụm listing.
- `src/evaluate.py`: bootstrap macro-F1 cố định danh sách lớp (trước đây đổi theo từng lần lấy lại); hỗ trợ người gán thứ hai (`--make-second-sheet`, Cohen's kappa giữa hai người).

**AI sai ở đâu (ví dụ thật):**
- Bản `viz.py` đầu tiên đặt nhãn khu vực ở góc hộp; vì các hộp chồng nhau, nhãn A05/A06/A07 đè lên nhau, A05 bị che mất. Phát hiện khi mở ảnh; đã sửa: nhãn đặt ở trung vị toạ độ listing, nhãn sát nhau được đẩy ra và nối bằng đường dẫn.
- Hình doanh thu ban đầu vẽ 3 mốc trên cùng một hàng; A07/A08 có doanh thu 03/2026 gần bằng 06/2026 nên chấm sau che mất chấm trước, trông như thiếu dữ liệu. Đã kiểm tra lại `kpi_median_revenue.csv` (đủ số liệu) rồi sửa: lệch dọc theo mốc và dùng hình dấu khác nhau.

- Khi nhóm gửi công thức ngưỡng KPI 5, cận trên nhóm 2 ban đầu được viết là Tmax + D (khiến nhóm 3 luôn rỗng). Claude hỏi lại thay vì tự sửa; nhóm xác nhận cận đúng là Tmax − D.

- Ảnh mẫu biểu đồ "nguồn doanh thu" của nhóm gán A03 là "nhờ giá" (giá chỉ +10,2% nhưng số đêm −22%) và A07 là "trung bình" (số đêm −11%, ngoài dải ±10%) vì quy tắc chỉ xét cột vượt +10%. Khi đưa vào `viz.py`, nhãn được xét cả hai chiều: A03 "giá cao, ít khách", A07 "ít khách".

**Kiểm chứng:** clone mới nhánh, cài `requirements.txt` trên Python 3.12, chạy `python run_pipeline.py` hai lần và so sánh tệp kết quả (giống hệt nhau); số liệu kỳ vọng của QA đều `ok`; mở từng hình để kiểm tra chữ đè và dữ liệu thiếu. Prompt LLM không bị sửa (cache vẫn khớp, không gọi lại API) và không chỉnh gì dựa trên 100 nhãn tay.

## Đợt hợp nhất 20/11/2026 (Claude, claude.ai): đưa cải tiến của nhánh HNH-RfS vào repo nộp bài

**Công cụ, vào việc gì:** Claude so sánh repo nộp bài với nhánh `HNH-RfS` (refactor của Hưng ngày 20/11, tách từ cùng commit 7bc270b), chạy thật cả hai, rồi chuyển các cải tiến của `HNH-RfS` sang đây; những phần nhánh này làm tốt hơn thì giữ nguyên.

**Prompt then chốt:**
- Gửi bảng so sánh hai repo và danh sách 7 cải tiến cần chuyển, kèm quyết định của nhóm: KPI giá trung vị tính trên mọi loại phòng gộp lại (`room_type = all`) và hình dùng mức này; khoảng tin cậy cảm xúc ròng và cách tính macro-F1 trong từng lần bootstrap giữ bản của repo này (của Giang).
- Claude hỏi lại: CSV giá có giữ thêm từng loại phòng không (nhóm chọn chỉ giữ `all`), đẩy thẳng lên `main` hay qua PR (nhóm chọn `main`), phạm vi sửa thêm (nhóm chọn sửa `.python-version`).

**Thay đổi theo từng tệp:**
- `src/common.py` (mới, lấy từ HNH-RfS): đường dẫn, đọc config, `load_refs`, `clean`, `sample_ids`, `review_texts`, điểm vào dòng lệnh dùng chung; các bước khác bỏ code lặp.
- `run_pipeline.py`: nhận `--config` như đề (vẫn nhận dạng cũ), thứ tự mới `... kpi -> viz -> evaluate`.
- `src/kpi.py`: mục `kpi:` trong YAML (`min_n`, `min_price_coverage`); bỏ `PRICE_MONTHS` ghi cứng, chọn mốc giá theo dữ liệu (`price_snapshots`, `viz.py` dùng chung); `median_price` chỉ còn `room_type = all`; bỏ review tự động khỏi KPI cảm xúc (`scored_reviews`, `viz.py` dùng chung). Giữ CI bootstrap theo cụm listing và dòng toàn mẫu.
- `src/llm.py`: không có khoá thì tự dùng cache, SDK Gemini chỉ nạp khi gọi API, cảnh báo khi cache tạo bởi model/prompt khác; review thiếu trong dữ liệu coi là rỗng thay vì dừng.
- `src/qa.py`: mốc thiếu cột thì thêm cột rỗng (`reindex`) thay vì lỗi. Giữ khảo sát calendar, cờ ngoại lai theo mốc × loại phòng, sắp xếp ổn định.
- `src/viz.py`, `src/evaluate.py`: `viz` vẽ 5 hình KPI; `evaluate` vẽ hình 6 sau khi có số đo, nên lỗi nhãn tay không chặn hình KPI. Chú thích hình 5 và 6 tính từ dữ liệu thay vì ghi cứng ("mốc 12/2025", "97% positive"). Giữ bootstrap macro-F1 cố định danh sách lớp và hỗ trợ người gán thứ hai.
- `.python-version`: `3.12.3` (dạng 3.x.y, đúng bản đã chạy kiểm thử).

**AI sai ở đâu (ví dụ thật):**
- Khi sửa chú thích hình 5 cho khỏi ghi cứng mốc, Claude ghép chuỗi bị thừa một dấu nháy làm `viz.py` lỗi cú pháp; phát hiện ngay khi đọc lại đoạn code trước khi chạy và sửa.

**Kiểm chứng:** chạy `python run_pipeline.py --config configs/cape_town.yaml` trên Python 3.12.3, so với kết quả trước khi sửa: các số KPI, kết quả LLM, baseline và đánh giá giữ nguyên; chỉ `kpi_median_price.csv` bớt các dòng từng loại phòng (dòng `all` giống từng byte), `llm_usage.json` thêm `city_snapshot`, hình 2, 4, 5 đổi chú thích. Chạy lại lần hai: `git status` sạch. Thử thêm trên bản sao: không có khoá API, bộ mốc khác (2025-06-25 đến 2026-03-30), một mốc thiếu cột `estimated_revenue_l365d`, cache thiếu 5 review, xoá tệp nhãn tay (5 hình KPI vẫn được vẽ, pipeline dừng ở `evaluate` với hướng dẫn rõ).
