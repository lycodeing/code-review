-- P0-1: 增量学习 — 新增 review_learnings 表

CREATE TABLE IF NOT EXISTS review_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type VARCHAR(32) NOT NULL DEFAULT 'feedback',
    source_comment_id UUID REFERENCES review_comments(id) ON DELETE SET NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'style',
    rule_text TEXT NOT NULL,
    context TEXT,
    feedback_sentiment VARCHAR(16),
    confidence INTEGER NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learnings_project ON review_learnings(project_id);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON review_learnings(project_id, category);
CREATE INDEX IF NOT EXISTS idx_learnings_enabled ON review_learnings(project_id, enabled);
