import json
import random
import uuid
from app.db.session import SessionLocal
from app.models.user import Province, District, Region, Report, User, ReportStatus, Survey

def seed_comprehensive_data():
    db = SessionLocal()
    try:
        # Get an agent for the reports
        agent = db.query(User).filter(User.role == "AGENT").first()
        if not agent:
            agent = db.query(User).filter(User.role == "agent").first()
        if not agent:
            agent = db.query(User).first()
        
        if not agent:
            print("❌ No user found to assign reports to.")
            return

        # Get the surveys (National and Regional)
        national_survey = db.query(Survey).filter(Survey.form_type == "National Crops Survey").first()
        regional_survey = db.query(Survey).filter(Survey.form_type == "Regional Crops Survey").first()
        
        if not national_survey:
            national_survey = Survey(name="National Crops 2024", form_type="National Crops Survey")
            db.add(national_survey)
            db.flush()
        
        if not regional_survey:
            regional_survey = Survey(name="Regional Crops 2024", form_type="Regional Crops Survey")
            db.add(regional_survey)
            db.flush()

        # Clear existing dummy reports to avoid clutter
        db.query(Report).filter(Report.description.like("%dummy data%")).delete(synchronize_session=False)
        db.commit()
        print("🧹 Cleared old dummy data.")

        crop_families = {
            "Cereals": ["Maize", "Wheat", "Rice", "Sorghum", "Millet"],
            "Legumes": ["Soybeans", "Groundnuts", "Beans"],
            "Tubers": ["Cassava", "Potatoes", "Sweet Potatoes"],
            "Vegetables": ["Cabbage", "Tomatoes", "Onions"],
            "Fruits": ["Oranges", "Bananas", "Mangoes"],
            "Other": ["Tobacco", "Cotton", "Sunflower"]
        }
        
        family_list = list(crop_families.keys())
        provinces = db.query(Province).all()
        
        print(f"Generating colorful data for {len(provinces)} provinces...")

        for p in provinces:
            # Force a random dominant family for this province to ensure color variety
            dominant_family = random.choice(family_list)
            
            districts = db.query(District).filter(District.province_id == p.id).all()
            
            # 1. Generate 4 National Reports per province
            for i in range(4):
                total_f = random.randint(1000, 3000)
                participating = random.randint(int(total_f * 0.7), int(total_f * 0.9))
                spoiled = random.randint(10, 100)
                
                crops_data = []
                # Add the dominant family with high yield
                dom_crop = random.choice(crop_families[dominant_family])
                crops_data.append({
                    "crop_name": dom_crop,
                    "family_name": dominant_family,
                    "yield_tonnes": round(random.uniform(2000.0, 5000.0), 1)
                })
                
                # Add 2-3 other families with lower yield
                other_families = [f for f in family_list if f != dominant_family]
                for other_fam in random.sample(other_families, 3):
                    other_crop = random.choice(crop_families[other_fam])
                    crops_data.append({
                        "crop_name": other_crop,
                        "family_name": other_fam,
                        "yield_tonnes": round(random.uniform(100.0, 800.0), 1)
                    })
                
                survey_data = {
                    "total_farmers": total_f,
                    "participating_farmers": participating,
                    "spoiled_responses": spoiled,
                    "crops": crops_data
                }
                
                report = Report(
                    agent_id=agent.id,
                    survey_id=national_survey.id,
                    title=f"National Survey - {p.name} (Dominant: {dominant_family})",
                    description="Comprehensive colorful dummy data",
                    status=ReportStatus.APPROVED,
                    gps_lat=random.uniform(-18.0, -8.0),
                    gps_lng=random.uniform(22.0, 33.0),
                    confirmation_no=f"NAT-{uuid.uuid4().hex[:6].upper()}",
                    survey_data=json.dumps(survey_data),
                    province_id=p.id
                )
                db.add(report)

            # 2. Generate Regional Reports for each district/region
            for d in districts:
                regions = db.query(Region).filter(Region.district_id == d.id).all()
                for r in regions:
                    # 1-2 Regional reports per region
                    for k in range(random.randint(1, 2)):
                        # Pick a random family for regional tally
                        reg_family = random.choice(family_list)
                        reg_crop = random.choice(crop_families[reg_family])
                        
                        total_f = random.randint(50, 300)
                        participating = random.randint(int(total_f * 0.7), int(total_f * 0.98))
                        spoiled = random.randint(0, 10)
                        
                        survey_data = {
                            "total_farmers": total_f,
                            "participating_farmers": participating,
                            "spoiled_responses": spoiled,
                            "crops": [{
                                "crop_name": reg_crop,
                                "family_name": reg_family,
                                "yield_tonnes": round(random.uniform(10.0, 150.0), 1)
                            }]
                        }
                        
                        report = Report(
                            agent_id=agent.id,
                            survey_id=regional_survey.id,
                            title=f"Regional Survey - {r.name}",
                            description="Tally colorful dummy data",
                            status=ReportStatus.APPROVED,
                            gps_lat=random.uniform(-18.0, -8.0),
                            gps_lng=random.uniform(22.0, 33.0),
                            confirmation_no=f"REG-{uuid.uuid4().hex[:6].upper()}",
                            survey_data=json.dumps(survey_data),
                            province_id=p.id,
                            district_id=d.id,
                            region_id=r.id
                        )
                        db.add(report)
            
            db.commit()
            print(f"✅ Province {p.name} seeded.")

        print("\n🚀 ALL COMPREHENSIVE DUMMY DATA SEEDED SUCCESSFULLY!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_comprehensive_data()
