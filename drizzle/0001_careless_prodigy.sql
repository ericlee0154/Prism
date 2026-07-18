CREATE TABLE `research_notes` (
	`note_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`symbol` text NOT NULL,
	`title` text NOT NULL,
	`thesis` text NOT NULL,
	`invalidation` text NOT NULL,
	`tags_json` text DEFAULT '[]' NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `research_note_owner_created_idx` ON `research_notes` (`owner_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `research_note_owner_symbol_idx` ON `research_notes` (`owner_id`,`symbol`);