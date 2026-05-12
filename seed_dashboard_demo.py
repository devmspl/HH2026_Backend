from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole, Report, Region, Camp
from datetime import datetime
import random

def seed_demo_data():
    db = SessionLocal()
    try:
        # IDs identified
        CHIPATA_CENTRAL_ID = 371
        LUANGENI_ID = 372

        # 1. Setup Chipata Central (To become BLUE)
        print("Processing Chipata Central (Target: BLUE)...")
        chipata_camps = db.query(Camp).filter(Camp.region_id == CHIPATA_CENTRAL_ID).all()
        chipata_agents = db.query(User).filter(User.region_id == CHIPATA_CENTRAL_ID, User.role == UserRole.AGENT).all()
        
        if not chipata_agents:
            print("No agents in Chipata Central, using a generic one...")
            any_agent = db.query(User).filter(User.role == UserRole.AGENT).first()
            chipata_agents = [any_agent]

        for camp in chipata_camps:
            # Check if camp already has a report
            existing = db.query(Report).filter(Report.camp_id == camp.id).first()
            if not existing:
                agent = random.choice(chipata_agents)
                report = Report(
                    agent_id=agent.id,
                    camp_id=camp.id,
                    region_id=CHIPATA_CENTRAL_ID,
                    district_id=camp.district_id,
                    province_id=camp.province_id,
                    title=f"Demo Report for {camp.name}",
                    description="Automated report to test dashboard status colors.",
                    status="pending",
                    gps_lat=-13.63, # Dummy Lat
                    gps_lng=32.65,  # Dummy Lng
                    confirmation_no=f"DEMO-{random.randint(10000, 99999)}"
                )
                db.add(report)
        
        print(f"Created reports for all {len(chipata_camps)} camps in Chipata Central.")

        # 2. Setup Luangeni (To become ORANGE)
        print("Processing Luangeni (Target: ORANGE)...")
        luangeni_camps = db.query(Camp).filter(Camp.region_id == LUANGENI_ID).all()
        luangeni_agents = db.query(User).filter(User.region_id == LUANGENI_ID, User.role == UserRole.AGENT).all()
        
        if not luangeni_agents:
            any_agent = db.query(User).filter(User.role == UserRole.AGENT).first()
            luangeni_agents = [any_agent]

        # Only report for half of the camps
        half_count = len(luangeni_camps) // 2
        for camp in luangeni_camps[:half_count]:
            existing = db.query(Report).filter(Report.camp_id == camp.id).first()
            if not existing:
                agent = random.choice(luangeni_agents)
                report = Report(
                    agent_id=agent.id,
                    camp_id=camp.id,
                    region_id=LUANGENI_ID,
                    district_id=camp.district_id,
                    province_id=camp.province_id,
                    title=f"Demo Report for {camp.name}",
                    description="Automated report to test dashboard status colors (Partial).",
                    status="pending",
                    gps_lat=-13.70, # Dummy Lat
                    gps_lng=32.70,  # Dummy Lng
                    confirmation_no=f"DEMO-{random.randint(10000, 99999)}"
                )
                db.add(report)

        print(f"Created reports for {half_count} out of {len(luangeni_camps)} camps in Luangeni.")

        db.commit()
        print("Demo data seeded successfully! Please refresh your dashboard.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_data()
