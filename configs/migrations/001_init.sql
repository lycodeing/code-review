-- 数据库迁移脚本（初始版本）
-- 使用方式：psql -U postgres -d code_review -f 001_init.sql

-- 项目配置表
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    platform VARCHAR(50) NOT NULL,
    platform_project_id VARCHAR(255) NOT NULL,
    webhook_secret VARCHAR(512),
    config JSONB,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_platform ON projects(platform, platform_project_id);

-- 评审任务表
CREATE TABLE IF NOT EXISTS review_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mr_iid VARCHAR(64) NOT NULL,
    mr_title VARCHAR(512),
    mr_author VARCHAR(255),
    mr_url TEXT,
    source_branch VARCHAR(255),
    target_branch VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    event_id VARCHAR(255),
    trigger_action VARCHAR(64),
    model_name VARCHAR(128),
    total_comments INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    summary TEXT,
    error_message TEXT,
    celery_task_id VARCHAR(255),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_review_event UNIQUE (project_id, mr_iid, event_id)
);

CREATE INDEX idx_review_status ON review_tasks(status);
CREATE INDEX idx_review_project ON review_tasks(project_id);

-- 评审意见表
CREATE TABLE IF NOT EXISTS review_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES review_tasks(id) ON DELETE CASCADE,
    file_path VARCHAR(1024) NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER,
    severity VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    suggestion TEXT,
    platform_comment_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comments_task ON review_comments(task_id);
CREATE INDEX idx_comments_severity ON review_comments(severity);

-- updated_at 自动更新触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_projects_updated
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
