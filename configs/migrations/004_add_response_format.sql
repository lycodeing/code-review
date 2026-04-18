-- 004: 添加 LLM 响应格式配置支持
-- 为 llm_configs 表添加 response_format 字段，支持前端配置不同的 LLM 响应格式

-- 添加 response_format 字段到 llm_configs 表
ALTER TABLE llm_configs
ADD COLUMN IF NOT EXISTS response_format VARCHAR(32) NOT NULL DEFAULT 'auto';

-- 添加注释
COMMENT ON COLUMN llm_configs.response_format IS 'LLM 响应格式：auto/json/anthropic_thinking/xml/plain_text';

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_llm_configs_response_format ON llm_configs(response_format);

-- 更新现有记录的默认值（如果需要）
UPDATE llm_configs
SET response_format = 'auto'
WHERE response_format IS NULL OR response_format = '';

-- 添加检查约束，确保只允许有效的格式值
ALTER TABLE llm_configs
DROP CONSTRAINT IF EXISTS chk_llm_configs_response_format;

ALTER TABLE llm_configs
ADD CONSTRAINT chk_llm_configs_response_format
CHECK (response_format IN ('auto', 'json', 'anthropic_thinking', 'xml', 'plain_text'));
