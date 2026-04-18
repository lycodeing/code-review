-- 数据库初始化脚本
-- 包含所有表结构、索引、触发器和种子数据
-- 使用方式：psql -U postgres -d code_review -f init.sql

-- ============================================================
-- 工具函数
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 项目表
-- ============================================================

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

CREATE INDEX IF NOT EXISTS idx_projects_platform ON projects(platform, platform_project_id);

CREATE TRIGGER trigger_projects_updated
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 评审任务表
-- ============================================================

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

CREATE INDEX IF NOT EXISTS idx_review_status ON review_tasks(status);
CREATE INDEX IF NOT EXISTS idx_review_project ON review_tasks(project_id);

-- ============================================================
-- 评审意见表
-- ============================================================

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

CREATE INDEX IF NOT EXISTS idx_comments_task ON review_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_comments_severity ON review_comments(severity);

-- ============================================================
-- Prompt 模板表
-- ============================================================

CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'default',
    locale VARCHAR(10) NOT NULL DEFAULT 'zh',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_prompt_template_name UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS ix_prompt_template_category ON prompt_templates(category);
CREATE INDEX IF NOT EXISTS ix_prompt_template_locale ON prompt_templates(locale);

CREATE TRIGGER trigger_prompt_templates_updated
    BEFORE UPDATE ON prompt_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 代码平台配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS platform_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(32) NOT NULL,
    access_token TEXT NOT NULL DEFAULT '',
    webhook_secret TEXT NOT NULL DEFAULT '',
    api_url VARCHAR(512) NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_platform UNIQUE (platform)
);

CREATE TRIGGER trigger_platform_configs_updated
    BEFORE UPDATE ON platform_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 通知渠道配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS notification_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(32) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    webhook_url VARCHAR(1024) NOT NULL DEFAULT '',
    secret TEXT NOT NULL DEFAULT '',
    at_mobiles VARCHAR(1024) NOT NULL DEFAULT '',
    description VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_notification_channel UNIQUE (channel)
);

CREATE TRIGGER trigger_notification_configs_updated
    BEFORE UPDATE ON notification_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 平台-通知关联表（多对多）
-- ============================================================

CREATE TABLE IF NOT EXISTS platform_notification_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platform_configs(id) ON DELETE CASCADE,
    notification_id UUID NOT NULL REFERENCES notification_configs(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_platform_notification UNIQUE (platform_id, notification_id)
);

CREATE INDEX IF NOT EXISTS idx_bindings_platform ON platform_notification_bindings(platform_id);
CREATE INDEX IF NOT EXISTS idx_bindings_notification ON platform_notification_bindings(notification_id);

-- ============================================================
-- LLM 配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS llm_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    provider VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    api_key TEXT NOT NULL DEFAULT '',
    api_base VARCHAR(512) NOT NULL DEFAULT '',
    response_format VARCHAR(32) NOT NULL DEFAULT 'auto',
    extra_params JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_llm_configs_response_format
        CHECK (response_format IN ('auto', 'json', 'anthropic_thinking', 'xml', 'plain_text'))
);

CREATE INDEX IF NOT EXISTS idx_llm_configs_provider ON llm_configs(provider);
CREATE INDEX IF NOT EXISTS idx_llm_configs_enabled ON llm_configs(enabled);
CREATE INDEX IF NOT EXISTS idx_llm_configs_response_format ON llm_configs(response_format);

COMMENT ON TABLE llm_configs IS 'LLM 提供商配置表';
COMMENT ON COLUMN llm_configs.provider IS '提供商：openai/anthropic/deepseek/ollama/azure/bedrock/dashscope';
COMMENT ON COLUMN llm_configs.api_key IS 'API 密钥（使用 AES-256-GCM 加密存储）';
COMMENT ON COLUMN llm_configs.response_format IS 'LLM 响应格式：auto/json/anthropic_thinking/xml/plain_text';
COMMENT ON COLUMN llm_configs.extra_params IS '额外参数：{"temperature": 0.3, "max_tokens": 4096}';

-- ============================================================
-- 项目-LLM 配置关联表（多对多）
-- ============================================================

CREATE TABLE IF NOT EXISTS project_llm_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    llm_config_id UUID NOT NULL REFERENCES llm_configs(id) ON DELETE CASCADE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_project_llm UNIQUE (project_id, llm_config_id)
);

CREATE INDEX IF NOT EXISTS idx_project_llm_project ON project_llm_bindings(project_id);
CREATE INDEX IF NOT EXISTS idx_project_llm_config ON project_llm_bindings(llm_config_id);

COMMENT ON TABLE project_llm_bindings IS '项目-LLM 配置关联表';
COMMENT ON COLUMN project_llm_bindings.is_default IS '是否为项目默认配置';
COMMENT ON COLUMN project_llm_bindings.priority IS '优先级（数字越大优先级越高）';

-- ============================================================
-- 项目-Prompt 模板关联表（多对多）
-- ============================================================

CREATE TABLE IF NOT EXISTS project_prompt_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_project_prompt UNIQUE (project_id, template_id)
);

CREATE INDEX IF NOT EXISTS idx_project_prompt_project ON project_prompt_bindings(project_id);
CREATE INDEX IF NOT EXISTS idx_project_prompt_template ON project_prompt_bindings(template_id);

COMMENT ON TABLE project_prompt_bindings IS '项目-Prompt 模板关联表';
COMMENT ON COLUMN project_prompt_bindings.is_default IS '是否为项目默认模板';
COMMENT ON COLUMN project_prompt_bindings.priority IS '优先级（数字越大优先级越高）';

