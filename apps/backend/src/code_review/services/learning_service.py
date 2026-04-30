"""偏好学习服务 — 将用户反馈沉淀为项目级偏好规则。"""

import logging
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import ReviewLearning, ReviewComment, ReviewTask

logger = logging.getLogger(__name__)

_SIMILARITY_THRESHOLD = 0.8
_MAX_PROMPT_LEARNINGS = 10


class LearningService:
    """团队偏好学习服务。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def process_feedback(self, comment_id: UUID, feedback: str) -> ReviewLearning | None:
        """用户反馈触发学习。thumbs_up 强化规则，thumbs_down 生成反向偏好。"""
        comment = await self._session.get(ReviewComment, comment_id)
        if not comment:
            logger.warning("评论不存在: %s", comment_id)
            return None

        task = await self._session.get(ReviewTask, comment.task_id)
        if not task:
            return None

        sentiment = "positive" if feedback == "thumbs_up" else "negative"
        rule_text = self._generate_rule(comment, sentiment)
        if not rule_text:
            return None

        existing = await self._find_similar(task.project_id, rule_text)
        if existing:
            existing.confidence += 1
            await self._session.commit()
            await self._session.refresh(existing)
            logger.info("强化已有偏好规则 (confidence=%d): %s", existing.confidence, existing.rule_text[:50])
            return existing

        learning = ReviewLearning(
            project_id=task.project_id,
            source_type="feedback",
            source_comment_id=comment_id,
            category=self._classify_category(comment),
            rule_text=rule_text,
            context=comment.message[:200] if comment.message else None,
            feedback_sentiment=sentiment,
            confidence=1,
            enabled=True,
        )
        self._session.add(learning)
        await self._session.commit()
        await self._session.refresh(learning)
        logger.info("新增偏好规则: %s", rule_text[:50])
        return learning

    async def get_learnings_for_prompt(self, project_id: UUID, limit: int = _MAX_PROMPT_LEARNINGS) -> str:
        """查询项目启用的偏好规则，格式化为 Prompt 注入文本。"""
        stmt = (
            select(ReviewLearning)
            .where(
                ReviewLearning.project_id == project_id,
                ReviewLearning.enabled.is_(True),
            )
            .order_by(ReviewLearning.confidence.desc(), ReviewLearning.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        learnings = list(result.scalars().all())

        if not learnings:
            return ""

        lines = []
        for l in learnings:
            priority = "高优先级" if l.confidence >= 3 else "参考"
            lines.append(f"- [{priority}] {l.rule_text}")
        return "\n".join(lines)

    async def add_manual_learning(
        self, project_id: UUID, rule_text: str, category: str = "style"
    ) -> ReviewLearning:
        """手动添加偏好规则。"""
        learning = ReviewLearning(
            project_id=project_id,
            source_type="manual",
            category=category,
            rule_text=rule_text,
            confidence=3,
            enabled=True,
        )
        self._session.add(learning)
        await self._session.commit()
        await self._session.refresh(learning)
        return learning

    async def merge_duplicate_learnings(self, project_id: UUID) -> int:
        """合并语义重复的偏好规则，叠加 confidence。"""
        stmt = (
            select(ReviewLearning)
            .where(ReviewLearning.project_id == project_id, ReviewLearning.enabled.is_(True))
            .order_by(ReviewLearning.confidence.desc())
        )
        result = await self._session.execute(stmt)
        all_learnings = list(result.scalars().all())

        merged_count = 0
        to_remove: list[UUID] = []

        for i, learning in enumerate(all_learnings):
            if learning.id in to_remove:
                continue
            for other in all_learnings[i + 1:]:
                if other.id in to_remove:
                    continue
                if self._compute_similarity(learning.rule_text, other.rule_text) > _SIMILARITY_THRESHOLD:
                    learning.confidence += other.confidence
                    to_remove.append(other.id)
                    merged_count += 1

        if to_remove:
            await self._session.execute(
                update(ReviewLearning)
                .where(ReviewLearning.id.in_(to_remove))
                .values(enabled=False)
            )
            await self._session.commit()

        return merged_count

    async def _find_similar(self, project_id: UUID, rule_text: str) -> ReviewLearning | None:
        stmt = (
            select(ReviewLearning)
            .where(ReviewLearning.project_id == project_id, ReviewLearning.enabled.is_(True))
        )
        result = await self._session.execute(stmt)
        for existing in result.scalars().all():
            if self._compute_similarity(existing.rule_text, rule_text) > _SIMILARITY_THRESHOLD:
                return existing
        return None

    @staticmethod
    def _compute_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def _generate_rule(comment: ReviewComment, sentiment: str) -> str:
        if not comment.message:
            return ""
        msg = comment.message[:300]
        if sentiment == "positive":
            return f"认可此代码风格: {msg}"
        return f"应避免此类代码: {msg}"

    @staticmethod
    def _classify_category(comment: ReviewComment) -> str:
        msg = (comment.message or "").lower()
        if any(kw in msg for kw in ("命名", "naming", "variable", "函数名", "类名")):
            return "naming"
        if any(kw in msg for kw in ("架构", "architecture", "设计", "design", "模式", "pattern")):
            return "architecture"
        if any(kw in msg for kw in ("性能", "performance", "优化", "optimize", "内存", "memory")):
            return "pattern"
        return "style"
