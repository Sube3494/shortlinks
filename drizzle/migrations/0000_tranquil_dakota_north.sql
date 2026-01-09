CREATE TABLE `api_keys` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`key` text NOT NULL,
	`name` text NOT NULL,
	`created_at` integer DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`expires_at` integer,
	`last_used_at` integer,
	`usage_count` integer DEFAULT 0 NOT NULL,
	`is_active` integer DEFAULT true NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `api_keys_key_unique` ON `api_keys` (`key`);--> statement-breakpoint
CREATE TABLE `shortlinks` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`short_code` text NOT NULL,
	`original_url` text NOT NULL,
	`url_hash` text,
	`created_at` integer DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`click_count` integer DEFAULT 0 NOT NULL,
	`last_accessed` integer,
	`expires_at` integer,
	`created_by_key_id` integer
);
--> statement-breakpoint
CREATE UNIQUE INDEX `shortlinks_short_code_unique` ON `shortlinks` (`short_code`);--> statement-breakpoint
CREATE TABLE `system_config` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`key` text NOT NULL,
	`value` text NOT NULL,
	`description` text,
	`updated_at` integer DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `system_config_key_unique` ON `system_config` (`key`);