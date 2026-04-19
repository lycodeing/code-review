-- 通知模板功能迁移脚本
-- 新增通知模板表、项目级模板绑定表，并为 notification_configs 加 template_id 列
-- 执行方式：psql -U postgres -d code_review -f add_notification_templates.sql

-- ============================================================
-- 通知模板表
-- ============================================================

CREATE TABLE IF NOT EXISTS notification_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    description VARCHAR(512) NOT NULL DEFAULT '',
    title_template VARCHAR(512) NOT NULL DEFAULT '',
    body_template TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_notification_template_name UNIQUE (name, channel)
);

CREATE INDEX IF NOT EXISTS idx_notification_templates_channel ON notification_templates(channel);
CREATE INDEX IF NOT EXISTS idx_notification_templates_is_default ON notification_templates(is_default);

COMMENT ON TABLE notification_templates IS '通知消息模板表';
COMMENT ON COLUMN notification_templates.channel IS '渠道标识：dingtalk / feishu';
COMMENT ON COLUMN notification_templates.title_template IS '卡片标题模板，支持 {{变量}} 语法';
COMMENT ON COLUMN notification_templates.body_template IS '正文 Markdown 模板，支持 {{变量}} 语法';
COMMENT ON COLUMN notification_templates.is_default IS '是否为该渠道的内置默认模板（不可删除）';

CREATE TRIGGER trigger_notification_templates_updated
    BEFORE UPDATE ON notification_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 项目级通知模板绑定表
-- ============================================================

CREATE TABLE IF NOT EXISTS project_notification_template_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    notification_id UUID NOT NULL REFERENCES notification_configs(id) ON DELETE CASCADE,
    template_id UUID REFERENCES notification_templates(id) ON DELETE SET NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_project_notification_binding UNIQUE (project_id, notification_id)
);

CREATE INDEX IF NOT EXISTS idx_proj_notif_tpl_project ON project_notification_template_bindings(project_id);
CREATE INDEX IF NOT EXISTS idx_proj_notif_tpl_notification ON project_notification_template_bindings(notification_id);
CREATE INDEX IF NOT EXISTS idx_proj_notif_tpl_template ON project_notification_template_bindings(template_id);

COMMENT ON TABLE project_notification_template_bindings IS '项目级通知模板绑定表（每个项目每个渠道最多一条）';
COMMENT ON COLUMN project_notification_template_bindings.template_id IS '指定模板，NULL 时降级到渠道默认模板';

-- ============================================================
-- 为 notification_configs 新增 template_id 列（渠道默认模板）
-- ============================================================

ALTER TABLE notification_configs
    ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES notification_templates(id) ON DELETE SET NULL;

COMMENT ON COLUMN notification_configs.template_id IS '渠道默认模板，NULL 时使用内置 is_default 模板';

-- ============================================================
-- 内置默认模板种子数据
-- ============================================================

-- 钉钉内置默认模板
INSERT INTO notification_templates (
    name,
    channel,
    description,
    title_template,
    body_template,
    enabled,
    is_default
) VALUES (
    'dingtalk_default',
    'dingtalk',
    '钉钉渠道内置默认模板',
    '代码评审 · {{project_name}}',
    E'### {{mr_title}}\n\n**{{mr_author}}** 提交于 **{{project_name}}**\n\n<font color="{{status_color}}">**{{status_emoji}} {{status_text}}**</font>\n\n🔴 严重 **{{critical_count}}**\t🟡 警告 **{{warning_count}}**\t🔵 建议 **{{suggestion_count}}**\tℹ️ 信息 **{{info_count}}**\n\n---\n\n{{summary}}',
    TRUE,
    TRUE
) ON CONFLICT (name) DO NOTHING;

-- 飞书内置默认模板
INSERT INTO notification_templates (
    name,
    channel,
    description,
    title_template,
    body_template,
    enabled,
    is_default
) VALUES (
    'feishu_default',
    'feishu',
    '飞书渠道内置默认模板',
    '{{status_emoji}} 代码评审 · {{project_name}}',
    E'**{{mr_title}}**\n提交人：{{mr_author}}\n\n🔴 严重 **{{critical_count}}** | 🟡 警告 **{{warning_count}}** | 🔵 建议 **{{suggestion_count}}** | ℹ️ 信息 **{{info_count}}**\n\n---\n{{summary}}',
    TRUE,
    TRUE
) ON CONFLICT (name) DO NOTHING;
