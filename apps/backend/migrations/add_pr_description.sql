-- P0-2: PR 摘要自动生成 — review_tasks 表新增字段

ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS pr_description TEXT;
ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS description_posted BOOLEAN NOT NULL DEFAULT FALSE;
