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
- 已儲存的真實資料可離線查閱，但會顯示觀察日與可用時間。
- Massive key 只存在本機 FastAPI 程序，不會傳到瀏覽器。

## 安裝與啟動

```bash
make setup
cp .env.example .env
```

在不會提交到 Git 的 `.env` 設定：

```dotenv
MASSIVE_API_KEY=你的金鑰
PRISM_DATABASE_PATH=./data/prism.duckdb
```

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

## 測試

```bash
make test
npm run lint
npx tsc --noEmit
```

下載的市場資料與 DuckDB 檔案不會提交到 Git。
