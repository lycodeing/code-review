# PR 评论命令系统使用指南

## 概述

本系统允许用户通过在 PR/MR 评论中输入特定命令来触发不同的评审操作。

## 支持的命令

### `/review` - 触发完整评审

执行完整的代码评审流程，包括：
- 规则引擎检查（确定性规则）
- LLM 代码评审
- 评论发布
- PR 摘要生成
- 通知发送

**用法：**
```
/review
```

**带参数：**
```
/review 请重点关注性能问题
```
> 注：当前参数仅用于日志记录，不影响评审行为

---

### `/describe` - 生成 PR 描述

生成 PR 的描述摘要，包括：
- PR 标题
- 作者
- 源分支 → 目标分支
- 变更文件列表（最多 10 个）

**用法：**
```
/describe
```

**输出示例：**
```markdown
## PR 描述

**标题:** 优化数据库查询性能
**作者:** john_doe
**分支:** feature/perf → main

**变更文件（15 个）：**
- `src/db/query.py`
- `src/api/endpoints.py`
- `tests/test_query.py`
...
```

---

### `/improve` - 使用改进模板评审

使用专门的改进模板（`improve_zh`）触发评审，专注于代码改进建议。

**用法：**
```
/improve
```

> 注：需要在数据库中配置名为 `improve_zh` 的 Prompt 模板

---

### `/analyze` - 仅执行规则引擎检查

仅执行规则引擎检查，不调用 LLM。适合快速检查代码规范和潜在问题。

**用法：**
```
/analyze
```

**输出示例：**
```markdown
## 规则引擎检查结果

- **[critical]** `src/api/endpoints.py:45` — 硬编码的 API 密钥
- **[warning]** `src/db/query.py:123` — 未使用参数化查询
- **[suggestion]** `tests/test_query.py:67` — 测试覆盖率低于 80%
```

如果没有命中规则：
```markdown
## 规则引擎检查结果

未发现规则命中。
```

---

## 平台支持

### GitHub

在 PR 页面的评论框中输入命令并提交。

**触发事件：** `issue_comment` + `created`

**bot 识别：** 用户名以 `[bot]` 结尾（如 `github-actions[bot]`）

---

### GitLab

在 MR 页面的评论框中输入命令并提交。

**触发事件：** `note` + `create`

**bot 识别：** 用户名为 `gitlab` 或以 `[bot]` 结尾

---

### Gitee

在 PR 页面的评论框中输入命令并提交。

**触发事件：** 包含 `comment` 或 `note` 的事件

**bot 识别：** 用户名以 `[bot]` 结尾

---

## 最佳实践

1. **命令触发前**：确保 Webhook 已正确配置
2. **`/review`**：适合需要全面评审的场景
3. **`/analyze`**：适合快速检查代码规范，节省 LLM 配额
4. **`/describe`**：适合生成 PR 摘要，便于 Code Review
5. **`/improve`**：适合关注代码质量改进的场景

---

## 注意事项

1. **命令不区分大小写**：`/REVIEW`、`/Review`、`/review` 等效
2. **bot 评论忽略**：bot 用户的评论不会触发命令（防止循环）
3. **命令参数**：当前参数仅用于日志，不影响评审行为
4. **重复命令**：同一评论 ID 的重复命令会被去重忽略
5. **权限控制**：当前不检查用户权限，任何有评论权限的用户都可触发

---

## 示例工作流

### 场景 1：快速检查代码规范

```bash
# 开发者提交 PR 后
git push origin feature/new-feature

# 在 PR 页面评论
/analyze

# 系统返回规则引擎检查结果
# 如果发现问题，可以针对性修复
```

---

### 场景 2：全面评审

```bash
# 开发者提交 PR 后
git push origin feature/new-feature

# 在 PR 页面评论
/review

# 系统执行完整评审流程
# 包括规则引擎 + LLM 评审 + 评论发布 + 通知
```

---

### 场景 3：生成 PR 摘要

```bash
# PR 已经创建，需要生成摘要
# 在 PR 页面评论
/describe

# 系统返回 PR 描述
# 可以复制到 PR 描述字段
```

---

## 故障排查

### 命令没有响应

1. 检查 Webhook 是否正确配置
2. 检查项目是否在系统中注册
3. 检查平台配置（token、API URL）是否正确
4. 查看后端日志：`docker logs -f code-review-backend-1`

### Bot 触发循环

如果出现 bot 循环触发：
1. 检查 bot 用户名是否正确识别（以 `[bot]` 结尾）
2. 检查 bot 评论是否被过滤
3. 在后端日志中查找 "忽略 bot 用户评论" 的记录

### 命令解析失败

1. 确保命令以 `/` 开头（如 `/review`）
2. 确保命令拼写正确（不区分大小写）
3. 确保命令之间没有多余空格（如 `/ review` 不会被识别）

---

## 后续扩展

如需添加新命令：

1. 在 `services/command_router.py` 的 `COMMANDS` 字典添加映射
2. 在 `services/command_handler.py` 添加对应的 `handle_xxx()` 方法
3. 在 `services/review_orchestrator.py` 的 `match/case` 添加分支
4. 重新部署后端服务

**示例：**

```python
# services/command_router.py
COMMANDS: dict[str, str] = {
    "/review": "review",
    "/describe": "describe",
    "/improve": "improve",
    "/analyze": "analyze",
    "/summary": "summary",  # 新增
}

# services/command_handler.py
async def handle_summary(self, event, session_factory, adapter=None) -> None:
    # 生成代码变更摘要
    pass

# services/review_orchestrator.py
match command:
    # ...
    case "summary":
        await handler.handle_summary(event, self._session_factory, adapter)
```

---

**文档版本：** 1.0
**最后更新：** 2026-04-30
