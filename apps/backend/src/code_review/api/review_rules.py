"""评审规则管理 API 端点。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from code_review.models.db import ReviewRule, ProjectRuleBinding

router = APIRouter(prefix="/api/v1/review-rules", tags=["review-rules"])


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    rule_type: str = Field(default="regex", pattern=r"^regex$")
    pattern: str = Field(..., min_length=1)
    severity: str = Field(default="warning", pattern=r"^(critical|warning|suggestion|info)$")
    message: str = Field(..., min_length=1)
    file_pattern: str = "**"
    enabled: bool = True


class RuleUpdate(BaseModel):
    description: str | None = None
    pattern: str | None = None
    severity: str | None = None
    message: str | None = None
    file_pattern: str | None = None
    enabled: bool | None = None


class RuleResponse(BaseModel):
    id: UUID
    name: str
    description: str
    rule_type: str
    pattern: str
    severity: str
    message: str
    file_pattern: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleBindingRequest(BaseModel):
    rule_id: UUID
    enabled: bool = True


@router.get("", response_model=list[RuleResponse])
async def list_rules(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewRule).order_by(ReviewRule.name)
        result = await session.execute(stmt)
        return result.scalars().all()


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(body: RuleCreate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        # 检查名称唯一性
        existing = await session.execute(
            select(ReviewRule).where(ReviewRule.name == body.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"规则名称 '{body.name}' 已存在")

        rule = ReviewRule(
            name=body.name,
            description=body.description,
            rule_type=body.rule_type,
            pattern=body.pattern,
            severity=body.severity,
            message=body.message,
            file_pattern=body.file_pattern,
            enabled=body.enabled,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: UUID, body: RuleUpdate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        rule = await session.get(ReviewRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")

        for key, value in body.model_dump(exclude_none=True).items():
            setattr(rule, key, value)
        rule.updated_at = datetime.now(tz=timezone.utc)
        await session.commit()
        await session.refresh(rule)
        return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        rule = await session.get(ReviewRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        await session.delete(rule)
        await session.commit()


@router.get("/project/{project_id}", response_model=list[RuleResponse])
async def list_project_rules(project_id: UUID, request: Request):
    """查询项目绑定的规则。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = (
            select(ReviewRule)
            .join(ProjectRuleBinding)
            .where(
                ProjectRuleBinding.project_id == project_id,
                ProjectRuleBinding.enabled.is_(True),
            )
            .order_by(ReviewRule.name)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


@router.post("/project/{project_id}/bind")
async def bind_rule_to_project(project_id: UUID, body: RuleBindingRequest, request: Request):
    """绑定规则到项目。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        rule = await session.get(ReviewRule, body.rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")

        stmt = select(ProjectRuleBinding).where(
            ProjectRuleBinding.project_id == project_id,
            ProjectRuleBinding.rule_id == body.rule_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.enabled = body.enabled
        else:
            binding = ProjectRuleBinding(
                project_id=project_id,
                rule_id=body.rule_id,
                enabled=body.enabled,
            )
            session.add(binding)
        await session.commit()
        return {"project_id": str(project_id), "rule_id": str(body.rule_id), "enabled": body.enabled}


@router.delete("/project/{project_id}/bind/{rule_id}", status_code=204)
async def unbind_rule_from_project(project_id: UUID, rule_id: UUID, request: Request):
    """取消规则与项目的绑定。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ProjectRuleBinding).where(
            ProjectRuleBinding.project_id == project_id,
            ProjectRuleBinding.rule_id == rule_id,
        )
        binding = (await session.execute(stmt)).scalar_one_or_none()
        if not binding:
            raise HTTPException(status_code=404, detail="绑定不存在")
        await session.delete(binding)
        await session.commit()
