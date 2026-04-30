-- P0-2: PR 摘要自动生成 — review_tasks 表新增字段

ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS pr_description TEXT;
ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS description_posted BOOLEAN NOT NULL DEFAULT FALSE;

-- PR 摘要系统配置
INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order, created_at, updated_at)
VALUES
    ('pr_description_enabled', 'true', 'bool', 'switch', 'review', 'PR 摘要自动发布', '评审完成后是否自动生成并发布 PR 摘要评论', '', 'true', NULL, 40, NOW(), NOW()),
    ('pr_description_mode', 'full', 'string', 'select', 'review', 'PR 摘要模式', '摘要内容模式：summary_only 仅摘要 / full 摘要+统计+文件列表', '', 'full', '[{"label":"仅摘要","value":"summary_only"},{"label":"摘要+统计+文件","value":"full"}]', 41, NOW(), NOW())
ON CONFLICT (key) DO NOTHING;
