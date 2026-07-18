CREATE TABLE `activity` (
	`activity_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`action` text NOT NULL,
	`summary` text NOT NULL,
	`metadata_json` text DEFAULT '{}' NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `activity_owner_created_idx` ON `activity` (`owner_id`,`created_at`);--> statement-breakpoint
CREATE TABLE `experiments` (
	`experiment_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`formula_version` text NOT NULL,
	`horizon` text NOT NULL,
	`weights_json` text NOT NULL,
	`result_json` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `experiment_owner_created_idx` ON `experiments` (`owner_id`,`created_at`);--> statement-breakpoint
CREATE TABLE `formula_drafts` (
	`formula_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`name` text NOT NULL,
	`horizon` text NOT NULL,
	`weights_json` text NOT NULL,
	`status` text DEFAULT 'draft' NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `formula_owner_updated_idx` ON `formula_drafts` (`owner_id`,`updated_at`);--> statement-breakpoint
CREATE TABLE `predictions` (
	`prediction_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`created_at` text NOT NULL,
	`data_cutoff` text NOT NULL,
	`symbol` text NOT NULL,
	`horizon` text NOT NULL,
	`direction` text NOT NULL,
	`confidence` real NOT NULL,
	`expected_range` text NOT NULL,
	`actual_outcome` text NOT NULL,
	`outcome` text NOT NULL,
	`formula_version` text NOT NULL,
	`metric_version` text NOT NULL,
	`input_snapshot_json` text NOT NULL,
	`previous_hash` text,
	`record_hash` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `prediction_owner_created_idx` ON `predictions` (`owner_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `prediction_owner_symbol_idx` ON `predictions` (`owner_id`,`symbol`);--> statement-breakpoint
CREATE TABLE `sync_runs` (
	`sync_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`provider` text NOT NULL,
	`status` text NOT NULL,
	`symbol_count` integer NOT NULL,
	`data_cutoff` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `watchlist` (
	`owner_id` text NOT NULL,
	`symbol` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `watchlist_owner_symbol_idx` ON `watchlist` (`owner_id`,`symbol`);--> statement-breakpoint
CREATE INDEX `watchlist_owner_idx` ON `watchlist` (`owner_id`);