from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Customer, Camp, Region, District, Province, RegionalCrop, CropFamily, Report

router = APIRouter()

@router.get("/summary")
def get_executive_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all aggregated national-level data for the Executive user.
    """
    # 1. SUMMARY METRICS (National Level)
    total_agents = db.query(User).filter(User.role == UserRole.AGENT, User.is_deleted == False).count()
    total_farmers = db.query(Customer).count()
    
    # Check for both "Affiliated" and "Registered" as requested by requirements
    affiliated_farmers = db.query(Customer).filter(
        (Customer.membership_status == "Affiliated") | (Customer.membership_status == "Registered")
    ).count()
    
    affiliated_percentage = (affiliated_farmers / total_farmers * 100) if total_farmers > 0 else 0
    total_camp_users = db.query(User).filter(User.role == UserRole.CAMP, User.is_deleted == False).count()
    total_camps = db.query(Camp).count()

    # 2. SURVEY PROGRESS
    total_camps_national = total_camps
    submitted_camps_national = db.query(Report.camp_id).filter(Report.camp_id.isnot(None)).distinct().count()
    survey_camps_percentage = (submitted_camps_national / total_camps_national * 100) if total_camps_national > 0 else 0

    total_regions = db.query(Region).count()
    completed_regions = db.query(Region).filter(Region.is_approved == True).count()
    completed_regions_percentage = (completed_regions / total_regions * 100) if total_regions > 0 else 0

    # 3. CROPS DATA: regional crops grouped by family
    crops_by_family_raw = db.query(
        CropFamily.family_name, 
        func.count(RegionalCrop.id)
    ).join(RegionalCrop, RegionalCrop.family_id == CropFamily.id).group_by(CropFamily.family_name).all()
    
    crops_by_family = [{"family": r[0], "count": r[1]} for r in crops_by_family_raw]

    # 4. TABLES
    # We'll pull all regions and calculate stats for each
    all_regions = db.query(Region).all()
    
    # A. Agents by Region Table
    agents_by_region = []
    # B. Farmer Assignment Table
    farmer_assignment_by_region = []
    # Region Statuses (needed for Survey Progress and Overview)
    region_statuses = []

    green_regions_count = 0

    for reg in all_regions:
        # 1. Agents Stats
        reg_agents = db.query(User).filter(User.region_id == reg.id, User.role == UserRole.AGENT, User.is_deleted == False).count()
        reg_camp_users = db.query(User).filter(User.region_id == reg.id, User.role == UserRole.CAMP, User.is_deleted == False).count()
        reg_affiliated = db.query(Customer).filter(
            Customer.region_id == reg.id,
            ((Customer.membership_status == "Affiliated") | (Customer.membership_status == "Registered"))
        ).count()
        
        agents_by_region.append({
            "region_name": reg.name,
            "agents_count": reg_agents,
            "camp_users_count": reg_camp_users,
            "affiliated_farmers_count": reg_affiliated
        })
        
        # 2. Farmer Assignment Stats
        reg_total_farmers = db.query(Customer).filter(Customer.region_id == reg.id).count()
        reg_assigned_farmers = db.query(Customer).filter(
            Customer.region_id == reg.id,
            (Customer.assigned_camp_user_id.isnot(None))
        ).count()
        reg_assignment_percentage = (reg_assigned_farmers / reg_total_farmers * 100) if reg_total_farmers > 0 else 0
        
        farmer_assignment_by_region.append({
            "region_name": reg.name,
            "assigned_farmers": reg_assigned_farmers,
            "total_farmers": reg_total_farmers,
            "percentage": round(reg_assignment_percentage, 2)
        })

        # 3. Status Logic (Ported from dashboard.py)
        total_camps_in_reg = db.query(Camp).filter(Camp.region_id == reg.id).count()
        submitted_camps_in_reg = db.query(Report.camp_id).filter(
            Report.region_id == reg.id,
            Report.camp_id.isnot(None)
        ).distinct().count()

        if total_camps_in_reg == 0:
            status = "N/A"
        elif reg.is_approved:
            status = "GREEN"
            green_regions_count += 1
        elif submitted_camps_in_reg == 0:
            status = "RED"
        elif submitted_camps_in_reg < total_camps_in_reg:
            status = "ORANGE"
        else:
            status = "BLUE"

        region_statuses.append({
            "id": reg.id,
            "name": reg.name,
            "total_camps": total_camps_in_reg,
            "submitted_camps": submitted_camps_in_reg,
            "status": status
        })

    # Update completed regions count based on calculated statuses
    total_regions_count = len(all_regions)
    completed_regions_percentage = (green_regions_count / total_regions_count * 100) if total_regions_count > 0 else 0

    # 5. MAP FEATURE: Show all agents nationwide on a live map
    agents_map = db.query(User).filter(
        User.role == UserRole.AGENT,
        User.is_deleted == False,
        User.last_lat.isnot(None),
        User.last_lng.isnot(None)
    ).all()
    
    map_data = [
        {
            "id": a.id,
            "name": a.full_name,
            "lat": a.last_lat,
            "lng": a.last_lng,
            "status": "online" if a.is_active else "offline"
        }
        for a in agents_map
    ]

    return {
        "summary_metrics": {
            "total_agents": total_agents,
            "total_farmers": total_farmers,
            "affiliated_farmers": affiliated_farmers,
            "affiliated_percentage": round(affiliated_percentage, 2),
            "total_camp_users": total_camp_users,
            "total_camps": total_camps
        },
        "survey_progress": {
            "uploaded_survey_camps": {
                "submitted": submitted_camps_national,
                "total": total_camps_national,
                "percentage": round(survey_camps_percentage, 2)
            },
            "completed_regions": {
                "completed": green_regions_count,
                "total": total_regions_count,
                "percentage": round(completed_regions_percentage, 2)
            }
        },
        "crops_data": crops_by_family,
        "agents_by_region": agents_by_region,
        "farmer_assignment": farmer_assignment_by_region,
        "region_statuses": region_statuses,
        "map_data": map_data
    }
