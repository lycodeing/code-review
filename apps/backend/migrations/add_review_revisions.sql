-- PR 评审版本管理：支持同一 PR 多次 push 复用主记录
-- 执行方式：psql -U postgres -d code_review -f add_review_revisions.sql

-- 增加 parent_id：NULL 为主记录，非 NULL 为子版本（指向主记录）
ALTER TABLE review_tasks
    ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES review_tasks(id) ON DELETE CASCADE;

-- 增加 revision：版本号，表示第几次 push
ALTER TABLE review_tasks
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;

-- 增加 is_latest：标记是否为该 PR 的最新版本
ALTER TABLE review_tasks
    ADD COLUMN IF NOT EXISTS is_latest BOOLEAN NOT NULL DEFAULT TRUE;

-- 索引：按 parent_id 查询子版本
CREATE INDEX IF NOT EXISTS ix_review_parent_id ON review_tasks(parent_id);

-- 复合索引：按 project_id + mr_iid 查找主记录/最新版本
CREATE INDEX IF NOT EXISTS ix_review_project_mr_iid ON review_tasks(project_id, mr_iid);

-- 将已有记录标记为主记录（parent_id=NULL, revision=1, is_latest=TRUE）
-- 默认值已覆盖，无需额外 UPDATE

COMMENT ON COLUMN review_tasks.parent_id IS '父记录 ID（NULL 为主记录，非 NULL 为子版本）';
COMMENT ON COLUMN review_tasks.revision IS '版本号（第几次 push）';
COMMENT ON COLUMN review_tasks.is_latest IS '是否为最新版本';
