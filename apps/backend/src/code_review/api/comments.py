"""评审评论反馈 API。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from code_review.models.db import ReviewComment

router = APIRouter(prefix="/api/v1/comments", tags=["comments"])


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
        return {"id": str(comment.id), "feedback": comment.feedback}
