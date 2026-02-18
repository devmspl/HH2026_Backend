"""
Seed script: Fill Crop Domination Map, Survey Results, and Approval Management.
Run from backend root: python seed_dashboard_data.py

Creates: Crop families & national crops, Provinces/Districts/Regions/Camps,
         National + Regional surveys (active), Agents with location,
         Reports with survey_data + province_id/district_id/region_id/camp_id,
         and a few PENDING users for Approval Management.
"""
import json
import random
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.user import (
    User, UserRole, AccountStatus,
    CropFamily, NationalCrop, Province, District, Region, Camp, RegionalCrop,
    Survey, SurveyType, SurveyStatus, TargetRespondents,
    Report, ReportStatus,
)
from app.core.security import get_password_hash

# Default password for seeded users
SEED_PASSWORD = "agent123"


def ensure_superuser(db):
    """Ensure superuser exists (id=1) for created_by."""
    u = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    if not u:
        from app.core.config import settings
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
        print("  Created superuser")
    return u.id


def seed_crop_families(db):
    """Crop families for legend and reports."""
    if db.query(CropFamily).count() > 0:
        print("  Crop families already exist, skipping.")
        return list(db.query(CropFamily).order_by(CropFamily.id).all())
    names = [
        ("Cereals", "Cereals"),
        ("Legumes", "Legumes"),
        ("Tubers", "Tubers"),
        ("Vegetables", "Vegetables"),
        ("Fruits", "Fruits"),
        ("Other", "Other"),
    ]
    families = []
    for name, label in names:
        f = CropFamily(family_name=name, label=label)
        db.add(f)
        families.append(f)
    db.commit()
    for f in families:
        db.refresh(f)
    print(f"  Created {len(families)} crop families")
    return list(db.query(CropFamily).order_by(CropFamily.id).all())


def seed_national_crops(db, families):
    """National crops linked to families."""
    if db.query(NationalCrop).count() > 0:
        print("  National crops already exist, skipping.")
        return
    # family index: 0 Cereals, 1 Legumes, 2 Tubers, 3 Vegetables, 4 Fruits, 5 Other
    crops_by_family = [
        ("Maize", "Rice", "Wheat", "Barley"),
        ("Beans", "Peas", "Groundnut", "Soybean"),
        ("Potato", "Cassava", "Sweet Potato"),
        ("Tomato", "Onion", "Cabbage", "Spinach"),
        ("Mango", "Banana", "Orange"),
        ("Cotton", "Sugarcane"),
    ]
    for i, family in enumerate(families):
        if i >= len(crops_by_family):
            break
        for crop_name in crops_by_family[i]:
            c = NationalCrop(crop_name=crop_name, family_id=family.id)
            db.add(c)
    db.commit()
    print("  Created national crops")


def seed_locations(db, families):
    """Provinces -> Districts -> Regions -> Camps. Returns (provinces, districts, regions, camps)."""
    if db.query(Province).count() > 0:
        print("  Locations already exist, skipping.")
        provinces = list(db.query(Province).order_by(Province.id).all())
        districts = list(db.query(District).order_by(District.id).all())
        regions = list(db.query(Region).order_by(Region.id).all())
        camps = list(db.query(Camp).order_by(Camp.id).all())
        return provinces, districts, regions, camps

    provinces = []
    for name in ["North", "South", "Central"]:
        p = Province(name=name, total_customers=0, main_crop_family_id=families[random.randint(0, len(families)-1)].id if families else None)
        db.add(p)
        provinces.append(p)
    db.commit()
    for p in provinces:
        db.refresh(p)

    districts = []
    for p in provinces:
        for d_name in [f"{p.name} D1", f"{p.name} D2"]:
            d = District(name=d_name, province_id=p.id, total_customers=0)
            db.add(d)
            districts.append(d)
    db.commit()
    for d in districts:
        db.refresh(d)

    regions = []
    for d in districts:
        for r_name in [f"{d.name} R1", f"{d.name} R2"]:
            p_id = d.province_id
            r = Region(name=r_name, district_id=d.id, province_id=p_id, total_customers=0)
            db.add(r)
            regions.append(r)
    db.commit()
    for r in regions:
        db.refresh(r)

    camps = []
    for r in regions:
        c = Camp(name=f"{r.name} Camp", region_id=r.id, province_id=r.province_id, district_id=r.district_id, total_customers=0)
        db.add(c)
        camps.append(c)
    db.commit()
    for c in camps:
        db.refresh(c)

    print(f"  Created {len(provinces)} provinces, {len(districts)} districts, {len(regions)} regions, {len(camps)} camps")
    return provinces, districts, regions, camps


