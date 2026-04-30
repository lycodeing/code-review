-- P1-3: 新增企业微信和 Slack 默认通知模板

INSERT INTO notification_templates (id, name, channel, description, title_template, body_template, enabled, is_default)
VALUES (
    gen_random_uuid(), 'default_wecom', 'wecom', '企业微信默认模板',
    '{{project_name}} 评审通知',
    '> **{{project_name}}** 评审完成\n> MR: [{{mr_title}}]({{mr_url}})\n> 作者: {{mr_author}}\n> Critical: {{critical_count}} | Warning: {{warning_count}}',
    true, true
);

INSERT INTO notification_templates (id, name, channel, description, title_template, body_template, enabled, is_default)
VALUES (
    gen_random_uuid(), 'default_slack', 'slack', 'Slack 默认模板',
    '{{project_name}} Review Notification',
    '*{{project_name}}* review completed\n• MR: <{{mr_url}}|{{mr_title}}>\n• Author: {{mr_author}}\n• Critical: {{critical_count}} | Warning: {{warning_count}}',
    true, true
);
