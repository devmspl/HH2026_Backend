import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.core.security import get_password_hash
from app.models.user import (
    User, UserRole, AccountStatus, Customer, Camp, Region, District, Province, 
    RegionalCrop, CropFamily, Report, ReportStatus, AuditLog, NotificationLog,
    SystemRole, Survey, SurveyStatus, SurveyType, TargetRespondents, 
    AttachmentRequirement, NationalCrop, ChatGroup, ChatMessage, SystemConfiguration
)

def seed_everything():
    db = SessionLocal()
    try:
        print("--- 🚀 STARTING MASTER A-TO-Z SEEDING ---")
        
        # 1. Clean Slate (Optional - Uncomment if you want to wipe first)
        print("Wiping existing data for a fresh start...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables recreated.")

        password_hash = get_password_hash("password123")

        # 2. Seed System Roles
        print("Seeding System Roles...")
        roles_data = [
            ("Super Admin", '{"all": true}'),
            ("Executive", '{"view_reports": true, "view_dashboard": true}'),
            ("Agent", '{"create_report": true, "view_assigned_customers": true}')
        ]
        role_objs = []
        for name, perms in roles_data:
            role = SystemRole(name=name, permissions=perms)
            db.add(role)
            db.flush()
            role_objs.append(role)

        # 3. Seed Crop Families & National Crops
        print("Seeding Crop Data...")
        families = [
            ("Grains", "Maize, Wheat, Rice"),
            ("Tubers", "Cassava, Sweet Potatoes"),
            ("Legumes", "Beans, Soybeans"),
            ("Fruits", "Mango, Banana"),
            ("Vegetables", "Nutritious Greens")
        ]
        family_objs = []
        for f_name, label in families:
            fam = CropFamily(family_name=f_name, label=label)
            db.add(fam)
            db.flush()
            family_objs.append(fam)
            
            # Add a National Crop for each family
            db.add(NationalCrop(crop_name=f"{f_name} Standard", family_id=fam.id))

        # 4. Seed Location Hierarchy (Detailed)
        print("Seeding Location Hierarchy & Users...")
        provinces = ["Lusaka", "Copperbelt", "Central", "Southern", "North-Western"]
        
        # Create Super Admin & Executive
        admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="System Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_superuser=True,
            role_id=role_objs[0].id
        )
        db.add(admin)
        
        ceo = User(
            email="executive@example.com",
            hashed_password=password_hash,
            full_name="Chief Executive",
            role=UserRole.EXECUTIVE
        )
        db.add(ceo)
        db.flush()

        for p_name in provinces:
            province = Province(name=p_name)
            db.add(province)
            db.flush()

            # Provincial Manager
            p_mgr = User(
                email=f"provincial-{province.id}@example.com",
                hashed_password=password_hash,
                full_name=f"Manager {p_name}",
                role=UserRole.PROVINCIAL,
                province_id=province.id
            )
            db.add(p_mgr)

            for d_idx in range(1, 3):
                district = District(name=f"{p_name} District {d_idx}", province_id=province.id)
                db.add(district)
                db.flush()

                for r_idx in range(1, 3):
                    region = Region(
                        name=f"{district.name} Region {r_idx}", 
                        district_id=district.id, 
                        province_id=province.id,
                        is_approved=True
                    )
                    db.add(region)
                    db.flush()

                    # Regional Crops
                    for _ in range(2):
                        fam = random.choice(family_objs)
                        db.add(RegionalCrop(
                            region_id=region.id,
                            crop_name=f"{fam.family_name} Var-{random.randint(1,10)}",
                            family_id=fam.id
                        ))

                    for c_idx in range(1, 3):
                        camp = Camp(
                            name=f"{region.name} Camp {c_idx}",
                            region_id=region.id,
                            district_id=district.id,
                            province_id=province.id,
                            total_customers=random.randint(100, 200)
                        )
                        db.add(camp)
                        db.flush()

                        # Camp Manager
                        camp_mgr = User(
                            email=f"manager-{camp.id}@example.com",
                            hashed_password=password_hash,
                            full_name=f"Manager {camp.name}",
                            role=UserRole.CAMP,
                            province_id=province.id,
                            district_id=district.id,
                            region_id=region.id,
                            camp_id=camp.id
                        )
                        db.add(camp_mgr)
                        db.flush()

                        # Chat Group for Camp
                        group = ChatGroup(name=f"Group {camp.name}", manager_id=camp_mgr.id, region_id=region.id)
                        db.add(group)
                        db.flush()

                        # Agents & Reports
                        for a_idx in range(1, 3):
                            agent = User(
                                email=f"agent-{camp.id}-{a_idx}@example.com",
                                hashed_password=password_hash,
                                full_name=f"Agent {a_idx} {camp.name}",
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
                            
                            # Add to group
                            db.execute(text(f"INSERT INTO chat_group_members (user_id, group_id) VALUES ({agent.id}, {group.id})"))

                            # Reports
                            for rep_idx in range(2):
                                db.add(Report(
                                    agent_id=agent.id,
                                    camp_id=camp.id,
                                    region_id=region.id,
                                    province_id=province.id,
                                    district_id=district.id,
                                    title=f"Assessment {rep_idx+1}",
                                    status=ReportStatus.APPROVED,
                                    gps_lat=agent.last_lat,
                                    gps_lng=agent.last_lng,
                                    confirmation_no=f"CONF-{agent.id}-{rep_idx}-{random.randint(100,999)}"
                                ))

                        # Customers (Farmers)
                        for f_idx in range(10):
                            db.add(Customer(
                                full_name=f"Farmer {random.randint(1000, 9999)}",
                                membership_status="Registered",
                                province_id=province.id,
                                district_id=district.id,
                                region_id=region.id,
                                camp_id=camp.id,
                                phone=f"+26097{random.randint(1000000, 9999999)}"
                            ))

        # 5. Seed Surveys
        print("Seeding Surveys...")
        surveys = [
            ("2024 National Maize Yield", SurveyType.NATIONAL.value, SurveyStatus.ACTIVE.value),
            ("Regional Soil Assessment", SurveyType.REGIONAL.value, SurveyStatus.ACTIVE.value),
            ("Draft Survey 1", SurveyType.NATIONAL.value, SurveyStatus.DRAFT.value)
        ]
        for name, s_type, status in surveys:
            db.add(Survey(
                name=name, 
                form_type=s_type, 
                status=status,
                created_by=admin.id,
                description="Sample survey description for testing A-to-Z data."
            ))

        # 6. Seed System Config & Audit Logs
        print("Seeding Audit Logs & Config...")
        db.add(SystemConfiguration(key="sms_settings", value='{"enabled": true, "provider": "twilio"}'))
        
        db.add(AuditLog(
            user_id=admin.id,
            action="INITIAL_SEED",
            details="System initialized with A-to-Z master seed script."
        ))

        db.commit()
        print("\n--- ✅ SUCCESS: MASTER SEEDING COMPLETED ---")
        print("Logins:")
        print(f"Admin: admin@example.com / admin123")
        print(f"Executive: executive@example.com / password123")
        print(f"Agent Example: agent-{camp.id}-1@example.com / password123")

    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {e}")
    finally:
        db.close()

from sqlalchemy import text
if __name__ == "__main__":
    seed_everything()
