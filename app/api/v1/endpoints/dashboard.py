from typing import Any, List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Report, NotificationLog, AuditLog, ReportImage
from app.schemas import general as general_schema

router = APIRouter()

@router.get("/stats", response_model=general_schema.DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get dashboard KPIs.
    """
    total_agents = db.query(User).count()
    active_agents = db.query(User).filter(User.is_active == True).count()
    inactive_agents = total_agents - active_agents
    total_reports = db.query(Report).count()
    
    # Report Status Breakdown
    pending_reports = db.query(Report).filter(Report.status == "pending").count()
    approved_reports = db.query(Report).filter(Report.status == "approved").count()
    rejected_reports = db.query(Report).filter(Report.status == "rejected").count()

    # Weekly Submission Trend
    from datetime import datetime, timedelta
    trend = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        count = db.query(Report).filter(func.date(Report.created_at) == date.date()).count()
        trend.append({"date": date.strftime("%a"), "count": count})

    recent_notifs = db.query(NotificationLog).order_by(NotificationLog.timestamp.desc()).limit(5).all()
    notifs_list = [{"message": n.message, "time": n.timestamp.isoformat(), "status": n.status} for n in recent_notifs]
    
    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "inactive_agents": inactive_agents,
        "total_reports": total_reports,
        "recent_notifications": notifs_list,
        "pending_reports": pending_reports,
        "approved_reports": approved_reports,
        "rejected_reports": rejected_reports,
        "report_trend": trend
    }

@router.get("/gis-tracking")
def get_gis_tracking(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get live coordinates of agents.
    """
    agents = db.query(User).all()
    results = [
        {
            "id": a.id,
            "name": a.full_name,
            "lat": a.last_lat,
            "lng": a.last_lng,
            "status": "online" if a.is_active else "offline",
            "last_seen": a.last_seen.isoformat() if a.last_seen else None
        }
        for a in agents if a.last_lat is not None
    ]
    return results

@router.get("/audit-logs", response_model=List[general_schema.AuditLog])
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get system audit logs.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        return []
        
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    results = []
    for log in logs:
        results.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_name": log.user.full_name if log.user else "System",
            "action": log.action,
            "details": log.details,
            "timestamp": log.timestamp,
            "ip_address": log.ip_address
        })
    return results

@router.get("/media", response_model=List[general_schema.MediaItem])
def get_media(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all uploaded media items.
    """
    items = db.query(ReportImage).all()
    results = []
    for item in items:
        results.append({
            "id": item.id,
            "report_id": item.report_id,
            "image_url": item.image_url,
            "agent_name": item.report.agent.full_name if item.report and item.report.agent else "Unknown",
            "report_title": item.report.title if item.report else "Deleted Report",
            "created_at": item.report.created_at if item.report else None
        })
    return results
