-- 005: 添加项目-Prompt 模板关联表
-- 支持项目绑定多个 Prompt 模板，包含优先级和默认设置

CREATE TABLE IF NOT EXISTS project_prompt_bindings (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_project_prompt UNIQUE (project_id, template_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_project_prompt_project ON project_prompt_bindings(project_id);
CREATE INDEX IF NOT EXISTS idx_project_prompt_template ON project_prompt_bindings(template_id);

-- 字段注释
COMMENT ON TABLE project_prompt_bindings IS '项目-Prompt 模板关联表（多对多）';
COMMENT ON COLUMN project_prompt_bindings.is_default IS '是否为项目默认模板';
COMMENT ON COLUMN project_prompt_bindings.priority IS '优先级（数字越大优先级越高）';
COMMENT ON COLUMN project_prompt_bindings.enabled IS '绑定是否启用';
