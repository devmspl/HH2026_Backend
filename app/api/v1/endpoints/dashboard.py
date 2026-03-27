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
    from sqlalchemy import or_
    
    # Hierarchy and Location filtering logic
    is_admin = current_user.is_superuser or str(current_user.role).upper() in [UserRole.SUPER_ADMIN.value, UserRole.ADMINISTRATOR.value]
    cur_role = str(current_user.role).upper()
    is_executive = cur_role == UserRole.EXECUTIVE.value
    
    user_ids_in_hierarchy = None
    
    if not is_admin:
        # 1. Start with recursive subordinates
        user_ids_in_hierarchy = [current_user.id]
        to_process = [current_user.id]
        processed = {current_user.id}
        
        while to_process:
            pid = to_process.pop()
            subs = db.query(User.id).filter(User.parent_id == pid, User.is_deleted == False).all()
            for s in subs:
                sid = s[0]
                if sid not in processed:
                    user_ids_in_hierarchy.append(sid)
                    to_process.append(sid)
                    processed.add(sid)

        # 2. Add location-based users (anyone in the same Province/District/Region/Camp)
        # This ensures a CAMP user sees all agents in their camp, even if not directly their children
        loc_filters = []
        if current_user.camp_id: loc_filters.append(User.camp_id == current_user.camp_id)
        elif current_user.region_id: loc_filters.append(User.region_id == current_user.region_id)
        elif current_user.district_id: loc_filters.append(User.district_id == current_user.district_id)
        elif current_user.province_id: loc_filters.append(User.province_id == current_user.province_id)
        
        if loc_filters and not is_executive:
             loc_users = db.query(User.id).filter(or_(*loc_filters), User.is_deleted == False).all()
             for u in loc_users:
                 if u[0] not in processed:
                     user_ids_in_hierarchy.append(u[0])
                     processed.add(u[0])

    # Common report filter
    report_q = db.query(Report)
    
    if not is_admin:
        from app.models.user import Region
        
        # Fast SQL JOIN for agents based on agent's assigned region (Auto-calculated via JOIN)
        if current_user.region_id:
            total_agents = db.query(User).join(Region, User.region_id == Region.id).filter(
                Region.id == current_user.region_id,
                User.is_deleted == False
            ).count()

            active_agents = db.query(User).join(Region, User.region_id == Region.id).filter(
                Region.id == current_user.region_id,
                User.is_active == True,
                User.is_deleted == False
            ).count()
        else:
            # Managed Agents = people in hierarchy/location EXCEPT current user (Fallback)
            managed_user_ids = [uid for uid in user_ids_in_hierarchy if uid != current_user.id]
            total_agents = db.query(User).filter(User.id.in_(managed_user_ids), User.is_deleted == False).count() if managed_user_ids else 0
            active_agents = db.query(User).filter(User.id.in_(managed_user_ids), User.is_deleted == False, User.is_active == True).count() if managed_user_ids else 0

        
        # Reports = from anyone in my scope (including me)
        report_q = report_q.filter(Report.agent_id.in_(user_ids_in_hierarchy))
    else:
        # Admin metrics
        # Total Agents = all agents except SUPER_ADMINs
        total_agents = db.query(User).filter(User.is_deleted == False, User.is_superuser == False).count()
        active_agents = db.query(User).filter(User.is_deleted == False, User.is_superuser == False, User.is_active == True).count()

    inactive_agents = total_agents - active_agents
    
    # Report Metrics counts
    pending_reports = report_q.filter(Report.status == "pending").count()
    approved_reports = report_q.filter(Report.status == "approved").count()
    rejected_reports = report_q.filter(Report.status == "rejected").count()
    total_reports = report_q.count()

    # Weekly Submission Trend
    from datetime import datetime, timedelta, time
    trend = []
    now = datetime.now()
    try:
        for i in range(6, -1, -1):
            target_date = (now - timedelta(days=i)).date()
            start_dt = datetime.combine(target_date, time.min)
            end_dt = datetime.combine(target_date, time.max)
            count = report_q.filter(Report.created_at >= start_dt, Report.created_at <= end_dt).count()
            trend.append({"date": target_date.strftime("%a"), "count": count})
    except Exception:
        trend = [{"date": "N/A", "count": 0} for _ in range(7)]

    # Notifications visibility
    notifs_list = []
    try:
        notif_q = db.query(NotificationLog)
        if user_ids_in_hierarchy is not None:
            # Non-admins only see notifications where they are the recipient
            notif_q = notif_q.filter(NotificationLog.recipient_id == current_user.id)
            
        raw_notifs = notif_q.order_by(NotificationLog.timestamp.desc()).limit(5).all()
        for n in raw_notifs:
            notifs_list.append({
                "id": n.id,
                "title": n.title or "Notification",
                "message": str(n.message) if n.message else "Notification",
                "icon": n.icon or "Notifications",
                "time": n.timestamp.isoformat() if n.timestamp else now.isoformat(),
                "status": n.status or "sent",
                "is_read": n.is_read or n.status == "read"
            })
    except Exception:
        pass
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
    # Hierarchy and Location filtering logic
    is_admin = current_user.is_superuser or current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]
    
    query = db.query(User).filter(User.is_deleted == False)
    
    if not is_admin:
        r = str(current_user.role).upper()
        if r == UserRole.CAMP.value and current_user.camp_id is not None:
            query = query.filter(User.camp_id == current_user.camp_id)
        elif r == UserRole.REGION.value and current_user.region_id is not None:
            query = query.filter(User.region_id == current_user.region_id)
        elif r == UserRole.DISTRICT.value and current_user.district_id is not None:
            query = query.filter(User.district_id == current_user.district_id)
        elif r == UserRole.PROVINCIAL.value and current_user.province_id is not None:
            query = query.filter(User.province_id == current_user.province_id)
        else:
            # Fallback: only see themselves/subordinates if no geo-id set
            # For GIS we might just want to show current user and their children
            query = query.filter((User.id == current_user.id) | (User.parent_id == current_user.id))

    agents = query.all()
    results = [
        {
            "id": a.id,
            "name": a.full_name,
            "role": a.role,
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
    
    # Geographic filtering
    r = str(current_user.role).upper()
    if r == UserRole.CAMP.value and current_user.camp_id is not None:
        query = query.filter(User.camp_id == current_user.camp_id)
    elif r == UserRole.REGION.value and current_user.region_id is not None:
        query = query.filter(User.region_id == current_user.region_id)
    elif r == UserRole.DISTRICT.value and current_user.district_id is not None:
        query = query.filter(User.district_id == current_user.district_id)
    elif r == UserRole.PROVINCIAL.value and current_user.province_id is not None:
        query = query.filter(User.province_id == current_user.province_id)
        
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
    
    # Permission Logic: 
    r = str(current_user.role).upper()
    # Agents only see their own media
    if r == UserRole.AGENT.value:
        query = query.filter(Report.agent_id == current_user.id)
    # Camp users only see media from their camp
    elif r == UserRole.CAMP.value and current_user.camp_id is not None:
        query = query.filter(Report.camp_id == current_user.camp_id)
    # Higher roles can see within their geography
    elif r == UserRole.REGION.value and current_user.region_id is not None:
        query = query.filter(Report.region_id == current_user.region_id)
    
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
