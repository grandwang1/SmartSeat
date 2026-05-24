# SmartSeat MVP (Mock Data)

這個版本是可直接執行的 MVP，使用 mock data 完成：

- DB schema 建立 (SQLite)
- 學生名單含**組別**，先打散同組連續順序再排位
- 前端 **20×20 格線**框選教室、標記柱子等不可用座位（可附註）
- 座位安排：**梅花座**（任兩人不可上下左右相鄰；柱子不佔間隔）
- 依打散名單順序，從左上往右、換行後繼續排
- 匯出排位 CSV
- 產出可視化 HTML 座位圖
- 瀏覽器前端 DEMO（免安裝第三方套件）

## 專案檔案

- `schema.sql`: 資料庫結構
- `mock_students_80.csv`: 80 筆學生 mock 資料
- `mock_classroom_maps.json`: 3 種教室地圖 mock 資料
- `scripts/setup_project.py`: 初始化 DB 與匯入資料
- `scripts/run_assignment.py`: 執行排位
- `scripts/export_results.py`: 匯出排位結果 CSV
- `scripts/visualize_seatmap.py`: 產出 HTML 座位圖
- `main.py`: 一鍵跑完整流程
- `webapp.py`: 本地 DEMO Web Server

## 如何執行

在專案根目錄執行：

```bash
python3 main.py
```

完成後會得到：

- `smartseat.db`
- `outputs/exam_1_seating_assignments.csv`
- `outputs/exam_1_seatmap.html`

## 分步執行

```bash
python3 main.py --only setup
python3 main.py --only assign
python3 main.py --only export
python3 main.py --only visualize
```

## 啟動前端 DEMO

```bash
python3 webapp.py
```

然後開啟瀏覽器：

- `http://127.0.0.1:8000`

1. 在 20×20 格線**拖曳框選**教室大小（例如 8×10）
2. 切換「標記不可用座位」，點格線標記柱子並輸入附註
3. **貼上學生名單**（下載範本 CSV → Excel 編輯 → 整批複製貼上），或選用 mock 名單
4. 按「一鍵排位」、查看座位圖（學號在上、姓名在下）、下載 CSV
5. 可點「預覽打散後名單」確認同組不連續

若出現 `Address already in use`，可改用其他 port：

```bash
python3 webapp.py --port 8001
```

## 規則說明

- 名單：依 `group_name` 打散，避免相鄰兩列同組
- 排位：依打散後順序，座位由左上往右、逐列掃描
- 梅花座：已排學生的上下左右不可再排人
- 柱子：不可用格不參與間隔計算（柱子兩側可各坐一人）
- 座位顯示：學號在上、姓名在下

## 你接下來可擴充

- 新增更多限制條件（例如同組、同系、特需座位）
- 支援多考場拆分
- 改成 Web API / UI 版
