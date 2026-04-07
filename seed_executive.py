import random
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import (
    User, UserRole, AccountStatus, Customer, Camp, Region, District, Province, 
    RegionalCrop, CropFamily, Report, ReportStatus, AuditLog
)
from app.core.security import get_password_hash

def seed_data():
    db = SessionLocal()
    try:
        print("--- Starting Executive Data Seeding ---")

        # 1. Create Crop Families
        families = [
            ("Grains", "Cereal crops like Maize, Wheat, Rice"),
            ("Fruits", "Vibrant fruits like Mango, Banana, Citrus"),
            ("Vegetables", "Nutritious greens and vegetables"),
            ("Legumes", "Protein-rich Beans, Soybeans, Groundnuts"),
            ("Tubers", "Root crops like Cassava, Sweet Potatoes"),
        ]
        family_objs = []
        for name, label in families:
            fam = db.query(CropFamily).filter(CropFamily.family_name == name).first()
            if not fam:
                fam = CropFamily(family_name=name, label=label)
                db.add(fam)
                db.flush()
            family_objs.append(fam)
        
        # 2. Create Provinces, Districts, Regions
        prov_names = ["Lusaka", "Copperbelt", "Central", "Southern"]
        dist_names = ["Capital City", "Highlands", "Industrial Zone", "Lakeview"]
        reg_names = ["North Region", "South Region", "East Sector", "West Sector"]
        
        password_hash = get_password_hash("password123")

        for p_name in prov_names:
            province = db.query(Province).filter(Province.name == p_name).first()
            if not province:
                province = Province(name=p_name)
                db.add(province)
                db.flush()
            
            for d_name in dist_names:
                district = db.query(District).filter(District.name == f"{p_name}-{d_name}").first()
                if not district:
                    district = District(name=f"{p_name}-{d_name}", province_id=province.id)
                    db.add(district)
                    db.flush()
                
                for r_name in reg_names:
                    region = db.query(Region).filter(Region.name == f"{district.name}-{r_name}").first()
                    if not region:
                        # Randomly approve some regions to show GREEN status
                        is_green = random.random() > 0.7 
                        region = Region(
                            name=f"{district.name}-{r_name}", 
                            district_id=district.id, 
                            province_id=province.id,
                            is_approved=is_green
                        )
                        db.add(region)
                        db.flush()

                    # 3. Create Crops for this Region
                    for _ in range(3):
                        fam = random.choice(family_objs)
                        crop = RegionalCrop(
                            region_id=region.id,
                            crop_name=f"{fam.family_name} Variety {random.randint(1, 100)}",
                            family_id=fam.id
                        )
                        db.add(crop)

                    # 4. Create Camps
                    for c_idx in range(2):
                        camp_name = f"{region.name}-Camp-{c_idx+1}"
                        camp = db.query(Camp).filter(Camp.name == camp_name).first()
                        if not camp:
                            camp = Camp(
                                name=camp_name,
                                region_id=region.id,
                                district_id=district.id,
                                province_id=province.id,
                                total_customers=random.randint(50, 200)
                            )
                            db.add(camp)
                            db.flush()
                        
                        # 5. Create Camp Users & Agents
                        camp_user_email = f"user-{camp.id}@example.com"
                        c_user = db.query(User).filter(User.email == camp_user_email).first()
                        if not c_user:
                            c_user = User(
                                email=camp_user_email,
                                hashed_password=password_hash,
                                full_name=f"Manager for {camp.name}",
                                role=UserRole.CAMP,
                                camp_id=camp.id,
                                region_id=region.id,
                                district_id=district.id,
                                province_id=province.id
                            )
                            db.add(c_user)
                            db.flush()
                        
                        # Add an extra camp assistant for some camps
                        if random.random() > 0.5:
                            extra_user_email = f"extra-user-{camp.id}@example.com"
                            if not db.query(User).filter(User.email == extra_user_email).first():
                                db.add(User(
                                    email=extra_user_email,
                                    hashed_password=password_hash,
                                    full_name=f"Asst Manager for {camp.name}",
                                    role=UserRole.CAMP,
                                    camp_id=camp.id,
                                    region_id=region.id,
                                    district_id=district.id,
                                    province_id=province.id
                                ))
                                db.flush()
                        
                        # Add Agents
                        for a_idx in range(2):
                            agent_email = f"agent-{camp.id}-{a_idx}@example.com"
                            agent = db.query(User).filter(User.email == agent_email).first()
                            if not agent:
                                agent = User(
                                    email=agent_email,
                                    hashed_password=password_hash,
                                    full_name=f"Agent {a_idx+1} ({camp.name})",
                                    role=UserRole.AGENT,
                                    camp_id=camp.id,
                                    region_id=region.id,
                                    district_id=district.id,
                                    province_id=province.id,
                                    last_lat=-15.4 + (random.random() * 2),
                                    last_lng=28.3 + (random.random() * 2),
                                    is_active=True
                                )
                                db.add(agent)
                                db.flush()
                            
                            # 6. Create Reports for Survey Progress
                            if random.random() > 0.4:
                                conf_no = f"CONF-{camp.id}-{agent.id}"
                                if not db.query(Report).filter(Report.confirmation_no == conf_no).first():
                                    report = Report(
                                        agent_id=agent.id,
                                        camp_id=camp.id,
                                        region_id=region.id,
                                        title=f"Survey Report - {camp.name}",
                                        status=ReportStatus.APPROVED if region.is_approved else ReportStatus.PENDING,
                                        gps_lat=agent.last_lat,
                                        gps_lng=agent.last_lng,
                                        confirmation_no=conf_no
                                    )
                                    db.add(report)

                        # 7. Create Farmers (Customers)
                        for f_idx in range(10):
                            membership = random.choice(["Affiliated", "Registered", "Non-Member", "Pending"])
                            customer = Customer(
                                full_name=f"Farmer {random.randint(1000, 9999)}",
                                membership_status=membership,
                                camp_id=camp.id,
                                region_id=region.id,
                                district_id=district.id,
                                province_id=province.id,
                                assigned_camp_user_id=c_user.id if random.random() > 0.3 else None
                            )
                            db.add(customer)

        # 8. Create some Audit Logs
        for _ in range(10):
            audit = AuditLog(
                user_id=1, # Assume 1 exists or just pick any
                action="EXECUTIVE_VIEW",
                details="Executive user accessed the national command center summary"
            )
            db.add(audit)

        db.commit()
        print("--- Seeding Completed Successfully ---")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
