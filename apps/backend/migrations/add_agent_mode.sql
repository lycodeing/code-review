-- P1-4: 多智能体评审 — review_tasks 新增 agent_mode 字段 + 系统配置

ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS agent_mode VARCHAR(16) NOT NULL DEFAULT 'single';

-- 系统配置
INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order, created_at, updated_at)
VALUES
    ('agent_mode', 'single', 'string', 'select', 'review', '评审模式', 'single 单 Agent（现有模式）/ multi 多 Agent 并行', '', 'single', '[{"label":"单 Agent","value":"single"},{"label":"多 Agent 并行","value":"multi"}]', 60, NOW(), NOW()),
    ('agent_profiles', '[{"name":"security","focus":"安全漏洞、敏感信息泄露、注入风险","severity":"critical"},{"name":"performance","focus":"性能瓶颈、资源泄漏、N+1 查询","severity":"warning"},{"name":"quality","focus":"代码风格、可维护性、命名规范、重复代码","severity":"suggestion"}]', 'string', 'text', 'review', 'Agent 配置', '多 Agent 模式下的 Agent Profile JSON 数组', '', '[]', NULL, 61, NOW(), NOW())
ON CONFLICT (key) DO NOTHING;
