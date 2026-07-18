import { index, integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const watchlist = sqliteTable(
  "watchlist",
  {
    ownerId: text("owner_id").notNull(),
    symbol: text("symbol").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    uniqueIndex("watchlist_owner_symbol_idx").on(table.ownerId, table.symbol),
    index("watchlist_owner_idx").on(table.ownerId),
  ],
);

export const formulaDrafts = sqliteTable(
  "formula_drafts",
  {
    formulaId: text("formula_id").primaryKey(),
    ownerId: text("owner_id").notNull(),
    name: text("name").notNull(),
    horizon: text("horizon").notNull(),
    weightsJson: text("weights_json").notNull(),
    status: text("status").notNull().default("draft"),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    index("formula_owner_updated_idx").on(table.ownerId, table.updatedAt),
  ],
);

export const experiments = sqliteTable(
  "experiments",
  {
    experimentId: text("experiment_id").primaryKey(),
    ownerId: text("owner_id").notNull(),
    formulaVersion: text("formula_version").notNull(),
    horizon: text("horizon").notNull(),
    weightsJson: text("weights_json").notNull(),
    resultJson: text("result_json").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("experiment_owner_created_idx").on(table.ownerId, table.createdAt),
  ],
);

export const predictions = sqliteTable(
  "predictions",
  {
    predictionId: text("prediction_id").primaryKey(),
    ownerId: text("owner_id").notNull(),
    createdAt: text("created_at").notNull(),
    dataCutoff: text("data_cutoff").notNull(),
    symbol: text("symbol").notNull(),
    horizon: text("horizon").notNull(),
    direction: text("direction").notNull(),
    confidence: real("confidence").notNull(),
    expectedRange: text("expected_range").notNull(),
    actualOutcome: text("actual_outcome").notNull(),
    outcome: text("outcome").notNull(),
    formulaVersion: text("formula_version").notNull(),
    metricVersion: text("metric_version").notNull(),
    inputSnapshotJson: text("input_snapshot_json").notNull(),
    previousHash: text("previous_hash"),
    recordHash: text("record_hash").notNull(),
  },
  (table) => [
    index("prediction_owner_created_idx").on(table.ownerId, table.createdAt),
    index("prediction_owner_symbol_idx").on(table.ownerId, table.symbol),
  ],
);

export const activity = sqliteTable(
  "activity",
  {
    activityId: text("activity_id").primaryKey(),
    ownerId: text("owner_id").notNull(),
    action: text("action").notNull(),
    summary: text("summary").notNull(),
    metadataJson: text("metadata_json").notNull().default("{}"),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("activity_owner_created_idx").on(table.ownerId, table.createdAt),
  ],
);

export const syncRuns = sqliteTable("sync_runs", {
  syncId: text("sync_id").primaryKey(),
  ownerId: text("owner_id").notNull(),
  provider: text("provider").notNull(),
  status: text("status").notNull(),
  symbolCount: integer("symbol_count").notNull(),
  dataCutoff: text("data_cutoff").notNull(),
  createdAt: text("created_at").notNull(),
});

export const researchNotes = sqliteTable(
  "research_notes",
  {
    noteId: text("note_id").primaryKey(),
    ownerId: text("owner_id").notNull(),
    symbol: text("symbol").notNull(),
    title: text("title").notNull(),
    thesis: text("thesis").notNull(),
    invalidation: text("invalidation").notNull(),
    tagsJson: text("tags_json").notNull().default("[]"),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("research_note_owner_created_idx").on(table.ownerId, table.createdAt),
    index("research_note_owner_symbol_idx").on(table.ownerId, table.symbol),
  ],
);
