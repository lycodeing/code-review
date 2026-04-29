"""仪表盘统计 API。"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request
from sqlalchemy import Date, cast, func, select

from code_review.models.db import ApiCallLog, Project, ReviewComment, ReviewTask

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _period_start(period: str, start_date: str | None = None, end_date: str | None = None) -> datetime | None:
    if period == "custom" and start_date:
        return datetime.fromisoformat(start_date).replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if period == "week":
        return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


@router.get("/stats")
async def dashboard_stats(
    request: Request,
    period: str = Query("all", pattern="^(week|month|all|custom)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project_count = (await session.execute(
            select(func.count()).select_from(Project)
        )).scalar() or 0

        overview_stmt = select(
            func.count().label("total"),
            func.count().filter(ReviewTask.status == "completed").label("completed"),
            func.count().filter(ReviewTask.status == "failed").label("failed"),
            func.count().filter(ReviewTask.status == "in_progress").label("in_progress"),
        )
        overview = (await session.execute(overview_stmt)).one()

        sd = _period_start(period, start_date, end_date)
        period_filter = ReviewTask.created_at >= sd if sd else True
        if period == "custom" and end_date:
            ed = datetime.fromisoformat(end_date).replace(tzinfo=UTC)
            period_filter = period_filter & (ReviewTask.created_at <= ed)

        period_stmt = select(
            func.count().label("review_count"),
            func.count().filter(ReviewTask.status == "completed").label("completed"),
            func.count().filter(ReviewTask.status == "failed").label("failed"),
            func.coalesce(func.sum(ReviewTask.critical_count), 0).label("critical_count"),
            func.coalesce(func.sum(ReviewTask.warning_count), 0).label("warning_count"),
            func.coalesce(func.sum(ReviewTask.total_comments), 0).label("total_comments"),
        ).where(period_filter)
        ps = (await session.execute(period_stmt)).one()

        sev_stmt = (
            select(ReviewComment.severity, func.count().label("count"))
            .join(ReviewTask, ReviewComment.task_id == ReviewTask.id)
            .where(period_filter)
            .group_by(ReviewComment.severity)
        )
        sev_rows = (await session.execute(sev_stmt)).all()
        sev_map = {r.severity: r.count for r in sev_rows}

        top_stmt = (
            select(
                Project.id.label("project_id"),
                Project.name.label("project_name"),
                func.count(ReviewTask.id).label("review_count"),
            )
            .join(ReviewTask, ReviewTask.project_id == Project.id)
            .where(period_filter)
            .group_by(Project.id, Project.name)
            .order_by(func.count(ReviewTask.id).desc())
            .limit(5)
        )
        top_rows = (await session.execute(top_stmt)).all()

        avg_comments = round(ps.total_comments / ps.review_count, 1) if ps.review_count else 0

        return {
            "overview": {
                "total_projects": project_count,
                "total_reviews": overview.total,
                "completed": overview.completed,
                "failed": overview.failed,
                "in_progress": overview.in_progress,
            },
            "period_stats": {
                "period": period,
                "start_date": sd.isoformat() if sd else None,
                "review_count": ps.review_count,
                "completed": ps.completed,
                "failed": ps.failed,
                "critical_count": ps.critical_count,
                "warning_count": ps.warning_count,
                "suggestion_count": sev_map.get("suggestion", 0),
                "info_count": sev_map.get("info", 0),
                "avg_comments_per_review": avg_comments,
            },
            "severity_distribution": [
                {"severity": s, "count": sev_map.get(s, 0)}
                for s in ("critical", "warning", "suggestion", "info")
            ],
            "top_projects": [
                {"project_id": str(r.project_id), "project_name": r.project_name, "review_count": r.review_count}
                for r in top_rows
            ],
        }


@router.get("/trend")
async def dashboard_trend(
    request: Request,
    days: int = Query(14, ge=1, le=90),
):
    session_factory = request.app.state.session_factory
    since = datetime.now(UTC) - timedelta(days=days)

    async with session_factory() as session:
        stmt = (
            select(
                cast(ReviewTask.created_at, Date).label("date"),
                func.count().label("total"),
                func.count().filter(ReviewTask.status == "completed").label("completed"),
                func.count().filter(ReviewTask.status == "failed").label("failed"),
                func.coalesce(func.sum(ReviewTask.critical_count), 0).label("critical"),
                func.coalesce(func.sum(ReviewTask.warning_count), 0).label("warning"),
            )
            .where(ReviewTask.created_at >= since)
            .group_by(cast(ReviewTask.created_at, Date))
            .order_by(cast(ReviewTask.created_at, Date))
        )
        rows = (await session.execute(stmt)).all()

    db_data = {str(r.date): r for r in rows}
    result = []
    for i in range(days):
        d = (since + timedelta(days=i + 1)).date()
        ds = str(d)
        if ds in db_data:
            r = db_data[ds]
            result.append({"date": ds, "total": r.total, "completed": r.completed, "failed": r.failed, "critical": r.critical, "warning": r.warning})
        else:
            result.append({"date": ds, "total": 0, "completed": 0, "failed": 0, "critical": 0, "warning": 0})

    return {"days": days, "data": result}


@router.get("/cost-analysis")
async def dashboard_cost_analysis(request: Request):
    """LLM 成本与效率分析：按项目、按模型、每日趋势及平均评审耗时。"""
    session_factory = request.app.state.session_factory
    since_30d = datetime.now(UTC) - timedelta(days=30)

    async with session_factory() as session:
        by_project_stmt = (
            select(
                Project.name.label("project_name"),
                func.count(ApiCallLog.id).label("total_calls"),
                func.coalesce(func.sum(ApiCallLog.duration_ms), 0).label("total_duration_ms"),
            )
            .join(ReviewTask, ApiCallLog.task_id == ReviewTask.id)
            .join(Project, ReviewTask.project_id == Project.id)
            .where(ApiCallLog.call_type == "llm")
            .group_by(Project.name)
            .order_by(func.sum(ApiCallLog.duration_ms).desc())
        )
        by_project_rows = (await session.execute(by_project_stmt)).all()

        by_model_stmt = (
            select(
                func.coalesce(ApiCallLog.provider, "unknown").label("provider"),
                func.count(ApiCallLog.id).label("total_calls"),
                func.coalesce(func.sum(ApiCallLog.duration_ms), 0).label("total_duration_ms"),
            )
            .where(ApiCallLog.call_type == "llm")
            .group_by(ApiCallLog.provider)
            .order_by(func.count(ApiCallLog.id).desc())
        )
        by_model_rows = (await session.execute(by_model_stmt)).all()

        daily_stmt = (
            select(
                cast(ApiCallLog.created_at, Date).label("date"),
                func.count(ApiCallLog.id).label("call_count"),
                func.coalesce(func.sum(ApiCallLog.duration_ms), 0).label("total_duration_ms"),
            )
            .where(ApiCallLog.call_type == "llm", ApiCallLog.created_at >= since_30d)
            .group_by(cast(ApiCallLog.created_at, Date))
            .order_by(cast(ApiCallLog.created_at, Date))
        )
        daily_rows = (await session.execute(daily_stmt)).all()

        avg_stmt = select(
            func.avg(
                func.extract("epoch", ReviewTask.completed_at - ReviewTask.started_at) * 1000
            ).label("avg_ms")
        ).where(
            ReviewTask.status == "completed",
            ReviewTask.started_at.isnot(None),
            ReviewTask.completed_at.isnot(None),
        )
        avg_row = (await session.execute(avg_stmt)).one()

    db_daily = {str(r.date): r for r in daily_rows}
    daily_trend = []
    for i in range(30):
        d = (since_30d + timedelta(days=i + 1)).date()
        ds = str(d)
        if ds in db_daily:
            r = db_daily[ds]
            daily_trend.append({"date": ds, "call_count": r.call_count, "total_duration_ms": r.total_duration_ms})
        else:
            daily_trend.append({"date": ds, "call_count": 0, "total_duration_ms": 0})

    return {
        "by_project": [
            {"project_name": r.project_name, "total_calls": r.total_calls, "total_duration_ms": r.total_duration_ms}
            for r in by_project_rows
        ],
        "by_model": [
            {"provider": r.provider, "total_calls": r.total_calls, "total_duration_ms": r.total_duration_ms}
            for r in by_model_rows
        ],
        "daily_trend": daily_trend,
        "avg_review_duration_ms": round(avg_row.avg_ms) if avg_row.avg_ms else 0,
    }
