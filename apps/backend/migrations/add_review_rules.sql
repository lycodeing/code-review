-- 评审规则引擎：规则定义表和项目-规则绑定表

CREATE TABLE IF NOT EXISTS review_rules (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    rule_type VARCHAR(32) NOT NULL DEFAULT 'regex',
    pattern TEXT NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'warning',
    message TEXT NOT NULL,
    file_pattern VARCHAR(512) NOT NULL DEFAULT '**',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_rules_enabled ON review_rules(enabled);

CREATE TABLE IF NOT EXISTS project_rule_bindings (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES review_rules(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_project_rule_project ON project_rule_bindings(project_id);
CREATE INDEX IF NOT EXISTS idx_project_rule_rule ON project_rule_bindings(rule_id);

-- 种子数据：内置评审规则
INSERT INTO review_rules (id, name, description, rule_type, pattern, severity, message, file_pattern, enabled)
VALUES
    (gen_random_uuid(), 'no-eval', '禁止使用 eval() 函数', 'regex',
     'eval\s*\(', 'critical', '使用了 eval() 函数，存在代码注入风险', '**/*.py', TRUE),
    (gen_random_uuid(), 'no-innerHTML', '禁止直接使用 innerHTML 赋值', 'regex',
     '\.innerHTML\s*=', 'critical', '直接使用 innerHTML 存在 XSS 风险，建议使用 textContent 或安全的 DOM API', '**/*.js', TRUE),
    (gen_random_uuid(), 'no-hardcoded-secrets', '检测硬编码的密钥和密码', 'regex',
     '(?:password|passwd|secret|api_key|apikey)\s*[:=]\s*[''"][^''"]+[''"]', 'critical',
     '检测到硬编码的敏感信息（密码/密钥），应使用环境变量或配置管理', '**', TRUE)
ON CONFLICT (name) DO NOTHING;
