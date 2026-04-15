-- 迁移脚本：新增配置中心表（平台配置 + 通知渠道配置 + 平台-通知关联）
-- 使用方式：psql -U postgres -d code_review -f 003_platform_and_notification_configs.sql

-- ============================================================
-- 1. 代码平台配置表
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
-- 2. 通知渠道配置表
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
-- 3. 平台-通知关联表（多对多）
-- ============================================================
CREATE TABLE IF NOT EXISTS platform_notification_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES platform_configs(id) ON DELETE CASCADE,
    notification_id UUID NOT NULL REFERENCES notification_configs(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_platform_notification UNIQUE (platform_id, notification_id)
);

CREATE INDEX idx_bindings_platform ON platform_notification_bindings(platform_id);
CREATE INDEX idx_bindings_notification ON platform_notification_bindings(notification_id);

-- ============================================================
-- 4. 种子数据
-- ============================================================

-- 平台默认配置
INSERT INTO platform_configs (platform, access_token, webhook_secret, api_url, enabled, description) VALUES
    ('gitee',  '', '', 'https://gitee.com/api/v5', true, 'Gitee 代码平台'),
    ('github', '', '', 'https://api.github.com',   true, 'GitHub 代码平台'),
    ('gitlab', '', '', 'https://gitlab.com/api/v4', true, 'GitLab 代码平台')
ON CONFLICT (platform) DO NOTHING;

-- 通知渠道默认配置
INSERT INTO notification_configs (channel, enabled, webhook_url, secret, description) VALUES
    ('dingtalk', false, '', '', '钉钉机器人通知'),
    ('feishu',   false, '', '', '飞书机器人通知')
ON CONFLICT (channel) DO NOTHING;

-- 默认绑定：所有平台关联所有通知渠道
INSERT INTO platform_notification_bindings (platform_id, notification_id, enabled)
SELECT p.id, n.id, true
FROM platform_configs p
CROSS JOIN notification_configs n
ON CONFLICT (platform_id, notification_id) DO NOTHING;
