"""仪表盘统计 API。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request
from sqlalchemy import select, func, case, cast, Date

from code_review.models.db import ReviewTask, ReviewComment, Project

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _period_start(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "week":
        return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


@router.get("/stats")
async def dashboard_stats(
    request: Request,
    period: str = Query("all", pattern="^(week|month|all)$"),
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

        start_date = _period_start(period)
        period_filter = ReviewTask.created_at >= start_date if start_date else True

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
                "start_date": start_date.isoformat() if start_date else None,
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
    since = datetime.now(timezone.utc) - timedelta(days=days)

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
