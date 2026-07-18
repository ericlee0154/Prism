import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("builds the local real-data Prism research workspace", async () => {
  const [app, layout] = await Promise.all([
    readFile(new URL("../app/prism-app.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(layout, /Prism — Personal Market Research/);
  assert.match(app, /Research what is actually stored\./);
  assert.match(app, /Market scanner/);
  assert.match(app, /Run real backtest/);
  assert.match(app, /Synchronize to DuckDB/);
  assert.match(app, /no substitute data is displayed/);
  assert.match(app, /區間 Metrics/);
  assert.match(app, /Calculate metrics & forecast/);
  assert.match(app, /World & company events/);
  assert.match(app, /Institution confidence · weekly/);
  assert.match(app, /Company long-term confidence · monthly/);
  assert.match(app, /Codex CLI/);
  assert.match(app, /language: \{ zh: "EN", en: "中文" \}/);
  assert.doesNotMatch(app, /demo-seed|initialLedger|const stocks/);
  assert.doesNotMatch(app, /codex-preview|Your site is taking shape|Building your site/i);
});

test("keeps provider credentials server-side and local", async () => {
  const [page, api, provider, hosting, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../apps/api/main.py", import.meta.url), "utf8"),
    readFile(new URL("../packages/prism_core/providers/massive.py", import.meta.url), "utf8"),
    readFile(new URL("../.openai/hosting.json", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /getChatGPTUser/);
  assert.match(api, /load_dotenv/);
  assert.match(api, /api\/v1\/sync/);
  assert.match(provider, /MASSIVE_API_KEY/);
  assert.doesNotMatch(provider, /NEXT_PUBLIC_/);
  assert.match(hosting, /"d1":\s*"DB"/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
