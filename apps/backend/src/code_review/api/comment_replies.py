"""评论回复 API 端点 — 支持多轮评审对话。"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from code_review.models.db import CommentReply, ReviewComment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/comments", tags=["comment-replies"])


class ReplyCreate(BaseModel):
    content: str = Field(..., min_length=1)
    author: str = Field(default="user")
    parent_reply_id: UUID | None = None


class ReplyResponse(BaseModel):
    id: UUID
    comment_id: UUID
    parent_reply_id: UUID | None
    author: str
    content: str
    source: str
    llm_context: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/{comment_id}/replies", response_model=list[ReplyResponse])
async def list_replies(comment_id: UUID, request: Request):
    """查询评论的所有回复。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        comment = await session.get(ReviewComment, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")

        stmt = (
            select(CommentReply)
            .where(CommentReply.comment_id == comment_id)
            .order_by(CommentReply.created_at.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()


@router.post("/{comment_id}/replies", response_model=ReplyResponse, status_code=201)
async def create_reply(comment_id: UUID, body: ReplyCreate, request: Request):
    """创建评论回复。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        comment = await session.get(ReviewComment, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")

        if body.parent_reply_id:
            parent = await session.get(CommentReply, body.parent_reply_id)
            if not parent or parent.comment_id != comment_id:
                raise HTTPException(status_code=400, detail="父回复不存在或不属于该评论")

        reply = CommentReply(
            comment_id=comment_id,
            parent_reply_id=body.parent_reply_id,
            author=body.author,
            content=body.content,
            source="user",
        )
        session.add(reply)
        await session.commit()
        await session.refresh(reply)
        return reply


@router.post("/{comment_id}/replies/llm-respond", response_model=ReplyResponse)
async def llm_respond(comment_id: UUID, request: Request):
    """让 LLM 对评论的回复生成回应。"""
    session_factory = request.app.state.session_factory
    config = request.app.state.config
    secret_key = request.app.state.config.server.secret_key

    async with session_factory() as session:
        comment = await session.get(ReviewComment, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")

        # 获取该评论的所有回复，构建对话上下文
        stmt = (
            select(CommentReply)
            .where(CommentReply.comment_id == comment_id)
            .order_by(CommentReply.created_at.asc())
        )
        result = await session.execute(stmt)
        replies = result.scalars().all()

        if not replies:
            raise HTTPException(status_code=400, detail="没有用户回复，无法生成 LLM 响应")

        # 构建对话历史
        conversation_lines = [
            f"## 原始评审评论",
            f"文件: {comment.file_path} (行 {comment.line_start}-{comment.line_end or comment.line_start})",
            f"严重程度: {comment.severity}",
            f"评论内容: {comment.message}",
        ]
        if comment.suggestion:
            conversation_lines.append(f"建议: {comment.suggestion}")

        conversation_lines.append("\n## 对话历史")
        for reply in replies:
            role = "开发者" if reply.source == "user" else "AI"
            conversation_lines.append(f"[{role}]: {reply.content}")

        conversation = "\n".join(conversation_lines)

        # 获取项目的 LLM 配置
        from code_review.services.llm_config_service import LLMConfigService
        from code_review.infrastructure.langchain_reviewer import LangChainReviewer
        from code_review.models.config import LLMConfig as LLMSettings
        from code_review.models.db import ReviewTask, Project

        task = await session.get(ReviewTask, comment.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="关联的评审任务不存在")

        llm_svc = LLMConfigService(session, secret_key)
        llm_config = await llm_svc.get_llm_config_for_project(task.project_id)

        if llm_config:
            api_key = await llm_svc.decrypt_api_key(llm_config.api_key)
            llm_settings = LLMSettings(
                model=llm_config.model_name,
                api_key=api_key,
                api_base=llm_config.api_base or "",
                temperature=0.5,
                max_tokens=1024,
                timeout=60,
            )
        else:
            llm_settings = config.llm

        # 调用 LLM
        reviewer = LangChainReviewer(llm_settings)
        from code_review.core.platform import FileChange
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=(
                "你是一位代码评审助手。根据评审评论和开发者的回复，提供有帮助的回应。"
                "回应应该简洁明了，如果开发者有疑问就解释清楚，如果开发者提出了修改建议就给出意见。"
                "使用中文回复。"
            )),
            HumanMessage(content=conversation),
        ]
        response = await reviewer._llm.ainvoke(messages)
        llm_content = response.content

        # 保存 LLM 回复
        reply = CommentReply(
            comment_id=comment_id,
            author="AI Reviewer",
            content=llm_content,
            source="llm",
            llm_context={"model": llm_settings.model, "conversation_turns": len(replies)},
        )
        session.add(reply)
        await session.commit()
        await session.refresh(reply)
        return reply


@router.delete("/replies/{reply_id}", status_code=204)
async def delete_reply(reply_id: UUID, request: Request):
    """删除评论回复。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        reply = await session.get(CommentReply, reply_id)
        if not reply:
            raise HTTPException(status_code=404, detail="回复不存在")
        await session.delete(reply)
        await session.commit()
