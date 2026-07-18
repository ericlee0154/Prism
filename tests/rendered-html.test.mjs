import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("builds the complete Prism research workspace", async () => {
  const [app, layout, worker] = await Promise.all([
    readFile(new URL("../app/prism-app.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../dist/server/index.js", import.meta.url), "utf8"),
  ]);

  assert.match(layout, /Prism — Personal Market Research/);
  assert.match(app, /Read the market, then test the story\./);
  assert.match(app, /Market scanner/);
  assert.match(app, /Formula lab/);
  assert.match(app, /Prediction ledger/);
  assert.match(app, /Research journal/);
  assert.match(app, /seal-prediction/);
  assert.match(app, /add-note/);
  assert.match(worker, /api\/prism/);
  assert.doesNotMatch(app, /codex-preview|Your site is taking shape|Building your site/i);
});

test("keeps durable state and writes behind the Prism API", async () => {
  const [page, api, schema, hosting, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/api/prism/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../db/schema.ts", import.meta.url), "utf8"),
    readFile(new URL("../.openai/hosting.json", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /getChatGPTUser/);
  assert.match(api, /identityFromRequest/);
  assert.match(api, /status:\s*401/);
  assert.match(schema, /predictions/);
  assert.match(schema, /watchlist/);
  assert.match(schema, /experiments/);
  assert.match(schema, /researchNotes/);
  assert.match(hosting, /"d1":\s*"DB"/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
