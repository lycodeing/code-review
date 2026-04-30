-- P0-3: 上下文增强系统配置

INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order, created_at, updated_at)
VALUES
    ('context_enhancement_enabled', 'true', 'bool', 'switch', 'review', '上下文增强', '评审时是否自动加载相关文件作为附加上下文', '', 'true', NULL, 50, NOW(), NOW()),
    ('context_max_files', '5', 'int', 'number', 'review', '最大上下文文件数', '自动加载的相关文件最大数量', '个', '5', NULL, 51, NOW(), NOW()),
    ('context_max_file_size', '10000', 'int', 'number', 'review', '单文件最大字符数', '单个上下文文件最大加载字符数', '字符', '10000', NULL, 52, NOW(), NOW())
ON CONFLICT (key) DO NOTHING;
