-- LLM 配置中心迁移脚本
-- 创建日期: 2026-04-18

-- ============================================
-- LLM 配置表
-- ============================================
CREATE TABLE IF NOT EXISTS llm_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    provider VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    api_key TEXT NOT NULL DEFAULT '',
    api_base VARCHAR(512) NOT NULL DEFAULT '',
    extra_params JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_llm_configs_provider ON llm_configs(provider);
CREATE INDEX IF NOT EXISTS idx_llm_configs_enabled ON llm_configs(enabled);

-- 注释
COMMENT ON TABLE llm_configs IS 'LLM 提供商配置表';
COMMENT ON COLUMN llm_configs.name IS '配置名称（唯一标识）';
COMMENT ON COLUMN llm_configs.provider IS '提供商：openai/anthropic/deepseek/ollama/azure/bedrock/dashscope';
COMMENT ON COLUMN llm_configs.model_name IS '模型名称';
COMMENT ON COLUMN llm_configs.api_key IS 'API 密钥（使用 Fernet 加密存储）';
COMMENT ON COLUMN llm_configs.api_base IS 'API 基础地址';
COMMENT ON COLUMN llm_configs.extra_params IS '额外参数：{"temperature": 0.3, "max_tokens": 4096}';
COMMENT ON COLUMN llm_configs.enabled IS '是否启用该配置';

-- ============================================
-- 项目-LLM 配置关联表（多对多）
-- ============================================
CREATE TABLE IF NOT EXISTS project_llm_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    llm_config_id UUID NOT NULL REFERENCES llm_configs(id) ON DELETE CASCADE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, llm_config_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_project_llm_project ON project_llm_bindings(project_id);
CREATE INDEX IF NOT EXISTS idx_project_llm_config ON project_llm_bindings(llm_config_id);

-- 注释
COMMENT ON TABLE project_llm_bindings IS '项目-LLM 配置关联表';
COMMENT ON COLUMN project_llm_bindings.is_default IS '是否为项目默认配置（优先级最高）';
COMMENT ON COLUMN project_llm_bindings.priority IS '优先级（数字越大优先级越高，未标记 default 时使用）';
COMMENT ON COLUMN project_llm_bindings.enabled IS '绑定是否启用';
