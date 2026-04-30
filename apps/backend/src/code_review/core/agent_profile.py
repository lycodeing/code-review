"""Agent 配置模型 — 描述单个评审 Agent 的关注点和参数。"""

from dataclasses import dataclass


@dataclass
class AgentProfile:
    """单个评审 Agent 的配置。"""

    name: str
    focus: str
    severity: str = "warning"
    system_prompt: str = ""

    def build_prompt(self, base_template: str) -> str:
        """在基础模板上追加 Agent 专属指令。"""
        additions = [
            f"\n\n**重点关注：** {self.focus}",
            f"**报告级别：** {self.severity}",
        ]
        if self.system_prompt:
            additions.insert(0, f"\n**角色：** {self.system_prompt}")
        return base_template + "\n".join(additions)