def seed_surveys(db, superuser_id):
    """National and Regional surveys (active)."""
    existing = db.query(Survey).filter(Survey.form_type == SurveyType.NATIONAL.value).first()
    if existing:
        print("  Surveys already exist, skipping.")
        return list(db.query(Survey).all())

    national = Survey(
        name="National Crops Survey 2025",
        form_type=SurveyType.NATIONAL.value,
        description="National crop yield and participation survey",
        target_respondents=TargetRespondents.ALL.value,
        status=SurveyStatus.ACTIVE.value,
        created_by=superuser_id,
    )
    db.add(national)
    regional = Survey(
        name="Regional Crops Survey 2025",
        form_type=SurveyType.REGIONAL.value,
        description="Regional crop tally",
        target_respondents=TargetRespondents.ALL.value,
        status=SurveyStatus.ACTIVE.value,
        created_by=superuser_id,
    )
    db.add(regional)
    db.commit()
    db.refresh(national)
    db.refresh(regional)
    print("  Created National and Regional surveys")
    return [national, regional]


def seed_agents_and_pending(db, regions, camps, superuser_id):
    """Agents with location; a few PENDING users for approval."""
    if db.query(User).filter(User.role == UserRole.AGENT).count() >= 6:
        print("  Agents already exist, skipping.")
        agents = list(db.query(User).filter(User.role == UserRole.AGENT).all())
    else:
        agents = []
        names = ["Amit Kumar", "Priya Singh", "Rajesh Verma", "Sita Devi", "Vijay Patel", "Anita Sharma"]
        for i, name in enumerate(names):
            if db.query(User).filter(User.email == f"agent{i+1}@seed.local").first():
                continue
            r = regions[i % len(regions)]
            c = camps[i % len(camps)]
            u = User(
                email=f"agent{i+1}@seed.local",
                hashed_password=get_password_hash(SEED_PASSWORD),
                full_name=name,
                role=UserRole.AGENT,
                is_active=True,
                account_status=AccountStatus.ACTIVE,
                province_id=r.province_id,
                district_id=r.district_id,
                region_id=r.id,
                camp_id=c.id,
                phone=f"+9198765{40000 + i}",
            )
            db.add(u)
            agents.append(u)
        db.commit()
        for u in agents:
            db.refresh(u)
        agents = list(db.query(User).filter(User.role == UserRole.AGENT).all())
        print(f"  Created/using {len(agents)} agents with location")

    # 2 PENDING users for Approval Management
    for i in range(1, 3):
        email = f"pending{i}@seed.local"
        if db.query(User).filter(User.email == email).first():
            continue
        u = User(
            email=email,
            hashed_password=get_password_hash(SEED_PASSWORD),
            full_name=f"Pending User {i}",
            role=UserRole.AGENT,
            is_active=False,
            account_status=AccountStatus.PENDING,
        )
        db.add(u)
    db.commit()
    print("  Added 2 PENDING users for Approval Management")
    return agents


def make_survey_data(families, family_names_list):
    """Build survey_data JSON for a report (national format)."""
    total = random.randint(180, 320)
    participating = random.randint(150, total - 10)
    spoiled = random.randint(0, 8)
    crops = []
    for fam in families:
        name = fam.family_name
        # 1–3 crops per family
        crop_names = family_names_list.get(name, [name])
        for cn in crop_names[: random.randint(1, 3)]:
            crops.append({
                "crop_name": cn,
                "family_name": name,
                "yield_tonnes": round(random.uniform(2, 25), 2),
            })
    return {
        "total_farmers": total,
        "participating_farmers": participating,
        "spoiled_responses": spoiled,
        "crops": crops,
    }


