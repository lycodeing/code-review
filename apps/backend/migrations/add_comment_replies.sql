-- 多轮评审对话：评论回复表

CREATE TABLE IF NOT EXISTS comment_replies (
    id UUID PRIMARY KEY,
    comment_id UUID NOT NULL REFERENCES review_comments(id) ON DELETE CASCADE,
    parent_reply_id UUID REFERENCES comment_replies(id) ON DELETE CASCADE,
    author VARCHAR(255) NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'user',
    llm_context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comment_replies_comment ON comment_replies(comment_id);
CREATE INDEX IF NOT EXISTS idx_comment_replies_parent ON comment_replies(parent_reply_id);
