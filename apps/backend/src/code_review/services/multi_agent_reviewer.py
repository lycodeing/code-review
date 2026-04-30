"""多 Agent 并行评审调度器。"""

import asyncio
import logging
from difflib import SequenceMatcher
from uuid import UUID

from code_review.core.agent_profile import AgentProfile
from code_review.core.platform import FileChange
from code_review.infrastructure.langchain_reviewer import LangChainReviewer
from code_review.models.config import LLMConfig

logger = logging.getLogger(__name__)

_DEDUP_SIMILARITY = 0.8

# 复用 core.llm 中的 ReviewResult
from code_review.core.llm import ReviewResult


class MultiAgentReviewer:
    """多 Agent 并行评审调度器。"""

    def __init__(self, profiles: list[AgentProfile]):
        self._profiles = profiles

    async def review(
        self,
        diff: str,
        files: list[FileChange],
        base_template: str,
        llm_candidates: list[tuple[str, LLMConfig]],
        task_id: UUID | None = None,
        session_factory=None,
        project_id: UUID | None = None,
    ) -> ReviewResult:
        """并行执行多 Agent 评审，返回汇总结果。"""
        tasks = []
        for profile in self._profiles:
            agent_prompt = profile.build_prompt(base_template)
            tasks.append(
                self._single_agent_review(
                    profile, diff, files, agent_prompt, llm_candidates,
                    task_id, session_factory, project_id,
                )
            )

        agent_results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: list[ReviewResult] = []
        for i, r in enumerate(agent_results):
            if isinstance(r, Exception):
                logger.warning("Agent %s 失败: %s", self._profiles[i].name, r)
            elif r is not None:
                successful.append(r)

        if not successful:
            raise RuntimeError("所有 Agent 均失败")

        return self._merge_agent_results(successful)

    async def _single_agent_review(
        self,
        profile: AgentProfile,
        diff: str,
        files: list[FileChange],
        prompt: str,
        llm_candidates: list[tuple[str, LLMConfig]],
        task_id: UUID | None = None,
        session_factory=None,
        project_id: UUID | None = None,
    ) -> ReviewResult:
        """单个 Agent 调用（复用 LangChainReviewer）。"""
        for config_name, llm_settings in llm_candidates:
            try:
                reviewer = LangChainReviewer(llm_settings)
                result = await reviewer.review(
                    diff=diff,
                    files=files,
                    prompt_template=prompt,
                    task_id=task_id,
                    session_factory=session_factory,
                    project_id=project_id,
                )
                logger.info("Agent %s 使用 %s 成功", profile.name, config_name)
                return result
            except Exception as e:
                logger.warning("Agent %s 配置 %s 失败: %s", profile.name, config_name, e)
                continue

        raise RuntimeError(f"Agent {profile.name} 所有 LLM 配置均失败")

    def _merge_agent_results(self, results: list[ReviewResult]) -> ReviewResult:
        """汇总多个 Agent 结果：去重 + 合并摘要。"""
        all_comments = []
        for r in results:
            all_comments.extend(r.comments)

        deduped = self._deduplicate(all_comments)
        summaries = [r.summary for r in results if r.summary]

        return ReviewResult(
            model="multi-agent",
            comments=deduped,
            summary="\n\n".join(summaries),
            total_tokens=sum(r.total_tokens for r in results),
            elapsed_seconds=max(r.elapsed_seconds for r in results),
        )

    @staticmethod
    def _deduplicate(comments: list) -> list:
        """去重策略：同文件同行号只保留严重程度最高的。"""
        severity_rank = {"critical": 4, "warning": 3, "suggestion": 2, "info": 1}
        seen: dict[tuple, int] = {}
        result: list = []

        for c in comments:
            key = (c.file_path, c.line_start)
            sev_val = severity_rank.get(
                c.severity.value if hasattr(c.severity, "value") else c.severity, 0
            )

            if key in seen:
                existing_idx = seen[key]
                existing_sev = severity_rank.get(
                    result[existing_idx].severity.value
                    if hasattr(result[existing_idx].severity, "value")
                    else result[existing_idx].severity, 0
                )
                if sev_val > existing_sev:
                    result[existing_idx] = c
                continue

            # 文本相似度检查
            is_dup = False
            for existing in result:
                if (existing.file_path == c.file_path and
                    existing.line_start == c.line_start):
                    msg_existing = existing.message or ""
                    msg_new = c.message or ""
                    if SequenceMatcher(None, msg_existing, msg_new).ratio() > _DEDUP_SIMILARITY:
                        is_dup = True
                        break
            if not is_dup:
                seen[key] = len(result)
                result.append(c)

        return result
