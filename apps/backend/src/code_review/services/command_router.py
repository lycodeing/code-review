"""命令路由器 — 从 PR 评论中解析命令。"""

import logging

logger = logging.getLogger(__name__)


class CommandRouter:
    """命令路由器，负责从评论内容中解析命令。"""

    COMMANDS: dict[str, str] = {
        "/review": "review",
        "/describe": "describe",
        "/improve": "improve",
        "/analyze": "analyze",
    }

    def parse_command(self, comment_body: str) -> tuple[str, str] | None:
        """解析评论中的命令。

        Args:
            comment_body: 评论内容

        Returns:
            (命令名称, 参数) 元组，如果不是命令则返回 None
        """
        body = comment_body.strip()
        body_lower = body.lower()

        for cmd_prefix, cmd_name in self.COMMANDS.items():
            if body_lower.startswith(cmd_prefix):
                # 保留原始大小写的参数
                args = body[len(cmd_prefix):].strip()
                logger.info("解析到命令: %s, 参数: %s", cmd_name, args)
                return cmd_name, args

        return None
