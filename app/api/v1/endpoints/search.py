from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, Report, Customer, UserRole

router = APIRouter()

@router.get("/")
def global_search(
    query: str = Query(default="", description="Search term"),
    agent_id: Optional[int] = Query(default=None, description="Filter by agent ID"),
    date_from: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    location: Optional[str] = Query(default=None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enhanced global search across reports, agents, and customers with filters.
    """
    results = {
        "reports": [],
        "agents": [],
        "customers": []
    }
    
    # Build report query with filters
    report_query = db.query(Report)
    
    if query:
        report_query = report_query.filter(
            or_(
                Report.title.ilike(f"%{query}%"),
                Report.description.ilike(f"%{query}%"),
                Report.confirmation_no.ilike(f"%{query}%")
            )
        )
    
    if agent_id:
        report_query = report_query.filter(Report.agent_id == agent_id)
    
    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            report_query = report_query.filter(Report.created_at >= start_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            report_query = report_query.filter(Report.created_at <= end_date)
        except ValueError:
            pass
    
    if location:
        # Filter by agent location (assuming agents have location field)
        report_query = report_query.join(User).filter(User.location.ilike(f"%{location}%"))
    
    reports = report_query.limit(20).all()
    
    # Search Agents
    agent_query = db.query(User).filter(User.role == UserRole.AGENT)
    
    if query:
        agent_query = agent_query.filter(
            or_(
                User.full_name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
                User.phone.ilike(f"%{query}%")
            )
        )
    
    if location:
        agent_query = agent_query.filter(User.location.ilike(f"%{location}%"))
    
    agents = agent_query.limit(20).all()
    
    # Search Customers
    customer_query = db.query(Customer)
    
    if query:
        customer_query = customer_query.filter(
            or_(
                Customer.full_name.ilike(f"%{query}%"),
                Customer.phone.ilike(f"%{query}%"),
                Customer.email.ilike(f"%{query}%"),
                Customer.cnic.ilike(f"%{query}%")
            )
        )
    
    if location:
        customer_query = customer_query.filter(Customer.address.ilike(f"%{location}%"))
    
    customers = customer_query.limit(20).all()
    
    # Format results
    results["reports"] = [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description[:100] if r.description else "",
            "confirmation_no": r.confirmation_no,
            "status": r.status.value if r.status else "pending",
            "agent_id": r.agent_id,
            "gps_lat": r.gps_lat,
            "gps_lng": r.gps_lng,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in reports
    ]
    
    results["agents"] = [
        {
            "id": a.id,
            "name": a.full_name,
            "email": a.email,
            "phone": a.phone,
            "location": a.location,
            "is_active": a.is_active,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None
        }
        for a in agents
    ]
    
    results["customers"] = [
        {
            "id": c.id,
            "full_name": c.full_name,
            "phone": c.phone,
            "email": c.email,
            "address": c.address,
            "cnic": c.cnic,
            "category": c.category,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in customers
    ]
    
    return results


@router.get("/confirmation/{confirmation_no}")
def search_by_confirmation(
    confirmation_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Quick lookup by exact confirmation number.
    """
    report = db.query(Report).filter(
        Report.confirmation_no == confirmation_no
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found with this confirmation number")
    
    # Get agent details
    agent = db.query(User).filter(User.id == report.agent_id).first()
    
    return {
        "id": report.id,
        "title": report.title,
        "description": report.description,
        "confirmation_no": report.confirmation_no,
        "status": report.status.value if report.status else "pending",
        "agent": {
            "id": agent.id if agent else None,
            "name": agent.full_name if agent else "Unknown",
            "email": agent.email if agent else None
        },
        "gps_lat": report.gps_lat,
        "gps_lng": report.gps_lng,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None
    }
