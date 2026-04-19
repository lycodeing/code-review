"""通知消息模板渲染工具。

将数据库中存储的 Mustache 风格模板（{{变量}}）渲染为最终的通知标题和正文。
"""

from code_review.core.notification import NotificationPayload


class NotificationRenderer:
    """通知模板渲染器。

    使用简单的字符串替换策略，将模板中所有 {{变量}} 占位符替换为实际值。
    发送前额外预计算 status_emoji / status_text / status_color 三个派生变量。
    """

    @staticmethod
    def _compute_status(payload: NotificationPayload) -> tuple[str, str, str]:
        """根据评审结果预计算状态相关变量。

        优先级：严重 > 警告 > 正常。

        Returns:
            (status_emoji, status_text, status_color)
        """
        if payload.critical_count > 0:
            return "⚠️", "发现严重问题，请及时处理", "#FF4D4F"
        if payload.warning_count > 0:
            return "🔔", "存在警告，建议关注", "#FA8C16"
        return "✅", "代码质量良好", "#52C41A"

    @staticmethod
    def render(
        title_template: str,
        body_template: str,
        payload: NotificationPayload,
    ) -> tuple[str, str]:
        """将模板渲染为 (标题, 正文) 元组。

        Args:
            title_template: 标题模板字符串，包含 {{变量}} 占位符。
            body_template: 正文模板字符串，包含 {{变量}} 占位符。
            payload: 通知载荷，提供所有变量的原始值。

        Returns:
            (rendered_title, rendered_body) 替换完成后的字符串元组。
        """
        status_emoji, status_text, status_color = NotificationRenderer._compute_status(payload)

        # 构建变量替换表
        variables: dict[str, str] = {
            "mr_title": payload.mr_title or "",
            "mr_author": payload.mr_author or "",
            "project_name": payload.project_name or "",
            "critical_count": str(payload.critical_count),
            "warning_count": str(payload.warning_count),
            "suggestion_count": str(payload.suggestion_count),
            "info_count": str(payload.info_count),
            "summary": (payload.summary or "").strip(),
            "mr_url": payload.mr_url or payload.detail_link or "",
            # 预计算状态变量
            "status_emoji": status_emoji,
            "status_text": status_text,
            "status_color": status_color,
        }

        def _replace(template: str) -> str:
            """对模板执行所有变量替换。"""
            result = template
            for key, value in variables.items():
                result = result.replace(f"{{{{{key}}}}}", value)
            return result

        return _replace(title_template), _replace(body_template)