-- ============================================================
-- 种子数据
-- ============================================================

-- 平台默认配置
INSERT INTO platform_configs (platform, access_token, webhook_secret, api_url, enabled, description) VALUES
    ('gitee',  '', '', 'https://gitee.com/api/v5',   TRUE, 'Gitee 代码平台'),
    ('github', '', '', 'https://api.github.com',      TRUE, 'GitHub 代码平台'),
    ('gitlab', '', '', 'https://gitlab.com/api/v4',   TRUE, 'GitLab 代码平台')
ON CONFLICT (platform) DO NOTHING;

-- 通知渠道默认配置
INSERT INTO notification_configs (channel, enabled, webhook_url, secret, description) VALUES
    ('dingtalk', FALSE, '', '', '钉钉机器人通知'),
    ('feishu',   FALSE, '', '', '飞书机器人通知')
ON CONFLICT (channel) DO NOTHING;

-- 默认绑定：所有平台关联所有通知渠道
INSERT INTO platform_notification_bindings (platform_id, notification_id, enabled)
SELECT p.id, n.id, TRUE
FROM platform_configs p
CROSS JOIN notification_configs n
ON CONFLICT (platform_id, notification_id) DO NOTHING;

-- 默认 Prompt 模板
INSERT INTO prompt_templates (name, content, category, locale) VALUES
('default_zh', E'请对以下代码变更进行专业评审，返回 JSON 格式的评审意见。\n\n## 评审要求\n1. 仔细检查代码逻辑、安全性、性能和可维护性\n2. 识别潜在的 Bug、安全漏洞和性能问题\n3. 给出具体的改进建议\n4. 严重程度分级：critical（必须修复）、warning（建议修复）、suggestion（优化建议）、info（信息提示）\n\n## 变更文件\n{{files_context}}\n\n## Diff 内容\n```\n{{diff}}\n```\n\n## 输出格式\n请严格按照以下 JSON 格式输出：\n```json\n{\n    "summary": "整体评审摘要（2-3句话总结主要发现）",\n    "comments": [\n        {\n            "file_path": "文件路径",\n            "line_start": 起始行号,\n            "line_end": 结束行号,\n            "severity": "critical|warning|suggestion|info",\n            "message": "评审意见（中文）",\n            "suggestion": "具体的修复建议或代码示例"\n        }\n    ]\n}\n```', 'default', 'zh'),

('default_en', E'Please review the following code changes and return structured feedback in JSON format.\n\n## Review Guidelines\n1. Check code logic, security, performance, and maintainability\n2. Identify potential bugs, security vulnerabilities, and performance issues\n3. Provide specific improvement suggestions\n4. Severity levels: critical (must fix), warning (should fix), suggestion (nice to have), info (informational)\n\n## Changed Files\n{{files_context}}\n\n## Diff\n```\n{{diff}}\n```\n\n## Output Format\nReturn strictly in this JSON format:\n```json\n{\n    "summary": "Overall review summary (2-3 sentences)",\n    "comments": [\n        {\n            "file_path": "file path",\n            "line_start": start_line,\n            "line_end": end_line,\n            "severity": "critical|warning|suggestion|info",\n            "message": "review comment",\n            "suggestion": "specific fix suggestion or code example"\n        }\n    ]\n}\n```', 'default', 'en'),

('python_zh', E'请对以下 Python 代码变更进行专业评审，返回 JSON 格式的评审意见。\n\n## 评审要求\n1. 检查 Python 特有问题：类型安全、异常处理、资源管理\n2. 关注安全漏洞：注入攻击、不安全的反序列化、路径遍历\n3. 审查代码风格（PEP 8）、docstring、类型提示\n4. 检查性能问题：不必要的计算、N+1 查询、内存泄漏\n5. 严重程度：critical（必须修复）、warning（建议修复）、suggestion（优化）、info（信息）\n\n## 变更文件\n{{files_context}}\n\n## Diff 内容\n```\n{{diff}}\n```\n\n## 输出格式\n```json\n{\n    "summary": "整体评审摘要（2-3句话总结主要发现）",\n    "comments": [\n        {\n            "file_path": "文件路径",\n            "line_start": 起始行号,\n            "line_end": 结束行号,\n            "severity": "critical|warning|suggestion|info",\n            "message": "评审意见",\n            "suggestion": "修复建议或代码示例"\n        }\n    ]\n}\n```', 'python', 'zh'),

('java_zh', E'请对以下 Java 代码变更进行专业评审，返回 JSON 格式的评审意见。\n\n## 评审要求\n1. 检查 Java 最佳实践：SOLID 原则、设计模式、异常处理\n2. 关注线程安全、资源泄漏（连接/流未关闭）\n3. 检查空指针风险、空集合处理\n4. 审查日志规范、方法复杂度、命名规范\n5. 严重程度：critical（必须修复）、warning（建议修复）、suggestion（优化）、info（信息）\n\n## 变更文件\n{{files_context}}\n\n## Diff 内容\n```\n{{diff}}\n```\n\n## 输出格式\n```json\n{\n    "summary": "整体评审摘要",\n    "comments": [\n        {\n            "file_path": "文件路径",\n            "line_start": 起始行号,\n            "line_end": 结束行号,\n            "severity": "critical|warning|suggestion|info",\n            "message": "评审意见",\n            "suggestion": "修复建议或代码示例"\n        }\n    ]\n}\n```', 'java', 'zh')

ON CONFLICT (name) DO NOTHING;
