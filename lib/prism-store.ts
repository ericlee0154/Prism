import { env } from "cloudflare:workers";
import {
  DATA_CUTOFF,
  DEFAULT_WEIGHTS,
  DEMO_LEDGER,
  METRIC_VERSION,
  STOCKS,
  evaluateFormula,
  expectedRange,
  scoreFor,
  type FormulaWeights,
  type Horizon,
  type LedgerRow,
} from "./prism-domain";

type Identity = {
  ownerId: string;
  email: string;
  displayName: string;
  local: boolean;
};

type D1Row = Record<string, string | number | null>;

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS watchlist (
    owner_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, symbol)
  )`,
  `CREATE INDEX IF NOT EXISTS watchlist_owner_idx ON watchlist (owner_id)`,
  `CREATE TABLE IF NOT EXISTS formula_drafts (
    formula_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    horizon TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS formula_owner_updated_idx ON formula_drafts (owner_id, updated_at)`,
  `CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    horizon TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS experiment_owner_created_idx ON experiments (owner_id, created_at)`,
  `CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data_cutoff TEXT NOT NULL,
    symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL NOT NULL,
    expected_range TEXT NOT NULL,
    actual_outcome TEXT NOT NULL,
    outcome TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    metric_version TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    previous_hash TEXT,
    record_hash TEXT NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS prediction_owner_created_idx ON predictions (owner_id, created_at)`,
  `CREATE INDEX IF NOT EXISTS prediction_owner_symbol_idx ON predictions (owner_id, symbol)`,
  `CREATE TABLE IF NOT EXISTS activity (
    activity_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS activity_owner_created_idx ON activity (owner_id, created_at)`,
  `CREATE TABLE IF NOT EXISTS sync_runs (
    sync_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    symbol_count INTEGER NOT NULL,
    data_cutoff TEXT NOT NULL,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS research_notes (
    note_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    title TEXT NOT NULL,
    thesis TEXT NOT NULL,
    invalidation TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS research_note_owner_created_idx ON research_notes (owner_id, created_at)`,
  `CREATE INDEX IF NOT EXISTS research_note_owner_symbol_idx ON research_notes (owner_id, symbol)`,
];

let storeInitialization: Promise<D1Database> | null = null;

function getBinding(): D1Database {
  const binding = (env as unknown as { DB?: D1Database }).DB;
  if (!binding) throw new Error("D1 binding DB is unavailable");
  return binding;
}

export async function initializeStore(): Promise<D1Database> {
  if (!storeInitialization) {
    storeInitialization = (async () => {
      const db = getBinding();
      await db.batch(SCHEMA.map((statement) => db.prepare(statement)));
      return db;
    })().catch((error) => {
      storeInitialization = null;
      throw error;
    });
  }
  return storeInitialization;
}

export async function identityFromRequest(request: Request): Promise<Identity | null> {
  const email = request.headers.get("oai-authenticated-user-email");
  const encodedName = request.headers.get("oai-authenticated-user-full-name");
  const encoding = request.headers.get("oai-authenticated-user-full-name-encoding");
  const url = new URL(request.url);
  const localEmail =
    (url.hostname === "localhost" || url.hostname === "127.0.0.1")
      ? request.headers.get("x-prism-local-user")
      : null;
  const resolvedEmail = email ?? localEmail;
  if (!resolvedEmail) return null;

  let fullName: string | null = null;
  if (encodedName && encoding === "percent-encoded-utf-8") {
    try {
      fullName = decodeURIComponent(encodedName);
    } catch {
      fullName = null;
    }
  }

  return {
    ownerId: await sha256(resolvedEmail.trim().toLowerCase()),
    email: resolvedEmail,
    displayName: fullName ?? resolvedEmail.split("@")[0] ?? resolvedEmail,
    local: !email,
  };
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((part) => part.toString(16).padStart(2, "0"))
    .join("");
}

function isHorizon(value: unknown): value is Horizon {
  return value === "10D" || value === "30D" || value === "90D";
}

function isWeights(value: unknown): value is FormulaWeights {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  const keys: (keyof FormulaWeights)[] = [
    "momentum",
    "relativeStrength",
    "trendQuality",
    "volumeConfirmation",
    "volatility",
  ];
  return keys.every((key) => {
    const item = record[key];
    return typeof item === "number" && Number.isFinite(item) && item >= -1 && item <= 1;
  });
}

async function addActivity(
  db: D1Database,
  ownerId: string,
  action: string,
  summary: string,
  metadata: Record<string, unknown> = {},
) {
  await db
    .prepare(
      "INSERT INTO activity (activity_id, owner_id, action, summary, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
    )
    .bind(crypto.randomUUID(), ownerId, action, summary, JSON.stringify(metadata), new Date().toISOString())
    .run();
}

function rowToPrediction(row: D1Row): LedgerRow {
  return {
    predictionId: String(row.prediction_id),
    createdAt: String(row.created_at),
    dataCutoff: String(row.data_cutoff),
    symbol: String(row.symbol),
    horizon: String(row.horizon) as Horizon,
    direction: String(row.direction) as LedgerRow["direction"],
    confidence: Number(row.confidence),
    expectedRange: String(row.expected_range),
    actualOutcome: String(row.actual_outcome),
    outcome: String(row.outcome) as LedgerRow["outcome"],
    formulaVersion: String(row.formula_version),
    metricVersion: String(row.metric_version),
    recordHash: String(row.record_hash),
    previousHash: row.previous_hash ? String(row.previous_hash) : null,
    source: "user",
  };
}

export async function bootstrap(identity: Identity | null) {
  const fallback = {
    watchlist: ["NVDA", "MSFT"],
    formulas: [],
    experiments: [],
    userPredictions: [] as LedgerRow[],
    activity: [],
    syncRuns: [],
    notes: [],
  };
  if (!identity) return buildBootstrap(identity, fallback);

  const db = await initializeStore();
  const existing = await db
    .prepare("SELECT symbol FROM watchlist WHERE owner_id = ? ORDER BY created_at")
    .bind(identity.ownerId)
    .all<D1Row>();
  if (!existing.results.length) {
    const now = new Date().toISOString();
    await db.batch(
      ["NVDA", "MSFT"].map((symbol) =>
        db.prepare("INSERT OR IGNORE INTO watchlist (owner_id, symbol, created_at) VALUES (?, ?, ?)")
          .bind(identity.ownerId, symbol, now),
      ),
    );
  }

  const [watchlist, formulas, experiments, predictions, activities, syncRuns, notes] = await Promise.all([
    db.prepare("SELECT symbol FROM watchlist WHERE owner_id = ? ORDER BY created_at")
      .bind(identity.ownerId).all<D1Row>(),
    db.prepare("SELECT formula_id, name, horizon, weights_json, status, created_at, updated_at FROM formula_drafts WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 20")
      .bind(identity.ownerId).all<D1Row>(),
    db.prepare("SELECT experiment_id, formula_version, horizon, weights_json, result_json, created_at FROM experiments WHERE owner_id = ? ORDER BY created_at DESC LIMIT 20")
      .bind(identity.ownerId).all<D1Row>(),
    db.prepare("SELECT * FROM predictions WHERE owner_id = ? ORDER BY created_at DESC LIMIT 500")
      .bind(identity.ownerId).all<D1Row>(),
    db.prepare("SELECT activity_id, action, summary, metadata_json, created_at FROM activity WHERE owner_id = ? ORDER BY created_at DESC LIMIT 12")
      .bind(identity.ownerId).all<D1Row>(),
    db.prepare("SELECT sync_id, provider, status, symbol_count, data_cutoff, created_at FROM sync_runs WHERE owner_id = ? ORDER BY created_at DESC LIMIT 10")
      .bind(identity.ownerId).all<D1Row>(),
    db.prepare("SELECT note_id, symbol, title, thesis, invalidation, tags_json, created_at FROM research_notes WHERE owner_id = ? ORDER BY created_at DESC LIMIT 200")
      .bind(identity.ownerId).all<D1Row>(),
  ]);

  return buildBootstrap(identity, {
    watchlist: watchlist.results.map((row) => String(row.symbol)),
    formulas: formulas.results.map((row) => ({
      formulaId: String(row.formula_id),
      name: String(row.name),
      horizon: String(row.horizon),
      weights: JSON.parse(String(row.weights_json)),
      status: String(row.status),
      createdAt: String(row.created_at),
      updatedAt: String(row.updated_at),
    })),
    experiments: experiments.results.map((row) => ({
      experimentId: String(row.experiment_id),
      formulaVersion: String(row.formula_version),
      horizon: String(row.horizon),
      weights: JSON.parse(String(row.weights_json)),
      result: JSON.parse(String(row.result_json)),
      createdAt: String(row.created_at),
    })),
    userPredictions: predictions.results.map(rowToPrediction),
    activity: activities.results.map((row) => ({
      activityId: String(row.activity_id),
      action: String(row.action),
      summary: String(row.summary),
      metadata: JSON.parse(String(row.metadata_json)),
      createdAt: String(row.created_at),
    })),
    syncRuns: syncRuns.results,
    notes: notes.results.map((row) => ({
      noteId: String(row.note_id),
      symbol: String(row.symbol),
      title: String(row.title),
      thesis: String(row.thesis),
      invalidation: String(row.invalidation),
      tags: JSON.parse(String(row.tags_json)),
      createdAt: String(row.created_at),
    })),
  });
}

function buildBootstrap(identity: Identity | null, records: {
  watchlist: string[];
  formulas: unknown[];
  experiments: unknown[];
  userPredictions: LedgerRow[];
  activity: unknown[];
  syncRuns: unknown[];
  notes: unknown[];
}) {
  const ledger = [...records.userPredictions, ...DEMO_LEDGER].sort(
    (left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt),
  );
  const matured = ledger.filter((row) => row.outcome !== "Pending");
  const correct = matured.filter((row) => row.outcome === "Correct");
  return {
    user: identity
      ? { displayName: identity.displayName, email: identity.email, local: identity.local }
      : null,
    readOnly: !identity,
    mode: "demo",
    provider: "demo-seed",
    dataCutoff: DATA_CUTOFF,
    metricVersion: METRIC_VERSION,
    stocks: STOCKS,
    watchlist: records.watchlist,
    formulas: records.formulas,
    experiments: records.experiments,
    ledger,
    activity: records.activity,
    syncRuns: records.syncRuns,
    notes: records.notes,
    overview: {
      marketRegime: { label: "Selective risk-on", confidence: 0.68 },
      candidateCoverage: {
        passing: STOCKS.filter((stock) => stock.score30 >= 60).length,
        universe: STOCKS.length,
      },
      directionHitRate30d: matured.length ? correct.length / matured.length : 0,
      ledger: {
        matured: matured.length,
        correct: correct.length,
        pending: ledger.length - matured.length,
      },
    },
    pipeline: {
      status: "healthy",
      steps: [
        { name: "Raw ingest", status: "ready", version: "demo-v1.0" },
        { name: "Time audit", status: "ready", version: "v1.0" },
        { name: "Metrics", status: "ready", version: METRIC_VERSION },
        { name: "Labels", status: "isolated", version: "v1.0" },
        { name: "Formula", status: "candidate", version: "core-v1.0" },
        { name: "Ledger", status: "append-only", version: "v1.0" },
      ],
    },
  };
}

export async function mutate(identity: Identity, input: Record<string, unknown>) {
  const db = await initializeStore();
  const action = String(input.action ?? "");

  if (action === "toggle-watch") {
    const symbol = String(input.symbol ?? "").toUpperCase();
    if (!STOCKS.some((stock) => stock.symbol === symbol)) throw new Error("Unknown symbol");
    const existing = await db
      .prepare("SELECT symbol FROM watchlist WHERE owner_id = ? AND symbol = ?")
      .bind(identity.ownerId, symbol).first();
    if (existing) {
      await db.prepare("DELETE FROM watchlist WHERE owner_id = ? AND symbol = ?")
        .bind(identity.ownerId, symbol).run();
    } else {
      await db.prepare("INSERT INTO watchlist (owner_id, symbol, created_at) VALUES (?, ?, ?)")
        .bind(identity.ownerId, symbol, new Date().toISOString()).run();
    }
    await addActivity(db, identity.ownerId, "watchlist", `${symbol} ${existing ? "removed from" : "added to"} watchlist`, { symbol });
    return { watched: !existing, symbol };
  }

  if (action === "save-formula") {
    const name = String(input.name ?? "").trim();
    const horizon = input.horizon;
    const weights = input.weights;
    if (!name || name.length > 80) throw new Error("Formula name must be 1–80 characters");
    if (!isHorizon(horizon) || !isWeights(weights)) throw new Error("Invalid formula inputs");
    const formulaId = crypto.randomUUID();
    const now = new Date().toISOString();
    await db.prepare(
      "INSERT INTO formula_drafts (formula_id, owner_id, name, horizon, weights_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)",
    ).bind(formulaId, identity.ownerId, name, horizon, JSON.stringify(weights), now, now).run();
    await addActivity(db, identity.ownerId, "formula", `Saved formula draft ${name}`, { formulaId, horizon });
    return { formulaId, name, horizon, weights, status: "draft", createdAt: now, updatedAt: now };
  }

  if (action === "evaluate-formula") {
    const name = String(input.name ?? "candidate-v1").trim();
    const horizon = input.horizon;
    const weights = input.weights;
    if (!name || name.length > 80 || !isHorizon(horizon) || !isWeights(weights)) {
      throw new Error("Invalid experiment inputs");
    }
    const result = evaluateFormula(horizon, weights);
    const experimentId = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    await db.prepare(
      "INSERT INTO experiments (experiment_id, owner_id, formula_version, horizon, weights_json, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
    ).bind(experimentId, identity.ownerId, name, horizon, JSON.stringify(weights), JSON.stringify(result), createdAt).run();
    await addActivity(db, identity.ownerId, "experiment", `Validated ${name} on ${horizon}`, { experimentId, horizon });
    return { experimentId, formulaVersion: name, weights, result, createdAt };
  }

  if (action === "seal-prediction") {
    const symbol = String(input.symbol ?? "").toUpperCase();
    const horizon = input.horizon;
    const formulaVersion = String(input.formulaVersion ?? "").trim();
    const stock = STOCKS.find((item) => item.symbol === symbol);
    if (!stock) throw new Error("Unknown symbol");
    if (!isHorizon(horizon)) throw new Error("Invalid horizon");
    if (!formulaVersion || formulaVersion.length > 80) throw new Error("Invalid formula version");
    if (Date.parse(DATA_CUTOFF) > Date.now()) {
      throw new Error("Data cutoff is not available yet");
    }
    const score = scoreFor(stock, horizon);
    const direction = score >= 60 ? "Bullish" : score < 45 ? "Bearish" : "Neutral";
    const previous = await db
      .prepare("SELECT record_hash FROM predictions WHERE owner_id = ? ORDER BY created_at DESC LIMIT 1")
      .bind(identity.ownerId).first<{ record_hash: string }>();
    const previousHash = previous?.record_hash ?? null;
    const predictionId = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    const snapshot = {
      symbol,
      metrics: stock.metrics,
      scores: { "10D": stock.score10, "30D": stock.score30, "90D": stock.score90 },
      dataCutoff: DATA_CUTOFF,
      source: "demo-seed",
      metricVersion: METRIC_VERSION,
    };
    const canonical = JSON.stringify({
      predictionId, createdAt, dataCutoff: DATA_CUTOFF, symbol, horizon,
      direction, confidence: stock.confidence, formulaVersion, snapshot, previousHash,
    });
    const recordHash = await sha256(canonical);
    await db.prepare(
      `INSERT INTO predictions (
        prediction_id, owner_id, created_at, data_cutoff, symbol, horizon,
        direction, confidence, expected_range, actual_outcome, outcome,
        formula_version, metric_version, input_snapshot_json, previous_hash,
        record_hash
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', 'Pending', ?, ?, ?, ?, ?)`,
    ).bind(
      predictionId, identity.ownerId, createdAt, DATA_CUTOFF, symbol, horizon,
      direction, stock.confidence, expectedRange(direction), formulaVersion,
      METRIC_VERSION, JSON.stringify(snapshot), previousHash, recordHash,
    ).run();
    await addActivity(db, identity.ownerId, "prediction", `Sealed ${symbol} ${horizon} ${direction} prediction`, { predictionId, recordHash });
    return {
      predictionId, createdAt, dataCutoff: DATA_CUTOFF, symbol, horizon,
      direction, confidence: stock.confidence, expectedRange: expectedRange(direction),
      actualOutcome: "Pending", outcome: "Pending", formulaVersion,
      metricVersion: METRIC_VERSION, recordHash, previousHash, source: "user",
    };
  }

  if (action === "sync-demo") {
    const syncId = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    await db.prepare(
      "INSERT INTO sync_runs (sync_id, owner_id, provider, status, symbol_count, data_cutoff, created_at) VALUES (?, ?, 'demo-seed', 'complete', ?, ?, ?)",
    ).bind(syncId, identity.ownerId, STOCKS.length, DATA_CUTOFF, createdAt).run();
    await addActivity(db, identity.ownerId, "sync", `Synchronized ${STOCKS.length} demo symbols`, { syncId });
    return { syncId, status: "complete", provider: "demo-seed", symbolCount: STOCKS.length, dataCutoff: DATA_CUTOFF, createdAt };
  }

  if (action === "add-note") {
    const symbol = String(input.symbol ?? "").toUpperCase();
    const title = String(input.title ?? "").trim();
    const thesis = String(input.thesis ?? "").trim();
    const invalidation = String(input.invalidation ?? "").trim();
    const tags = Array.isArray(input.tags)
      ? input.tags.map((tag) => String(tag).trim()).filter(Boolean).slice(0, 8)
      : [];
    if (!STOCKS.some((stock) => stock.symbol === symbol)) throw new Error("Unknown symbol");
    if (!title || title.length > 120) throw new Error("Note title must be 1–120 characters");
    if (!thesis || thesis.length > 2000) throw new Error("Thesis must be 1–2000 characters");
    if (!invalidation || invalidation.length > 1000) throw new Error("Invalidation condition must be 1–1000 characters");
    const noteId = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    await db.prepare(
      "INSERT INTO research_notes (note_id, owner_id, symbol, title, thesis, invalidation, tags_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    ).bind(noteId, identity.ownerId, symbol, title, thesis, invalidation, JSON.stringify(tags), createdAt).run();
    await addActivity(db, identity.ownerId, "journal", `Recorded ${symbol} thesis: ${title}`, { noteId, symbol });
    return { noteId, symbol, title, thesis, invalidation, tags, createdAt };
  }

  if (action === "verify-ledger") {
    const rows = await db.prepare(
      `SELECT prediction_id, created_at, data_cutoff, symbol, horizon, direction,
        confidence, formula_version, input_snapshot_json, previous_hash, record_hash
      FROM predictions WHERE owner_id = ? ORDER BY created_at`,
    ).bind(identity.ownerId).all<{
      prediction_id: string;
      created_at: string;
      data_cutoff: string;
      symbol: string;
      horizon: string;
      direction: string;
      confidence: number;
      formula_version: string;
      input_snapshot_json: string;
      previous_hash: string | null;
      record_hash: string;
    }>();
    let previous: string | null = null;
    let valid = true;
    for (const row of rows.results) {
      const canonical = JSON.stringify({
        predictionId: row.prediction_id,
        createdAt: row.created_at,
        dataCutoff: row.data_cutoff,
        symbol: row.symbol,
        horizon: row.horizon,
        direction: row.direction,
        confidence: row.confidence,
        formulaVersion: row.formula_version,
        snapshot: JSON.parse(row.input_snapshot_json),
        previousHash: row.previous_hash,
      });
      const contentValid = await sha256(canonical) === row.record_hash;
      const linked = row.previous_hash === previous;
      valid = valid && linked && contentValid;
      previous = row.record_hash;
    }
    await addActivity(db, identity.ownerId, "integrity", `Ledger integrity ${valid ? "verified" : "failed"}`, { records: rows.results.length });
    return { valid, records: rows.results.length, checkedAt: new Date().toISOString() };
  }

  if (action === "reset-default-formula") {
    return { weights: DEFAULT_WEIGHTS };
  }

  throw new Error("Unknown action");
}
