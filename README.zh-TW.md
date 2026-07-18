# Prism

[English README](./README.md)

Prism 是一個只在本機執行的時間點市場研究工作台。它從 Massive
下載真實的調整後美股日線，存入 DuckDB，計算有版本的 metrics，並執行
walk-forward 研究回測。

Prism 不會下單，也沒有建立、修改或取消券商訂單的功能。

## 資料真實性原則

- 執行時不存在 demo 市場資料。
- 空資料庫就顯示空畫面。
- API 或網路失敗時不會補入範例價格、分數、預測或回測。
- Massive 回傳 HTTP 429 時立即停止該批同步，不重試，也不再請求剩餘股票。
- Codex／ChatGPT 額度用完時也立即停止研究，不重試。
- 已儲存的真實資料可離線查閱，但會顯示觀察日與可用時間。
- Massive key 只存在本機 FastAPI 程序，不會傳到瀏覽器或 Codex 子程序。

## 安裝與啟動

```bash
make setup
cp .env.example .env
```

在不會提交到 Git 的 `.env` 設定：

```dotenv
MASSIVE_API_KEY=你的金鑰
PRISM_AI_PROVIDER=codex_cli
PRISM_CODEX_MODEL=gpt-5.6-sol
PRISM_CODEX_TIMEOUT_SECONDS=300
PRISM_DATABASE_PATH=./data/prism.duckdb
```

AI 研究不需要 OpenAI Platform API key。先在本機終端確認：

```bash
codex login status
```

若尚未登入就執行 `codex login`。Codex CLI 未安裝、未登入或額度用完時，
世界事件、公司事件與信心研究會保持空白；不影響 Massive 市場日線、
metrics 與回測。

Prism 預設明確固定使用 `gpt-5.6-sol`，避免 Codex 推薦模型改變時讓
研究結果無意間換模型。只有刻意比較模型時才使用
`PRISM_CODEX_MODEL` 覆寫。

啟動本機 API 與 Web：

```bash
make dev
```

開啟終端顯示的本機網址。介面右上角可切換中文與 English。
Web 介面透過同源本機 API route 連到 `127.0.0.1:8000`；Massive key
始終只由 FastAPI 讀取，不會進入瀏覽器。

## 自訂資料與時間區間

在「資料與管線」輸入股票代碼、開始日期與結束日期。Prism 會保留：

- 請求區間
- Massive 實際回傳區間
- 觀察時間
- 資料可用時間
- 同步結果與失敗訊息

如果 Massive 方案截短歷史區間，Prism 會顯示實際覆蓋缺口，不會補值。

「區間 Metrics」頁面提供日期欄位及雙端拖曳時間軸。選定範圍後會計算：

- 5 日與 20 日報酬
- 20 日年化已實現波動
- 20 日成交量 z-score
- 距離 20 日均線
- 60 日回撤

同時會用該區間內較早的相似 metric 狀態，建立 10、30、90
交易日的歷史類比 forecast，回報中位數、10–90% 區間、正報酬比例與樣本數。
少於十個合格樣本時不產生 forecast 數值。

這些結果僅供研究與回測設計，不是投資建議或交易指令。

## 世界事件、公司事件與信心追蹤

「世界與公司事件」只在你按下更新時呼叫本機 `codex exec --search`。
Codex 在隔離的唯讀暫存目錄非互動執行，不會收到 Massive key。Prism
驗證 JSON Schema、搜尋紀錄與來源 URL，並保存來源、模型、prompt 版本、
run 狀態與用量。缺登入、缺來源、網路失敗或 quota 用完時都不會補入
預設事件。

在「區間 Metrics」完成計算後，可以針對 90 個交易日 forecast 視窗研究
財報與重大發表。每個事件會標記落在哪些 10／30／90 日 horizon。事件發生
後可再查詢正式結果；Prism 使用本機 Massive 日線計算 1／5／20 個交易日
報酬、相對 SPY 超額報酬與成交量反應。尚未累積足夠交易日的反應保持
`pending`。

同一頁另保存兩種 point-in-time 信心序列：

- 每週機構信心：AI 只抽取帶來源的機構立場（−2 到 +2），Prism 以固定公式
  轉成 0–100。
- 每月公司長期信心：由本機 6／12 個月價格行為、機構信心與帶來源的品牌
  證據組成。

每個分項都顯示 coverage；缺失分項保持空值，整體標為 `partial`，不會以
50 分補齊。此版本採手動更新，因此缺少某週或某月只代表未執行研究，不代表
沒有事件或市場沒有觀點。詳細公式與資料血緣請見
[EVENT_RESEARCH.md](./EVENT_RESEARCH.md)。

## 測試

```bash
make test
npm run lint
npx tsc --noEmit
```

下載的市場資料與 DuckDB 檔案不會提交到 Git。
