import random
import enum
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import (
    User, UserRole, AccountStatus, Customer, Camp, Region, District, Province, 
    RegionalCrop, CropFamily, Report, ReportStatus, AuditLog, NotificationLog
)
from app.core.security import get_password_hash
from datetime import datetime, timedelta

def seed_production_data():
    db = SessionLocal()
    try:
        print("--- Starting Comprehensive Data Seeding ---")

        # 1. Clear some existing data to avoid conflicts if needed (optional)
        # Note: In production seeding, we usually skip or update.
        
        password_hash = get_password_hash("password123")

        # 2. Ensure SuperAdmin
        admin = db.query(User).filter(User.email == "admin@example.com").first()
        if not admin:
            admin = User(
                email="admin@example.com",
                hashed_password=password_hash,
                full_name="System Administrator",
                role=UserRole.SUPER_ADMIN,
                is_superuser=True
            )
            db.add(admin)
            db.flush()

        # 3. Create Hierarchical Structure
        provinces = ["Lusaka", "Copperbelt", "Central", "Southern", "North-Western"]
        for p_name in provinces:
            province = db.query(Province).filter(Province.name == p_name).first()
            if not province:
                province = Province(name=p_name)
                db.add(province)
                db.flush()

            # Create Provincial User
            prov_email = f"provincial-{province.id}@example.com"
            if not db.query(User).filter(User.email == prov_email).first():
                db.add(User(
                    email=prov_email,
                    hashed_password=password_hash,
                    full_name=f"Provincial Manager {p_name}",
                    role=UserRole.PROVINCIAL,
                    province_id=province.id
                ))

            # Disticts for each province
            for d_idx in range(2):
                d_name = f"{p_name} District {d_idx+1}"
                district = db.query(District).filter(District.name == d_name).first()
                if not district:
                    district = District(name=d_name, province_id=province.id)
                    db.add(district)
                    db.flush()
                
                # Create District User
                dist_email = f"district-{district.id}@example.com"
                if not db.query(User).filter(User.email == dist_email).first():
                    db.add(User(
                        email=dist_email,
                        hashed_password=password_hash,
                        full_name=f"District Head {d_name}",
                        role=UserRole.DISTRICT,
                        province_id=province.id,
                        district_id=district.id
                    ))

                # Regions for each district
                for r_idx in range(2):
                    r_name = f"{d_name} Region {r_idx+1}"
                    region = db.query(Region).filter(Region.name == r_name).first()
                    if not region:
                        region = Region(
                            name=r_name, 
                            district_id=district.id, 
                            province_id=province.id,
                            is_approved=random.choice([True, False, False]) # Some approved
                        )
                        db.add(region)
                        db.flush()
                    
                    # Create Region User
                    reg_email = f"region-{region.id}@example.com"
                    if not db.query(User).filter(User.email == reg_email).first():
                        db.add(User(
                            email=reg_email,
                            hashed_password=password_hash,
                            full_name=f"Regional Director {r_name}",
                            role=UserRole.REGION,
                            province_id=province.id,
                            district_id=district.id,
                            region_id=region.id
                        ))

                    # Camps for each region
                    for c_idx in range(2):
                        c_name = f"{r_name} Camp {c_idx+1}"
                        camp = db.query(Camp).filter(Camp.name == c_name).first()
                        if not camp:
                            camp = Camp(
                                name=c_name,
                                region_id=region.id,
                                district_id=district.id,
                                province_id=province.id,
                                total_customers=random.randint(200, 500)
                            )
                            db.add(camp)
                            db.flush()
                        
                        # Create Camp Manager (CAMP role)
                        camp_email = f"manager-{camp.id}@example.com"
                        camp_manager = db.query(User).filter(User.email == camp_email).first()
                        if not camp_manager:
                            camp_manager = User(
                                email=camp_email,
                                hashed_password=password_hash,
                                full_name=f"Camp Manager {c_name}",
                                role=UserRole.CAMP,
                                province_id=province.id,
                                district_id=district.id,
                                region_id=region.id,
                                camp_id=camp.id
                            )
                            db.add(camp_manager)
                            db.flush()

                        # Create Agents for this camp
                        for a_idx in range(3):
                            agent_email = f"agent-{camp.id}-{a_idx+1}@example.com"
                            agent = db.query(User).filter(User.email == agent_email).first()
                            if not agent:
                                agent = User(
                                    email=agent_email,
                                    hashed_password=password_hash,
                                    full_name=f"Field Agent {a_idx+1} ({c_name})",
                                    role=UserRole.AGENT,
                                    province_id=province.id,
                                    district_id=district.id,
                                    region_id=region.id,
                                    camp_id=camp.id,
                                    last_lat=-15.4 + (random.random() * 2),
                                    last_lng=28.3 + (random.random() * 2),
                                    is_active=random.choice([True, True, False])
                                )
                                db.add(agent)
                                db.flush()

                            # Create Reports for this Agent
                            if random.random() > 0.3:
                                for rep_idx in range(random.randint(1, 3)):
                                    status = random.choice([ReportStatus.PENDING, ReportStatus.APPROVED, ReportStatus.REJECTED])
                                    report = Report(
                                        agent_id=agent.id,
                                        camp_id=camp.id,
                                        region_id=region.id,
                                        province_id=province.id,
                                        district_id=district.id,
                                        title=f"Weekly Crop Assessment - {datetime.now().date()}",
                                        description="Assessment of maize growth and pest control effectiveness in the northern sector.",
                                        status=status,
                                        gps_lat=agent.last_lat + (random.random() * 0.01),
                                        gps_lng=agent.last_lng + (random.random() * 0.01),
                                        confirmation_no=f"REP-{agent.id}-{datetime.now().timestamp()}-{rep_idx}"
                                    )
                                    db.add(report)

                        # Create Farmers (Customers) for this camp
                        for f_idx in range(20):
                            m_status = random.choice(["Affiliated", "Registered", "Non-Member", "Pending"])
                            customer = Customer(
                                full_name=f"Farmer {random.randint(10000, 99999)}",
                                membership_status=m_status,
                                province_id=province.id,
                                district_id=district.id,
                                region_id=region.id,
                                camp_id=camp.id,
                                assigned_camp_user_id=camp_manager.id if random.random() > 0.4 else None,
                                household=f"HH-{random.randint(100, 999)}",
                                phone=f"+26097{random.randint(1000000, 9999999)}"
                            )
                            db.add(customer)

        # 4. Create Crop Data
        families = ["Grains", "Tubers", "Legumes", "Fruits", "Vegetables"]
        family_objs = []
        for f_name in families:
            fam = db.query(CropFamily).filter(CropFamily.family_name == f_name).first()
            if not fam:
                fam = CropFamily(family_name=f_name, label=f"Sustainable {f_name} Production")
                db.add(fam)
                db.flush()
            family_objs.append(fam)

        # Regional Crops for every region
        all_regions = db.query(Region).all()
        for reg in all_regions:
            for _ in range(3):
                fam = random.choice(family_objs)
                crop_name = f"{fam.family_name} Type {random.randint(1, 10)}"
                if not db.query(RegionalCrop).filter(RegionalCrop.region_id == reg.id, RegionalCrop.crop_name == crop_name).first():
                    db.add(RegionalCrop(
                        region_id=reg.id,
                        crop_name=crop_name,
                        family_id=fam.id
                    ))

        # 5. Create Audit Logs
        users = db.query(User).limit(10).all()
        actions = ["LOGIN", "VIEW_DASHBOARD", "CREATE_REPORT", "ASSIGN_FARMER", "UPDATE_PROFILE"]
        for _ in range(50):
            u = random.choice(users)
            db.add(AuditLog(
                user_id=u.id,
                action=random.choice(actions),
                details=f"User {u.full_name} performed system action at {datetime.now()}",
                timestamp=datetime.now() - timedelta(minutes=random.randint(0, 10000))
            ))

        # 6. Create Notifications
        for _ in range(30):
            u = random.choice(users)
            db.add(NotificationLog(
                recipient_id=u.id,
                type="sms",
                title="System Alert",
                message="Your weekly summary is now available in the portal.",
                status="sent",
                is_read=random.choice([True, False])
            ))

        # 7. Create Executive User
        exec_user = db.query(User).filter(User.email == "executive@example.com").first()
        if not exec_user:
            db.add(User(
                email="executive@example.com",
                hashed_password=password_hash,
                full_name="Chief Executive Officer",
                role=UserRole.EXECUTIVE
            ))

        db.commit()
        print("--- Final Production Seeding Completed Successfully ---")

    except Exception as e:
        db.rollback()
        print(f"FAILED to seed data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_production_data()
