"""团队偏好学习管理 API。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from code_review.models.db import ReviewLearning
from code_review.services.learning_service import LearningService

router = APIRouter(prefix="/api/v1/learnings", tags=["learnings"])


class LearningCreate(BaseModel):
    rule_text: str
    category: str = "style"


class LearningUpdate(BaseModel):
    rule_text: str | None = None
    enabled: bool | None = None
    category: str | None = None


class LearningMergeResult(BaseModel):
    merged_count: int


@router.get("/{project_id}")
async def list_learnings(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        from sqlalchemy import select
        stmt = (
            select(ReviewLearning)
            .where(ReviewLearning.project_id == project_id)
            .order_by(ReviewLearning.confidence.desc(), ReviewLearning.created_at.desc())
        )
        result = await session.execute(stmt)
        learnings = list(result.scalars().all())
        return [
            {
                "id": str(l.id),
                "project_id": str(l.project_id),
                "source_type": l.source_type,
                "category": l.category,
                "rule_text": l.rule_text,
                "context": l.context,
                "feedback_sentiment": l.feedback_sentiment,
                "confidence": l.confidence,
                "enabled": l.enabled,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "updated_at": l.updated_at.isoformat() if l.updated_at else None,
            }
            for l in learnings
        ]


@router.post("/{project_id}")
async def create_learning(project_id: UUID, body: LearningCreate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LearningService(session)
        learning = await svc.add_manual_learning(project_id, body.rule_text, body.category)
        return {
            "id": str(learning.id),
            "rule_text": learning.rule_text,
            "category": learning.category,
            "confidence": learning.confidence,
        }


@router.put("/{learning_id}")
async def update_learning(learning_id: UUID, body: LearningUpdate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        learning = await session.get(ReviewLearning, learning_id)
        if not learning:
            raise HTTPException(status_code=404, detail="偏好规则不存在")
        if body.rule_text is not None:
            learning.rule_text = body.rule_text
        if body.enabled is not None:
            learning.enabled = body.enabled
        if body.category is not None:
            learning.category = body.category
        await session.commit()
        await session.refresh(learning)
        return {
            "id": str(learning.id),
            "rule_text": learning.rule_text,
            "enabled": learning.enabled,
            "category": learning.category,
        }


@router.delete("/{learning_id}")
async def delete_learning(learning_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        learning = await session.get(ReviewLearning, learning_id)
        if not learning:
            raise HTTPException(status_code=404, detail="偏好规则不存在")
        await session.delete(learning)
        await session.commit()
        return {"detail": "已删除"}


@router.post("/{project_id}/merge")
async def merge_learnings(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LearningService(session)
        count = await svc.merge_duplicate_learnings(project_id)
        return LearningMergeResult(merged_count=count)
