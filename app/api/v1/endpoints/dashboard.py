from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, cast, String, and_
from datetime import datetime
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Report, NotificationLog, AuditLog, ReportMedia, SystemConfiguration, Camp, Region, District, Province
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
    cur_role = str(current_user.role).upper()
    is_admin = current_user.is_superuser or cur_role in [UserRole.SUPER_ADMIN.value, UserRole.ADMINISTRATOR.value]
    
    # Robustness: Geographically anchored users should always see scoped data
    # unless they are super-users. This prevents misconfiguration leakage.
    if not current_user.is_superuser and (current_user.region_id or current_user.district_id or current_user.camp_id or current_user.province_id):
        is_admin = False

    is_executive = cur_role == UserRole.EXECUTIVE.value
    
    user_ids_in_hierarchy = None
    
    if not is_admin:
        # 1. Determine the strict user scope based on Role and Location
        if (cur_role == "CAMP" or cur_role == "AGENT") and current_user.camp_id:
            # STRICT CAMP ANCHOR: Only see users in this camp
            scope_users = db.query(User.id).filter(
                User.camp_id == current_user.camp_id, 
                User.is_deleted == False
            ).all()
            user_ids_in_hierarchy = [u[0] for u in scope_users]
        elif cur_role == "REGION" and current_user.region_id:
            # STRICT REGION ANCHOR: Only see users in this region
            scope_users = db.query(User.id).filter(
                User.region_id == current_user.region_id, 
                User.is_deleted == False
            ).all()
            user_ids_in_hierarchy = [u[0] for u in scope_users]
        elif cur_role == "DISTRICT" and current_user.district_id:
            # DISTRICT ANCHOR
            scope_users = db.query(User.id).filter(
                User.district_id == current_user.district_id, 
                User.is_deleted == False
            ).all()
            user_ids_in_hierarchy = [u[0] for u in scope_users]
        elif cur_role == "PROVINCIAL" and current_user.province_id:
            # STRICT PROVINCE ANCHOR
            scope_users = db.query(User.id).filter(
                User.province_id == current_user.province_id, 
                User.is_deleted == False
            ).all()
            user_ids_in_hierarchy = [u[0] for u in scope_users]
        else:
            # DEFAULT HIERARCHY: Recursive subordinates if no specific anchor is found
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

    # Common report filter
    report_q = db.query(Report)
    
    # Permission Scope: Admins and Executives see all reports (National scope). 
    # Others are restricted to their hierarchy/location.
    if not is_admin and not is_executive:
        # STRICT ROLE-BASED SCOPING
        if (cur_role == "CAMP" or cur_role == "AGENT") and current_user.camp_id:
            # 1. Total Agents in this specific Camp
            total_agents = db.query(User).filter(
                User.camp_id == current_user.camp_id,
                User.role.ilike('%AGENT%'),
                User.is_deleted == False
            ).count()

            # 2. Active Agents in this specific Camp
            active_agents = db.query(User).filter(
                User.camp_id == current_user.camp_id,
                User.role.ilike('%AGENT%'),
                User.is_deleted == False,
                User.is_active == True
            ).count()
        elif current_user.region_id:
            # 3. Total Agents in this specific Region (for Regional Managers)
            total_agents = db.query(User).filter(
                User.region_id == current_user.region_id,
                User.role.ilike('%AGENT%'),
                User.is_deleted == False
            ).count()

            active_agents = db.query(User).filter(
                User.region_id == current_user.region_id,
                User.role.ilike('%AGENT%'),
                User.is_deleted == False,
                User.is_active == True
            ).count()
        else:
            # Managed Agents = people in hierarchy/location EXCEPT current user (Fallback)
            managed_user_ids = [uid for uid in user_ids_in_hierarchy if uid != current_user.id]
            total_agents = db.query(User).filter(
                User.id.in_(managed_user_ids), 
                User.is_deleted == False,
                User.role.ilike('%AGENT%')
            ).count() if managed_user_ids else 0
            
            active_agents = db.query(User).filter(
                User.id.in_(managed_user_ids), 
                User.is_deleted == False, 
                User.is_active == True,
                User.role.ilike('%AGENT%')
            ).count() if managed_user_ids else 0

        
        # Reports = from anyone in my scope (including me)
        if cur_role == "AGENT":
            report_q = report_q.filter(Report.agent_id == current_user.id)
        else:
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
    # Farmer and Affiliation Metrics
    from app.models.user import Customer, Camp, Region, Province
    
    total_farmers = 0
    affiliated_farmers = 0
    total_expected_reports = 0
    total_camp_users = 0

    if is_admin or is_executive:
        total_farmers = db.query(func.sum(Province.total_customers)).scalar() or 0
        if not total_farmers:
            total_farmers = db.query(Customer).count() # Fallback to registered
        affiliated_farmers = db.query(Customer).count()
        total_expected_reports = total_agents
        total_camp_users = db.query(User).filter(User.is_deleted == False, User.role.ilike('%CAMP%')).count()
    elif cur_role == "AGENT":
        camp = db.query(Camp).filter(Camp.id == current_user.camp_id).first()
        total_farmers = camp.total_customers if camp else 0
        affiliated_farmers = db.query(Customer).filter(Customer.camp_id == current_user.camp_id).count()
        total_expected_reports = 1 # Each agent is expected to submit 1 report
        total_camp_users = db.query(User).filter(User.is_deleted == False, User.camp_id == current_user.camp_id, User.role.ilike('%CAMP%')).count()
    elif cur_role == "CAMP" and current_user.camp_id:
        camp = db.query(Camp).filter(Camp.id == current_user.camp_id).first()
        total_farmers = camp.total_customers if camp else 0
        affiliated_farmers = db.query(Customer).filter(Customer.camp_id == current_user.camp_id).count()
        total_expected_reports = total_agents
        total_camp_users = db.query(User).filter(User.is_deleted == False, User.camp_id == current_user.camp_id, User.role.ilike('%CAMP%')).count()
    elif current_user.region_id:
        region = db.query(Region).filter(Region.id == current_user.region_id).first()
        total_farmers = region.total_customers if region else 0
        affiliated_farmers = db.query(Customer).filter(Customer.region_id == current_user.region_id).count()
        total_expected_reports = total_agents
        total_camp_users = db.query(User).filter(User.is_deleted == False, User.region_id == current_user.region_id, User.role.ilike('%CAMP%')).count()
    elif current_user.district_id:
        dist = db.query(District).filter(District.id == current_user.district_id).first()
        total_farmers = dist.total_customers if dist else 0
        affiliated_farmers = db.query(Customer).filter(Customer.district_id == current_user.district_id).count()
        total_expected_reports = total_agents
        total_camp_users = db.query(User).filter(User.is_deleted == False, User.district_id == current_user.district_id, User.role.ilike('%CAMP%')).count()
    elif current_user.province_id:
        province = db.query(Province).filter(Province.id == current_user.province_id).first()
        total_farmers = province.total_customers if province else 0
        affiliated_farmers = db.query(Customer).filter(Customer.province_id == current_user.province_id).count()
        total_expected_reports = total_agents
        total_camp_users = db.query(User).filter(User.is_deleted == False, User.province_id == current_user.province_id, User.role.ilike('%CAMP%')).count()
    else:
        # Fallback for other roles/geographies
        total_farmers = 0
        affiliated_farmers = 0
        total_expected_reports = 0
        total_camp_users = 0

    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "inactive_agents": inactive_agents,
        "total_reports": total_reports,
        "recent_notifications": notifs_list,
        "pending_reports": pending_reports,
        "approved_reports": approved_reports,
        "rejected_reports": rejected_reports,
        "report_trend": trend,
        "total_farmers": total_farmers,
        "total_customers": total_farmers,
        "affiliated_farmers": affiliated_farmers,
        "total_camp_users": total_camp_users,
        "reports_submitted": total_reports,
        "total_expected_reports": total_expected_reports
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
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
    region_id: Optional[int] = None,
    camp_id: Optional[int] = None,
    q: Optional[str] = None,
    ne_lat: Optional[float] = None,
    ne_lng: Optional[float] = None,
    sw_lat: Optional[float] = None,
    sw_lng: Optional[float] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    Enterprise-grade GIS tracking with server-side search and viewport-based filtering.
    """
    from sqlalchemy import or_, cast, String, case, func
    
    cur_role = str(current_user.role).upper()
    # Robust admin check: superuser OR matches common admin role strings
    is_admin = current_user.is_superuser or any(r in cur_role for r in ["SUPER", "ADMIN", "EXECUTIVE", "NATIONAL"])
    
    skip = (page - 1) * page_size
    limit = page_size

    # Get global station location for distance fallback
    station = _get_station_location(db)
    s_lat = station[0] if station else 0
    s_lng = station[1] if station else 0

    # Hierarchical Station Reference for distance calculation in SQL
    target_lat = func.coalesce(Camp.lat, Region.lat, District.lat, Province.lat, s_lat)
    target_lng = func.coalesce(Camp.lng, Region.lng, District.lng, Province.lng, s_lng)
    
    # Haversine distance expression (KM)
    rad_lat1 = func.radians(User.last_lat)
    rad_lat2 = func.radians(target_lat)
    rad_lng_diff = func.radians(target_lng - User.last_lng)
    cos_val = func.cos(rad_lat1) * func.cos(rad_lat2) * func.cos(rad_lng_diff) + func.sin(rad_lat1) * func.sin(rad_lat2)
    safe_cos = case((cos_val > 1, 1), (cos_val < -1, -1), else_=cos_val)
    distance_expr = 6371 * func.acos(safe_cos)

    # Base query - Use ilike for case-insensitive role matching
    query = db.query(User).filter(User.is_deleted == False, User.role.ilike('%AGENT%'))
    
    # Joins for distance calculation
    query = query.outerjoin(Camp, User.camp_id == Camp.id)\
                 .outerjoin(Region, User.region_id == Region.id)\
                 .outerjoin(District, User.district_id == District.id)\
                 .outerjoin(Province, User.province_id == Province.id)
    
    # Apply administrative scope for non-admins
    if not is_admin:
        if cur_role == "CAMP" and current_user.camp_id:
            query = query.filter(User.camp_id == current_user.camp_id)
        elif cur_role == "REGION" and current_user.region_id:
            query = query.filter(User.region_id == current_user.region_id)
        elif cur_role == "DISTRICT" and current_user.district_id:
            query = query.filter(User.district_id == current_user.district_id)
        elif cur_role == "PROVINCIAL" and current_user.province_id:
            query = query.filter(User.province_id == current_user.province_id)
        else:
            query = query.filter(User.id == current_user.id)

    # Apply manual filters
    if province_id: query = query.filter(User.province_id == province_id)
    if district_id: query = query.filter(User.district_id == district_id)
    if region_id: query = query.filter(User.region_id == region_id)
    if camp_id: query = query.filter(User.camp_id == camp_id)
    if status and status != 'all':
        if status.lower() == 'online':
            query = query.filter(User.is_active == True)
        elif status.lower() == 'offline':
            query = query.filter(User.is_active == False)
        else:
            query = query.filter(User.account_status == status)

    # Server-side Search (P0)
    if q:
        query = query.filter(or_(
            User.full_name.ilike(f"%{q}%"),
            cast(User.id, String).ilike(f"%{q}%")
        ))

    # Viewport-based Filtering (P1)
    if ne_lat and sw_lat and ne_lng and sw_lng:
        query = query.filter(
            User.last_lat <= ne_lat,
            User.last_lat >= sw_lat,
            User.last_lng <= ne_lng,
            User.last_lng >= sw_lng
        )

    # Fetch with lightweight projection
    total = query.count()
    query = query.with_entities(
        User.id, User.full_name, User.role, User.last_lat, User.last_lng, User.last_seen, User.account_status, User.is_active,
        distance_expr.label("distance_km")
    )
    
    agents = query.order_by(User.last_seen.desc().nullslast()).offset(skip).limit(limit).all()
    
    return {
        "items": [
            {
                "id": a.id,
                "name": a.full_name,
                "role": a.role,
                "agent_lat": a.last_lat,
                "agent_lng": a.last_lng,
                "last_seen": a.last_seen.isoformat() if a.last_seen else None,
                "status": "online" if a.is_active else "offline",
                "distance_km": round(float(a.distance_km), 2) if a.distance_km is not None else None
            } for a in agents
        ],
        "total": total,
        "page": page,
        "page_size": limit
    }


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
    query = db.query(User).filter(User.is_deleted == False, User.role.ilike('%AGENT%'))
    
    # Geographic filtering
    r = str(current_user.role).upper()
    if r == UserRole.CAMP.value and current_user.camp_id is not None:
        query = query.filter(User.camp_id == current_user.camp_id)
    elif r == UserRole.REGION.value and current_user.region_id is not None:
        query = query.filter(User.region_id == current_user.region_id)
        # Removed exception for CAMP users to align with Agent-only monitoring requirement
        pass
    elif r == UserRole.DISTRICT.value and current_user.district_id is not None:
        query = query.filter(User.district_id == current_user.district_id)
    elif r == UserRole.PROVINCIAL.value and current_user.province_id is not None:
        query = query.filter(User.province_id == current_user.province_id)
        
    # Efficiently load relationships to avoid N+1 queries
    agents = query.options(
        joinedload(User.camp),
        joinedload(User.region),
        joinedload(User.district),
        joinedload(User.province)
    ).all()
    
    results = []
    for a in agents:
        agent_lat, agent_lng = a.last_lat, a.last_lng
        
        # HIERARCHICAL STATION SELECTION:
        # 1. Camp Location
        # 2. Region Location
        # 3. District Location
        # 4. Province Location
        # 5. Global Station Configuration
        
        target_station = None
        
        if a.camp and a.camp.lat is not None and a.camp.lng is not None:
            target_station = (a.camp.lat, a.camp.lng)
        elif a.region and a.region.lat is not None and a.region.lng is not None:
            target_station = (a.region.lat, a.region.lng)
        elif a.district and a.district.lat is not None and a.district.lng is not None:
            target_station = (a.district.lat, a.district.lng)
        elif a.province and a.province.lat is not None and a.province.lng is not None:
            target_station = (a.province.lat, a.province.lng)
        else:
            target_station = station # Fallback to global setting
            
        distance_km = None
        if target_station and agent_lat is not None and agent_lng is not None:
            distance_km = haversine_km(target_station[0], target_station[1], agent_lat, agent_lng)
            # Round to 2 decimal places for cleaner UI
            distance_km = round(distance_km, 2)
            
        results.append({
            "id": a.id,
            "name": a.full_name,
            "role": a.role,
            "profession": a.profession,
            "lat": agent_lat,
            "lng": agent_lng,
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

@router.get("/district-summary", response_model=general_schema.DistrictSummary)
def get_district_summary(
    district_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get District-level metrics and region-wise reporting status.
    """
    from app.models.user import Region, Camp, Customer, UserRole, District, Report
    
    # 1. Scope Determination
    target_district_id = district_id or current_user.district_id
    
    # NEW: Handle Provincial-wide view if no district specified
    is_provincial_view = False
    user_role_upper = str(current_user.role).upper()
    
    if not target_district_id:
        if "PROVINCIAL" in user_role_upper and current_user.province_id:
            is_provincial_view = True
        else:
            raise HTTPException(status_code=400, detail="District ID is required")
        
    # Permission check: District User can only see their own district
    user_role_upper = str(current_user.role).upper()
    if "DISTRICT" in user_role_upper:
        if current_user.district_id != target_district_id:
            raise HTTPException(status_code=403, detail="You can only view your own district's summary")
    
    # Permission check: Provincial User can see any district in their province
    if "PROVINCIAL" in user_role_upper:
        # Check if the district belongs to their province
        dist = db.query(District).filter(District.id == target_district_id).first()
        if not dist or dist.province_id != current_user.province_id:
            raise HTTPException(status_code=403, detail="You can only view districts within your province")

    # 2. Total Farmers in Scope
    if is_provincial_view:
        total_farmers = db.query(Customer).filter(Customer.province_id == current_user.province_id).count()
        regions = db.query(Region).filter(Region.province_id == current_user.province_id).all()
    else:
        total_farmers = db.query(Customer).filter(Customer.district_id == target_district_id).count()
        regions = db.query(Region).filter(Region.district_id == target_district_id).all()
    agents_by_region = []
    customers_by_region = []
    region_statuses = []

    for region in regions:
        # Agents count
        agent_count = db.query(User).filter(User.region_id == region.id, User.role.ilike('%AGENT%')).count()
        agents_by_region.append({"id": region.id, "name": region.name, "count": agent_count})

        # Customers count
        customer_count = db.query(Customer).filter(Customer.region_id == region.id).count()
        customers_by_region.append({"id": region.id, "name": region.name, "count": customer_count})

        # 4. Region-wise Reporting Status
        total_camps = db.query(Camp).filter(Camp.region_id == region.id).count()
        
        # A camp is "submitted" if it has at least one report? 
        # Or let's group reports by camp_id and count distinct camp_ids
        submitted_camps = db.query(Report.camp_id).filter(
            Report.region_id == region.id,
            Report.camp_id.isnot(None)
        ).distinct().count()

        # Status Logic
        if total_camps == 0:
            status = "N/A"
        elif region.is_approved:
            status = "GREEN"
        elif submitted_camps == 0:
            status = "RED"
        elif submitted_camps < total_camps:
            status = "ORANGE"
        else:
            status = "BLUE"

        region_statuses.append({
            "id": region.id,
            "name": region.name,
            "total_camps": total_camps,
            "submitted_camps": submitted_camps,
            "is_approved": bool(region.is_approved),
            "status": status
        })

    return {
        "total_farmers": total_farmers,
        "agents_by_region": agents_by_region,
        "customers_by_region": customers_by_region,
        "region_statuses": region_statuses
    }
