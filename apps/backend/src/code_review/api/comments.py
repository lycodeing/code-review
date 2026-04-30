"""评审评论反馈 API。"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from code_review.models.db import ReviewComment

router = APIRouter(prefix="/api/v1/comments", tags=["comments"])

_logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    feedback: str | None = None


@router.patch("/{comment_id}/feedback")
async def update_comment_feedback(
    comment_id: str,
    body: FeedbackRequest,
    request: Request,
):
    if body.feedback not in (None, "thumbs_up", "thumbs_down"):
        raise HTTPException(
            status_code=422, detail="feedback 值必须为 thumbs_up、thumbs_down 或 null",
        )

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        comment = await session.get(ReviewComment, UUID(comment_id))
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")
        comment.feedback = body.feedback
        await session.commit()
        await session.refresh(comment)

        # 触发偏好学习
        if body.feedback in ("thumbs_up", "thumbs_down"):
            try:
                from code_review.services.learning_service import LearningService
                svc = LearningService(session)
                await svc.process_feedback(UUID(comment_id), body.feedback)
            except Exception as e:
                _logger.warning("偏好学习失败（不影响反馈保存）: %s", e)

        return {"id": str(comment.id), "feedback": comment.feedback}
