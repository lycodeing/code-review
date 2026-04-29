-- 通知渠道配置表增加 extra_config JSON 字段
-- 用于存储渠道特有的配置（如 email 的 SMTP 设置）

ALTER TABLE notification_configs
    ADD COLUMN IF NOT EXISTS extra_config JSONB;

COMMENT ON COLUMN notification_configs.extra_config IS '渠道特有配置（如 email 的 SMTP 设置）';