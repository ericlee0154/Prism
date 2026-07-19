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

## Metrics 與評分 v0.2

`price-core-v0.2` 是固定公式的價格研究基線，不是已訓練或校準過的報酬
模型。每個原始 metric 只使用觀察時間與 `available_at` 都不晚於指定
cutoff 的拆股調整日線。歷史不足、缺少同日 SPY，或分母無法定義時回傳
`null`。若 catalog 明確定義「沒有移動」在數學上應為 0，仍會得到真實的
0；但不會拿 0、50 分、中性分數或 demo 值填補缺失資料。Web 顯示的
catalog 與實際計算共用同一份定義，其中記錄公式、輸入、交易日視窗、
最少觀察數、價格基礎、`ddof`、cutoff 規則、空值與零分母政策。

v0.2 原始 metrics 包含：

- 5／20／60 個交易日的收盤價報酬；
- 20／60 日年化已實現波動與下行半波動，以及 20D／60D 波動比；
- 含當日的 20 日成交量 z-score、相對前 20 日的當日成交量驚奇，以及
  20 日漲跌成交量平衡；
- 距 MA20／MA50、60 日回撤、20／60 日趨勢效率，以及 60 日價格區間位置；
- 20 日成交金額中位數（只作流動性診斷）；以及
- 相對 SPY 的 60 日 Beta 與 20／60 日 Beta 調整價格報酬。

`cross-sectional-alpha-risk-v0.2` 是市場掃描與歷史 walk-forward 共用的
唯一評分實作。每次掃描會保存實際儲存股票池、symbol-list hash、共同
as-of 交易日、共同資料 cutoff、可計分／排除股票與各 horizon 覆蓋率。
SPY 只作 benchmark，不列入候選股票排名；至少需要三檔資料完整的候選
股票。

每個可用 metric 先以同名次平均的方式計算橫截面百分位，再將 0–100
映射到 -1–1。Alpha 與觀察到的價格風險完全分開：

- Alpha 有兩個各占 50% 的 factor bucket。「市場調整動能」使用扣除
  Beta 倍數 SPY 報酬後的報酬；「趨勢品質」平均趨勢效率、60 日區間位置
  與距離對應均線。10D／30D 使用 20D Beta 調整報酬，90D 使用 60D；
  10D 使用 20D 趨勢效率與 MA20，30D／90D 使用 MA50，90D 另使用
  60D 趨勢效率。
- Risk 有三個各占三分之一的 bucket：已實現／下行波動水準、60 日回撤
  嚴重度，以及 20D／60D 波動擴張。已實現波動與下行半波動放在同一
  bucket，避免高度相關指標各拿一份獨立權重。Risk 較高只代表觀察到的
  價格風險較高，不等同預期報酬較低。

每個 bucket 先平均其中帶方向的 metric ranks，再套用 bucket 權重。任何
必要 bucket 缺值時整個 model 保持 `null`。Alpha／risk 原始值維持在
-1–1，並各自再轉成 0–100 橫截面排名供快速掃描；這些排名只是目前
DuckDB 股票池內的相對位置，不是機率或信心校準。

因此 v0.2 封存的研究預測使用相對超額／相對落後標籤。在累積足夠
forward calibration 前，資料庫中的 `confidence` 保持 `null`；rank
extremity 會另外保存在不可變 input snapshot，並明確標示它不是機率。

介面同時區分兩種百分位。「橫截面百分位」比較共同 cutoff 下不同股票的
同一 metric；「歷史百分位」只拿當前值與該股票嚴格較早的 point-in-time
值比較，最多使用前 252 個 endpoint，且至少需 60 個可用觀察。比較樣本
不足就顯示空值；兩種百分位本身都不代表具有預測力。

## Walk-forward 診斷 v0.2

回測會在每個歷史評估 cutoff 重建同一組 raw metrics，並呼叫與即時掃描
完全相同的 Alpha／risk 評分程式。需要對齊的 SPY 與至少三檔候選股票，
支援 10／30／90 個交易日 horizon，每五個交易日重新評估一次；每次結果
會保存 requested universe hash、實際可用股票數、覆蓋率與排除原因。

收盤到收盤的診斷 label 仍會保留，但主要研究 label 改為：

```text
(股票 close[t+h] / 股票 open[t+1] - 1)
-
(SPY close[t+h] / SPY open[t+1] - 1)
```

輸出包含逐日 Spearman IC、中位數與正 IC 比率、最高組減最低組的
SPY 超額報酬差、方向準確率及多數類別 baseline、未來最大回撤／漲幅、
risk 對未來已實現波動與回撤嚴重度的 IC，以及 factor ablation 與
factor correlation。這些是用來淘汰或修改公式的研究診斷，不是基線可獲利
的證明。

目前限制必須一起閱讀：不同評估日的未來視窗會重疊，因此 observation
不能視為彼此獨立；universe 是目前 DuckDB 內的股票，尚未解決
survivorship bias；報酬只使用拆股調整價格，不含股息；也未計入手續費、
滑價、稅務、借券成本與市場衝擊。Point-in-time 產業相對報酬、total-return
資料，以及由 AI 自動搜尋公式或調整權重，都刻意延後到資料血緣與
out-of-sample 驗證可被稽核之後。AI 事件研究不會改寫 v0.2 公式。

## 區間 Metrics 與歷史類比

「區間 Metrics」提供日期欄位及雙端拖曳時間軸，依選定結束日計算 v0.2
point-in-time raw metric snapshot。同時用該區間內較早的相似狀態建立
10／30／90 交易日歷史類比 forecast，回報 10%、50%、90% 報酬與價格
點位、正報酬比例及樣本數。股票、日期或滑桿變更後會自動重算；整段區間
也能依指定天數向左或向右平移，方便逐日檢查 metrics 的連續性。

若歷史分析 cutoff 後已有儲存日線，只有 Forecast 真值驗證區會讀取它們，
並列出目標日及其前後五個交易日。區間外資料不會進入 Metrics、上方價格
序列或歷史類比生成。可選的單一股票 3D forecast history 以 target time、
data source（actual／P10／P50／P90）與價格為三軸；它不屬於跨股票回測。
少於十個合格類比樣本時不產生 forecast 數值。

這些結果僅供研究與回測設計，不是投資建議或交易指令。

## 世界事件、公司事件與信心追蹤

「世界與公司事件」只在你按下更新時呼叫本機 `codex exec --search`。
Codex 在隔離的唯讀暫存目錄非互動執行，不會收到 Massive key。Prism
驗證 JSON Schema、搜尋紀錄與來源 URL，並保存來源、模型、prompt 版本、
run 狀態與用量。缺登入、缺來源、網路失敗或 quota 用完時都不會補入
預設事件。

新研究的世界與公司事件會同時保存英文內容與忠實的繁中翻譯。每個引用
來源都會標注網頁語言，並提供獨立的「查看原文」連結。舊事件若沒有翻譯
metadata 會清楚保持英文，直到下一次有來源的研究更新。

每則事件會分開標示可能影響規模、傳導範圍、方向、時間尺度與固定市場
分類。本機追蹤股票／ETF 會依有來源的業務或基金曝險事前分類；只有分類
確實相交或事件直接涉及該公司時才建立連結，未分類或無交集時保持空白。

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
