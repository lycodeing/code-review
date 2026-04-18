-- 迁移脚本：新增 prompt_templates 表
-- 使用方式：psql -U postgres -d code_review -f 002_prompt_templates.sql

CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'default',
    locale VARCHAR(10) NOT NULL DEFAULT 'zh',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_prompt_template_name UNIQUE (name)
);

CREATE INDEX ix_prompt_template_category ON prompt_templates(category);
CREATE INDEX ix_prompt_template_locale ON prompt_templates(locale);

-- updated_at 自动更新触发器
CREATE TRIGGER trigger_prompt_templates_updated
    BEFORE UPDATE ON prompt_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 初始化默认模板数据
-- ============================================================

-- 通用默认模板（中文）
INSERT INTO prompt_templates (name, content, category, locale) VALUES
('default_zh', E'请对以下代码变更进行专业评审，返回 JSON 格式的评审意见。

## 评审要求
1. 仔细检查代码逻辑、安全性、性能和可维护性
2. 识别潜在的 Bug、安全漏洞和性能问题
3. 给出具体的改进建议
4. 严重程度分级：critical（必须修复）、warning（建议修复）、suggestion（优化建议）、info（信息提示）

## 变更文件
{{files_context}}

## Diff 内容
```
{{diff}}
```

## 输出格式
请严格按照以下 JSON 格式输出：
```json
{
    "summary": "整体评审摘要（2-3句话总结主要发现）",
    "comments": [
        {
            "file_path": "文件路径",
            "line_start": 起始行号,
            "line_end": 结束行号,
            "severity": "critical|warning|suggestion|info",
            "message": "评审意见（中文）",
            "suggestion": "具体的修复建议或代码示例"
        }
    ]
}
```',
'default', 'zh');

-- 通用默认模板（英文）
INSERT INTO prompt_templates (name, content, category, locale) VALUES
('default_en', E'Please review the following code changes and return structured feedback in JSON format.

## Review Guidelines
1. Check code logic, security, performance, and maintainability
2. Identify potential bugs, security vulnerabilities, and performance issues
3. Provide specific improvement suggestions
4. Severity levels: critical (must fix), warning (should fix), suggestion (nice to have), info (informational)

## Changed Files
{{files_context}}

## Diff
```
{{diff}}
```

## Output Format
Return strictly in this JSON format:
```json
{
    "summary": "Overall review summary (2-3 sentences)",
    "comments": [
        {
            "file_path": "file path",
            "line_start": start_line,
            "line_end": end_line,
            "severity": "critical|warning|suggestion|info",
            "message": "review comment",
            "suggestion": "specific fix suggestion or code example"
        }
    ]
}
```',
'default', 'en');

-- Python 模板（中文）
INSERT INTO prompt_templates (name, content, category, locale) VALUES
('python_zh', E'请对以下 Python 代码变更进行专业评审，返回 JSON 格式的评审意见。

## 评审要求
1. 检查 Python 特有问题：类型安全、异常处理、资源管理
2. 关注安全漏洞：注入攻击、不安全的反序列化、路径遍历
3. 审查代码风格（PEP 8）、docstring、类型提示
4. 检查性能问题：不必要的计算、N+1 查询、内存泄漏
5. 严重程度：critical（必须修复）、warning（建议修复）、suggestion（优化）、info（信息）

## 变更文件
{{files_context}}

## Diff 内容
```
{{diff}}
```

## 输出格式
```json
{
    "summary": "整体评审摘要（2-3句话总结主要发现）",
    "comments": [
        {
            "file_path": "文件路径",
            "line_start": 起始行号,
            "line_end": 结束行号,
            "severity": "critical|warning|suggestion|info",
            "message": "评审意见",
            "suggestion": "修复建议或代码示例"
        }
    ]
}
```',
'python', 'zh');

-- Java 模板（中文）
INSERT INTO prompt_templates (name, content, category, locale) VALUES
('java_zh', E'请对以下 Java 代码变更进行专业评审，返回 JSON 格式的评审意见。

## 评审要求
1. 检查 Java 最佳实践：SOLID 原则、设计模式、异常处理
2. 关注线程安全、资源泄漏（连接/流未关闭）
3. 检查空指针风险、空集合处理
4. 审查日志规范、方法复杂度、命名规范
5. 严重程度：critical（必须修复）、warning（建议修复）、suggestion（优化）、info（信息）

## 变更文件
{{files_context}}

## Diff 内容
```
{{diff}}
```

## 输出格式
```json
{
    "summary": "整体评审摘要",
    "comments": [
        {
            "file_path": "文件路径",
            "line_start": 起始行号,
            "line_end": 结束行号,
            "severity": "critical|warning|suggestion|info",
            "message": "评审意见",
            "suggestion": "修复建议或代码示例"
        }
    ]
}
```',
'java', 'zh');
