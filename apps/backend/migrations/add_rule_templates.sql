-- 内置规则模板库：为 review_rules 表添加 is_builtin 字段并插入内置规则

ALTER TABLE review_rules ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN review_rules.is_builtin IS '是否为内置模板规则';

-- 插入 12 条内置规则模板（is_builtin=true），使用 $$ 引号避免正则中单引号冲突
INSERT INTO review_rules (id, name, description, rule_type, pattern, severity, message, file_pattern, enabled, is_builtin)
VALUES
    (gen_random_uuid(), 'python-print-debug',
     'Python 调试输出检测',
     'regex', $$print\s*\($$,
     'warning', '检测到 print() 调试输出，生产代码应使用日志框架替代',
     '**/*.py', TRUE, TRUE),

    (gen_random_uuid(), 'python-bare-except',
     'Python 裸异常捕获检测',
     'regex', $$except\s*:$$,
     'warning', '使用了裸 except:，应指定具体异常类型以避免掩盖错误',
     '**/*.py', TRUE, TRUE),

    (gen_random_uuid(), 'python-hardcoded-password',
     'Python 硬编码密码检测',
     'regex', $$password\s*=\s*['"][^'"]+['"]$$,
     'critical', '检测到硬编码密码，应使用环境变量或配置管理',
     '**/*.py', TRUE, TRUE),

    (gen_random_uuid(), 'java-system-out-println',
     'Java 调试输出检测',
     'regex', $$System\.out\.println$$,
     'warning', '检测到 System.out.println() 调试输出，生产代码应使用日志框架替代',
     '**/*.java', TRUE, TRUE),

    (gen_random_uuid(), 'java-todo-fixme',
     'Java 待办标记检测',
     'regex', $$TODO|FIXME$$,
     'info', '检测到 TODO/FIXME 标记，请确认是否需要在本次提交前处理',
     '**/*.java', TRUE, TRUE),

    (gen_random_uuid(), 'java-print-stack-trace',
     'Java 异常堆栈打印检测',
     'regex', $$e\.printStackTrace\(\)$$,
     'warning', '检测到 e.printStackTrace()，应使用日志框架记录异常信息',
     '**/*.java', TRUE, TRUE),

    (gen_random_uuid(), 'go-fmt-println',
     'Go 调试输出检测',
     'regex', $$fmt\.Println$$,
     'warning', '检测到 fmt.Println() 调试输出，生产代码应使用结构化日志库替代',
     '**/*.go', TRUE, TRUE),

    (gen_random_uuid(), 'go-panic-call',
     'Go panic 调用检测',
     'regex', $$panic\($$,
     'warning', '检测到 panic() 调用，应使用错误返回值处理异常情况',
     '**/*.go', TRUE, TRUE),

    (gen_random_uuid(), 'general-hardcoded-credentials',
     '硬编码凭证检测（通用）',
     'regex', $$(password|passwd|secret|api_key)\s*=\s*['"][^'"]{6,}['"]$$,
     'critical', '检测到硬编码凭证信息，应使用环境变量或密钥管理服务',
     '**', TRUE, TRUE),

    (gen_random_uuid(), 'general-hardcoded-ip',
     '硬编码 IP 地址检测',
     'regex', $$\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b$$,
     'warning', '检测到硬编码 IP 地址，应使用配置文件或服务发现机制',
     '**', TRUE, TRUE),

    (gen_random_uuid(), 'sql-select-star',
     'SQL 全表查询检测',
     'regex', $$SELECT \* FROM$$,
     'warning', '检测到 SELECT * 全表查询，应明确指定所需字段以提升性能',
     '**', TRUE, TRUE),

    (gen_random_uuid(), 'general-eval-usage',
     '危险 eval 调用检测',
     'regex', $$eval\s*\($$,
     'critical', '检测到 eval() 调用，存在代码注入安全风险',
     '**', TRUE, TRUE)

ON CONFLICT (name) DO NOTHING;