def seed_reports(db, agents, national_survey, regional_survey, families, provinces=None, regions=None):
    """Reports with survey_data and location (so Crop Map & Survey Results show data)."""
    family_crop_names = {
        "Cereals": ["Maize", "Rice", "Wheat", "Barley"],
        "Legumes": ["Beans", "Peas", "Groundnut"],
        "Tubers": ["Potato", "Cassava", "Sweet Potato"],
        "Vegetables": ["Tomato", "Onion", "Cabbage"],
        "Fruits": ["Mango", "Banana", "Orange"],
        "Other": ["Cotton", "Sugarcane"],
    }
    if db.query(Report).filter(Report.survey_id == national_survey.id).count() >= 5:
        print("  Report survey data already seeded, skipping.")
        # Ensure every Central region (D1 R1, D1 R2, D2 R1, D2 R2) has at least one report for By Region map
        if provinces and regions and agents:
            central = next((p for p in provinces if p.name == "Central"), None)
            if central:
                central_regions = [r for r in regions if r.province_id == central.id]
                for central_region in central_regions:
                    if db.query(Report).filter(Report.region_id == central_region.id).count() > 0:
                        continue
                    survey_data = make_survey_data(families, family_crop_names)
                    r = Report(
                        agent_id=agents[0].id,
                        survey_id=national_survey.id,
                        title=f"Central - {central_region.name}",
                        description="Seed report for Crop Map",
                        status=ReportStatus.APPROVED,
                        gps_lat=28.6, gps_lng=77.2,
                        confirmation_no=f"CONF-{random.randint(100000, 999999)}",
                        survey_data=json.dumps(survey_data),
                        province_id=central.id,
                        district_id=central_region.district_id,
                        region_id=central_region.id,
                        camp_id=None,
                    )
                    db.add(r)
                if central_regions:
                    db.commit()
                    print("  Added Central region reports for Crop Map (incl. Central D1 R2).")
        return

    for agent in agents[: min(6, len(agents))]:
        if not getattr(agent, "province_id", None):
            continue
        for _ in range(random.randint(1, 2)):
            survey_data = make_survey_data(families, family_crop_names)
            r = Report(
                agent_id=agent.id,
                survey_id=national_survey.id,
                title=f"National Survey - {agent.full_name}",
                description="Seed report",
                status=random.choice([ReportStatus.PENDING, ReportStatus.APPROVED]),
                gps_lat=round(28.5 + random.uniform(-0.5, 0.5), 6),
                gps_lng=round(77.2 + random.uniform(-0.5, 0.5), 6),
                confirmation_no=f"CONF-{random.randint(100000, 999999)}",
                survey_data=json.dumps(survey_data),
                province_id=agent.province_id,
                district_id=agent.district_id,
                region_id=agent.region_id,
                camp_id=agent.camp_id,
            )
            db.add(r)
    # Ensure Central has reports (agents might only be North/South)
    if provinces and regions and agents:
        central = next((p for p in provinces if p.name == "Central"), None)
        if central:
            central_regions = [r for r in regions if r.province_id == central.id]
            for central_region in central_regions[:2]:
                survey_data = make_survey_data(families, family_crop_names)
                r = Report(
                    agent_id=agents[0].id,
                    survey_id=national_survey.id,
                    title=f"Central - {central_region.name}",
                    description="Seed report",
                    status=ReportStatus.APPROVED,
                    gps_lat=28.6, gps_lng=77.2,
                    confirmation_no=f"CONF-{random.randint(100000, 999999)}",
                    survey_data=json.dumps(survey_data),
                    province_id=central.id,
                    district_id=central_region.district_id,
                    region_id=central_region.id,
                    camp_id=None,
                )
                db.add(r)
    db.commit()
    print("  Created reports with survey_data and location (Crop Map + Survey Results will show data)")
    return


def seed_regional_crops(db, regions, families):
    """Regional crops per region for regional survey."""
    if db.query(RegionalCrop).count() > 0:
        return
    names = ["Local Maize", "Upland Rice", "Garden Beans", "Valley Potato", "Hill Tomato"]
    for r in regions[: min(6, len(regions))]:
        for i, name in enumerate(names[:3]):
            fam = families[i % len(families)]
            rc = RegionalCrop(region_id=r.id, crop_name=name, family_id=fam.id)
            db.add(rc)
    db.commit()
    print("  Created regional crops")


def main():
    print("Seeding dashboard data (locations, crops, surveys, agents, reports, pending users)...")
    db = SessionLocal()
    try:
        superuser_id = ensure_superuser(db)
        families = seed_crop_families(db)
        seed_national_crops(db, families)
        provinces, districts, regions, camps = seed_locations(db, families)
        if not regions or not camps:
            print("ERROR: No regions/camps. Run seed_locations first or check DB.")
            return
        surveys = seed_surveys(db, superuser_id)
        national_survey = next((s for s in surveys if s.form_type == SurveyType.NATIONAL.value), None)
        regional_survey = next((s for s in surveys if s.form_type == SurveyType.REGIONAL.value), None)
        if not national_survey:
            print("ERROR: National survey not found.")
            return
        agents = seed_agents_and_pending(db, regions, camps, superuser_id)
        seed_reports(db, agents, national_survey, regional_survey, families, provinces, regions)
        seed_regional_crops(db, regions, families)
        print("\nDone. Refresh: Crop Domination Map, Survey Results, Approval Management.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
