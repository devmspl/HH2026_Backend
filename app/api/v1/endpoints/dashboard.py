from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Report, NotificationLog, AuditLog, ReportMedia, SystemConfiguration
from app.schemas import general as general_schema
import json

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

def _get_station_location(db: Session) -> Optional[tuple]:
    """Return (lat, lng) from system config 'station_location' or None."""
    row = db.query(SystemConfiguration).filter(SystemConfiguration.key == "station_location").first()
    if not row or not row.value:
        return None
    try:
        data = json.loads(row.value)
        lat = data.get("lat")
        lng = data.get("lng")
        if lat is not None and lng is not None:
            return (float(lat), float(lng))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


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


@router.get("/agents-with-distance")
def get_agents_with_distance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    For Region user: table of agents (in their region) with location and distance from station.
    Station is set in System Config key 'station_location' = {"lat": x, "lng": y}.
    Returns list of { id, name, lat, lng, last_seen, region_id, distance_km }.
    """
    from app.utils.geo import haversine_km

    station = _get_station_location(db)
    query = db.query(User).filter(User.is_deleted == False)
    # Region user sees only agents in their region
    if current_user.role == UserRole.REGION and current_user.region_id is not None:
        query = query.filter(User.region_id == current_user.region_id)
    agents = query.all()
    results = []
    for a in agents:
        lat, lng = a.last_lat, a.last_lng
        distance_km = None
        if station and lat is not None and lng is not None:
            distance_km = haversine_km(station[0], station[1], lat, lng)
        results.append({
            "id": a.id,
            "name": a.full_name,
            "lat": lat,
            "lng": lng,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
            "region_id": a.region_id,
            "distance_km": distance_km,
            "status": "online" if a.is_active else "offline",
        })
    return {"station_configured": station is not None, "agents": results}

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
    agent_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all uploaded media items with filtering and role-based visibility.
    """
    from app.models.user import ReportMedia, Report
    query = db.query(ReportMedia).join(Report)
    
    # Permission Logic: Agents only see their own media
    if current_user.role == UserRole.AGENT:
        query = query.filter(Report.agent_id == current_user.id)
    
    # Optional Filters
    if agent_id:
        query = query.filter(Report.agent_id == agent_id)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Report.title.ilike(search_filter)) |
            (Report.agent.has(full_name=search_filter))
        )
    
    items = query.all()
    results = []
    for item in items:
        results.append({
            "id": item.id,
            "report_id": item.report_id,
            "image_url": item.file_url,
            "agent_name": item.report.agent.full_name if item.report and item.report.agent else "Unknown",
            "report_title": item.report.title if item.report else "Deleted Report",
            "created_at": item.report.created_at if item.report else None
        })
    return results
