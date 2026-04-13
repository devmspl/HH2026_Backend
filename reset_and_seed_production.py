import random
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import (
    User, UserRole, AccountStatus, Customer, Camp, Region, District, Province, 
    RegionalCrop, CropFamily, Report, ReportStatus, AuditLog, NotificationLog
)
from app.core.security import get_password_hash
from datetime import datetime, timedelta

def reset_and_seed():
    db = SessionLocal()
    try:
        print("--- CRITICAL: Starting Full Database Reset ---")
        
        # 1. Drop all tables and recreate them for a perfect 'Clean Slate'
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("✅ Tables dropped and recreated successfully.")

        print("--- Starting Fresh Data Seeding ---")
        password_hash = get_password_hash("password123")

        # 2. Create Global Admin
        admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="System Administrator",
            role=UserRole.SUPER_ADMIN,
            is_superuser=True
        )
        db.add(admin)
        db.flush()

        # 3. Create Global Executive
        executive = User(
            email="executive@example.com",
            hashed_password=password_hash,
            full_name="Executive Director",
            role=UserRole.EXECUTIVE
        )
        db.add(executive)
        db.flush()

        # 4. Create Crop Families
        families = [
            ("Grains", "Cereal crops like Maize, Wheat, Rice"),
            ("Tubers", "Root crops like Cassava, Sweet Potatoes"),
            ("Legumes", "Protein-rich Beans, Soybeans"),
            ("Fruits", "Vibrant fruits like Mango, Banana"),
            ("Vegetables", "Nutritious greens"),
        ]
        family_objs = []
        for name, label in families:
            fam = CropFamily(family_name=name, label=label)
            db.add(fam)
            db.flush()
            family_objs.append(fam)

        # 5. Build Hierarchy (Prov -> Dist -> Reg -> Camp)
        provinces_list = ["Lusaka", "Copperbelt", "Central", "Southern"]
        for p_name in provinces_list:
            province = Province(name=p_name)
            db.add(province)
            db.flush()

            # Provincial Manager
            db.add(User(
                email=f"provincial-{province.name.lower()}@example.com",
                hashed_password=password_hash,
                full_name=f"Manager of {p_name}",
                role=UserRole.PROVINCIAL,
                province_id=province.id
            ))

            for d_idx in range(1, 3):
                district = District(name=f"{p_name} District {d_idx}", province_id=province.id)
                db.add(district)
                db.flush()

                # District Manager
                db.add(User(
                    email=f"district-{district.id}@example.com",
                    hashed_password=password_hash,
                    full_name=f"Head of {district.name}",
                    role=UserRole.DISTRICT,
                    province_id=province.id,
                    district_id=district.id
                ))

                for r_idx in range(1, 3):
                    region = Region(
                        name=f"{district.name} Region {r_idx}", 
                        district_id=district.id, 
                        province_id=province.id,
                        is_approved=random.choice([True, False, False])
                    )
                    db.add(region)
                    db.flush()

                    # Region Manager
                    db.add(User(
                        email=f"region-{region.id}@example.com",
                        hashed_password=password_hash,
                        full_name=f"Director of {region.name}",
                        role=UserRole.REGION,
                        province_id=province.id,
                        district_id=district.id,
                        region_id=region.id
                    ))

                    # Regional Crops
                    for _ in range(3):
                        fam = random.choice(family_objs)
                        db.add(RegionalCrop(
                            region_id=region.id,
                            crop_name=f"{fam.family_name} Type {random.randint(1, 5)}",
                            family_id=fam.id
                        ))

                    for c_idx in range(1, 3):
                        camp = Camp(
                            name=f"{region.name} Camp {c_idx}",
                            region_id=region.id,
                            district_id=district.id,
                            province_id=province.id,
                            total_customers=random.randint(200, 400)
                        )
                        db.add(camp)
                        db.flush()

                        # Camp Manager
                        camp_mgr = User(
                            email=f"camp-{camp.id}@example.com",
                            hashed_password=password_hash,
                            full_name=f"Officer in Charge ({camp.name})",
                            role=UserRole.CAMP,
                            province_id=province.id,
                            district_id=district.id,
                            region_id=region.id,
                            camp_id=camp.id
                        )
                        db.add(camp_mgr)
                        db.flush()

                        # Agents
                        for a_idx in range(1, 4):
                            agent = User(
                                email=f"agent-{camp.id}-{a_idx}@example.com",
                                hashed_password=password_hash,
                                full_name=f"Agent {a_idx} ({camp.name})",
                                role=UserRole.AGENT,
                                province_id=province.id,
                                district_id=district.id,
                                region_id=region.id,
                                camp_id=camp.id,
                                last_lat=-15.4 + (random.random() * 2),
                                last_lng=28.3 + (random.random() * 2),
                                is_active=True
                            )
                            db.add(agent)
                            db.flush()

                            # Some Reports for this Agent
                            for rep_idx in range(random.randint(2, 5)):
                                status = random.choice([ReportStatus.PENDING, ReportStatus.APPROVED, ReportStatus.REJECTED])
                                db.add(Report(
                                    agent_id=agent.id,
                                    camp_id=camp.id,
                                    region_id=region.id,
                                    province_id=province.id,
                                    district_id=district.id,
                                    title=f"Field Progress Report {rep_idx+1}",
                                    description="Regular crop health monitoring and farmer engagement summary.",
                                    status=status,
                                    gps_lat=agent.last_lat + (random.random() * 0.01),
                                    gps_lng=agent.last_lng + (random.random() * 0.01),
                                    confirmation_no=f"CONF-{agent.id}-{datetime.now().timestamp()}-{rep_idx}"
                                ))

                        # Farmers (Customers)
                        for f_idx in range(15):
                            m_status = random.choice(["Affiliated", "Registered", "Non-Member", "Pending"])
                            db.add(Customer(
                                full_name=f"Farmer {random.randint(1000, 9999)}",
                                membership_status=m_status,
                                province_id=province.id,
                                district_id=district.id,
                                region_id=region.id,
                                camp_id=camp.id,
                                assigned_camp_user_id=camp_mgr.id if random.random() > 0.5 else None,
                                phone=f"+26097{random.randint(1000000, 9999999)}"
                            ))

        db.commit()
        print("--- SUCCESS: Database Wipe & Re-Seed Completed ---")
        print("Global Executive login: executive@example.com / password123")
        print("Global Admin login: admin@example.com / password123")

    except Exception as e:
        db.rollback()
        print(f"❌ CRITICAL ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed()
