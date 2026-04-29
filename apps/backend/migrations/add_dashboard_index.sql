-- 仪表盘统计查询优化索引
CREATE INDEX IF NOT EXISTS ix_review_tasks_created_at
    ON review_tasks (created_at);

CREATE INDEX IF NOT EXISTS ix_review_tasks_project_created
    ON review_tasks (project_id, created_at);
