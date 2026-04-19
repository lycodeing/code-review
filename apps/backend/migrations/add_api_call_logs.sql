-- API 调用日志表：统一记录 LLM 调用和通知发送的请求/响应详情
CREATE TABLE IF NOT EXISTS api_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES review_tasks(id) ON DELETE CASCADE,
    call_type VARCHAR(32) NOT NULL,   -- 'llm' | 'notification'
    provider VARCHAR(64),             -- 模型名称或渠道名称（dingtalk/feishu/gpt-4 等）
    method VARCHAR(16),               -- HTTP 方法（POST 等）
    url TEXT,                         -- 端点 URL（access_token 等敏感字段已脱敏）
    request_headers JSONB,            -- 请求头（Authorization 脱敏为 [REDACTED]）
    request_body JSONB,               -- 请求体
    response_status INTEGER,          -- HTTP 响应状态码
    response_body JSONB,              -- 响应内容（超 64KB 时截断）
    status VARCHAR(32) NOT NULL DEFAULT 'success',  -- 'success' | 'failed'
    error_message TEXT,               -- 失败时的错误详情
    duration_ms INTEGER,              -- 请求耗时（毫秒）
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_call_logs_task_id ON api_call_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_api_call_logs_call_type ON api_call_logs(call_type);
CREATE INDEX IF NOT EXISTS idx_api_call_logs_status ON api_call_logs(status);
CREATE INDEX IF NOT EXISTS idx_api_call_logs_created_at ON api_call_logs(created_at);
