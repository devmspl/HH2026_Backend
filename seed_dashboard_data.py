"""
Unified Seed Script: Populates all necessary data for the dashboard.
Run: python seed_dashboard_data.py
"""
import json
import random
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.user import (
    User, UserRole, AccountStatus,
    CropFamily, NationalCrop, Province, District, Region, Camp, RegionalCrop,
    Survey, SurveyType, SurveyStatus, TargetRespondents,
    Report, ReportStatus,
)
from app.core.security import get_password_hash
from app.core.config import settings

SEED_PASSWORD = "agent123"

# Source of truth for crop names and families
FAMILY_CROP_NAMES = {
    "Cereals": ["Maize", "Rice", "Wheat", "Barley"],
    "Legumes": ["Beans", "Peas", "Groundnut"],
    "Tubers": ["Potato", "Cassava", "Sweet Potato"],
    "Vegetables": ["Tomato", "Onion", "Cabbage"],
    "Fruits": ["Mango", "Banana", "Orange"],
    "Other": ["Cotton", "Sugarcane"],
}

def ensure_superuser(db):
    u = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    if not u:
        u = User(
            email=settings.FIRST_SUPERUSER,
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD or "admin123"),
            full_name="System Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_superuser=True,
            account_status=AccountStatus.ACTIVE,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u.id

def seed_crop_families(db):
    if db.query(CropFamily).count() > 0:
        return list(db.query(CropFamily).all())
    
    families = []
    for name in FAMILY_CROP_NAMES.keys():
        f = CropFamily(family_name=name)
        db.add(f)
        families.append(f)
    db.commit()
    for f in families: db.refresh(f)
    print("  Created crop families")
    return families

def seed_national_crops(db, families):
    if db.query(NationalCrop).count() > 0:
        return
    for fam in families:
        crop_names = FAMILY_CROP_NAMES.get(fam.family_name, [])
        for i, name in enumerate(crop_names):
            c_id = f"NC-{fam.family_name[:1].upper()}{i+1:03d}"
            c = NationalCrop(crop_name=name, family_id=fam.id, crop_id=c_id)
            db.add(c)
    db.commit()
    print("  Created national crops")

def seed_regional_crops(db, regions, families):
    if db.query(RegionalCrop).count() > 0:
        return
    for r in regions[:6]:
        for fam in families:
            crop_names = FAMILY_CROP_NAMES.get(fam.family_name, [])
            for i, name in enumerate(crop_names[:2]): # 2 per family per region
                local_name = f"Local {name}"
                rc_id = f"RC-{r.id:02d}-{fam.id}{i+1:03d}"
                rc = RegionalCrop(region_id=r.id, crop_name=local_name, family_id=fam.id, rcrop_id=rc_id)
                db.add(rc)
    db.commit()
    print("  Created regional crops")

def seed_locations(db):
    if db.query(Province).count() > 0:
        return list(db.query(Province).all()), list(db.query(District).all()), list(db.query(Region).all()), list(db.query(Camp).all())
    
    # Simple setup
    p1 = Province(name="Punjab")
    db.add(p1)
    db.commit()
    db.refresh(p1)
    
    d1 = District(name="Ludhiana", province_id=p1.id)
    db.add(d1)
    db.commit()
    db.refresh(d1)
    
    r1 = Region(name="North Central", district_id=d1.id, province_id=p1.id)
    db.add(r1)
    db.commit()
    db.refresh(r1)
    
    c1 = Camp(name="Main Camp", region_id=r1.id, district_id=d1.id, province_id=p1.id)
    db.add(c1)
    db.commit()
    db.refresh(c1)
    
    print("  Created locations")
    return [p1], [d1], [r1], [c1]

def seed_surveys(db, superuser_id):
    surveys = db.query(Survey).all()
    if surveys: return surveys
    
    s1 = Survey(name="National Survey", form_type=SurveyType.NATIONAL.value, status=SurveyStatus.ACTIVE.value, created_by=superuser_id)
    s2 = Survey(name="Regional Tally", form_type=SurveyType.REGIONAL.value, status=SurveyStatus.ACTIVE.value, created_by=superuser_id)
    db.add(s1)
    db.add(s2)
    db.commit()
    db.refresh(s1)
    db.refresh(s2)
    print("  Created surveys")
    return [s1, s2]

def make_survey_data(families, is_regional=False):
    crops = []
    for fam in families:
        name_list = FAMILY_CROP_NAMES.get(fam.family_name, [])
        for i, cn in enumerate(name_list[:2]):
            final_name = f"Local {cn}" if is_regional else cn
            crops.append({
                "crop_name": final_name,
                "family_name": fam.family_name,
                "yield_tonnes": round(random.uniform(5, 50), 2),
                "crop_id": f"NC-{fam.family_name[:1].upper()}{i+1:03d}" if not is_regional else None,
                "rcrop_id": None if is_regional else None
            })
    return {
        "total_farmers": 100,
        "participating_farmers": 85,
        "spoiled_responses": 5,
        "crops": crops
    }

def seed_reports(db, agents, surveys, families):
    if db.query(Report).count() > 10: return
    
    for s in surveys:
        is_reg = s.form_type == SurveyType.REGIONAL.value
        for a in agents[:3]:
            data = make_survey_data(families, is_regional=is_reg)
            r = Report(
                agent_id=a.id,
                survey_id=s.id,
                title=f"Initial {s.name}",
                status=ReportStatus.APPROVED,
                survey_data=json.dumps(data),
                gps_lat=28.6,
                gps_lng=77.2,
                province_id=a.province_id,
                district_id=a.district_id,
                region_id=a.region_id,
                camp_id=a.camp_id,
                confirmation_no=f"SEED-{random.randint(1000,9999)}"
            )
            db.add(r)
    db.commit()
    print("  Created reports")

def main():
    db = SessionLocal()
    try:
        # Clear existing data using truncate cascade for PostgreSQL
        print("Cleaning database...")
        db.execute(text("TRUNCATE TABLE reports, report_edit_history, regional_crops, national_crops, surveys, crop_families, users CASCADE"))
        db.commit()
        
        sid = ensure_superuser(db)
        fams = seed_crop_families(db)
        seed_national_crops(db, fams)
        provinces, districts, regions, camps = seed_locations(db)
        surveys = seed_surveys(db, sid)
        
        # Agents
        agents = db.query(User).filter(User.role == UserRole.AGENT).all()
        if not agents:
            a = User(email="agent@example.com", hashed_password=get_password_hash("agent123"), full_name="Agent Alpha", role=UserRole.AGENT, is_active=True, account_status=AccountStatus.ACTIVE, province_id=provinces[0].id, district_id=districts[0].id, region_id=regions[0].id, camp_id=camps[0].id)
            db.add(a)
            db.commit()
            db.refresh(a)
            agents = [a]
        
        seed_regional_crops(db, regions, fams)
        seed_reports(db, agents, surveys, fams)
        print("Seeding complete!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
