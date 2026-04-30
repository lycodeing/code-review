-- 系统配置表（通用 key-value 模式）
-- input_type: number / switch / text / select — 控制前端渲染哪种输入控件
-- options: JSON 数组，仅 select 类型使用，如 [{"label":"选项A","value":"a"}]
-- unit: 输入框后缀，如 "秒"、"MB"
-- default_value: 初始默认值，用于重置
CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(128) PRIMARY KEY,
    value TEXT NOT NULL,
    value_type VARCHAR(16) NOT NULL DEFAULT 'string',
    input_type VARCHAR(16) NOT NULL DEFAULT 'text',
    category VARCHAR(64) NOT NULL DEFAULT 'general',
    label VARCHAR(255) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    unit VARCHAR(16) NOT NULL DEFAULT '',
    default_value TEXT NOT NULL DEFAULT '',
    options JSONB,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 超时配置种子数据
INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order) VALUES
('review_timeout_seconds', '1800', 'int', 'number', 'timeout', '评审超时时间',
 '评审任务的超时时间（秒），超时后自动标记为 TIMEOUT 状态。-1 表示无限制', '秒', '1800', NULL, 1),
('llm_timeout_seconds', '120', 'int', 'number', 'timeout', 'AI 请求超时时间',
 '调用大模型的请求超时时间（秒）。-1 表示无限制', '秒', '120', NULL, 2),
('notification_timeout_seconds', '30', 'int', 'number', 'timeout', '通知发送超时时间',
 '发送通知（飞书/钉钉）的 HTTP 请求超时时间（秒）。-1 表示无限制', '秒', '30', NULL, 3)
ON CONFLICT (key) DO NOTHING;

-- 为已有数据库补充新列（兼容已有部署）
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_settings' AND column_name = 'value_type')
        AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_settings' AND column_name = 'input_type') THEN
        ALTER TABLE system_settings ADD COLUMN input_type VARCHAR(16) NOT NULL DEFAULT 'text';
        ALTER TABLE system_settings ADD COLUMN unit VARCHAR(16) NOT NULL DEFAULT '';
        ALTER TABLE system_settings ADD COLUMN default_value TEXT NOT NULL DEFAULT '';
        ALTER TABLE system_settings ADD COLUMN options JSONB;
        -- 回填已有行
        UPDATE system_settings SET input_type = 'number', unit = '秒', default_value = value WHERE category = 'timeout';
    END IF;
END $$;
