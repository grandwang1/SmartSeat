# SmartSeat

考場智慧排座系統。透過瀏覽器介面，依序完成教室設定、名單上傳、排除人員、一鍵排位，自動產出梅花座配置並匯出 Excel 座位表。

## 功能特色

- **互動式教室編輯器** — 拖曳框選教室範圍，標記黑板、門、不可用座位
- **CSV 彈性上傳** — 支援任意欄位順序，透過欄位對應介面自行指定；姓名可合併「姓＋名」兩欄
- **排除名單** — 依組別整批排除，或逐一勾選；支援組別欄位為空的人員（如助教、老師），以「無組別」顯示
- **多選分組篩選** — 各名單區塊均提供多選 checkbox 下拉選單，快速篩選特定組別
- **梅花座排位** — 打散同組連續順序後，確保相鄰上下左右無同組人員；黑板、柱子等結構物不佔間隔
- **排位結果明細** — 顯示已安排／未安排名單，每頁 20 筆分頁瀏覽
- **匯出 Excel 座位表** — 含色彩標示，黑板、門、排數標籤以 16pt 粗體顯示

## 系統需求

- Python 3.9+
- 標準函式庫（無需安裝第三方套件）

## 啟動方式

```bash
python3 webapp.py
```

開啟瀏覽器前往：

```
http://127.0.0.1:8000
```

若 port 被佔用：

```bash
python3 webapp.py --port 8001
```

## 使用流程

**步驟 1 — 設定教室**

在 20×20 格線上拖曳框選教室範圍，再切換「標記不可用座位」標記黑板、門等位置。

**步驟 2 — 學生名單**

上傳 CSV 檔案，透過欄位對應介面指定組別、學號、系級、姓名欄位。套用後可依組別排除不需排座位的人員（如助教、老師），確認後預覽最終名單。

**步驟 3 — 執行排位**

填入考試名稱與考場名稱，按「一鍵排位」完成自動排座。可先點「預覽打散後名單」確認同組不連續。

**步驟 4 — 排位結果**

預覽座位圖，查看已安排／未安排學生名單，下載含色彩的 Excel 座位表或 PDF 報表。

## 專案結構

```
webapp.py                    # Web Server（Python 標準 http.server）
smartseat_db.py              # SQLite 資料庫操作
smartseat_allocator.py       # 梅花座排位演算法
smartseat_roster_parse.py    # CSV 名單解析與欄位對應
smartseat_seatmap_style.py   # 座位圖 HTML 渲染與樣式
smartseat_student_shuffle.py # 學生名單打散邏輯
schema.sql                   # 資料庫 Schema
app/static/
  index.html                 # 前端介面
  app.js                     # 前端互動邏輯（Vanilla JS）
  style.css                  # 樣式
scripts/
  setup_project.py           # 初始化 DB
  run_assignment.py          # 執行排位
  export_results.py          # 匯出 Excel 座位表
  export_report.py           # 匯出 PDF 報表
  visualize_seatmap.py       # 產出 HTML 座位圖
mock_students_120.csv        # 120 筆示範學生資料
```

## 排位規則

- 名單依 `group_name` 打散，避免相鄰順序同組
- 排位由左上往右、逐列掃描
- 梅花座：已排學生的上下左右不可再排人
- 黑板、門、柱子等結構物不佔梅花座間隔（兩側可各坐一人）
- 排數標籤僅計算有學生的列與欄
