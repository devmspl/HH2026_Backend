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

        crop_options = [
            ("Maize", "Cereals"),
            ("Wheat", "Cereals"),
            ("Rice", "Cereals"),
            ("Soybeans", "Legumes"),
            ("Cassava", "Tubers"),
            ("Sorghum", "Cereals"),
            ("Millet", "Cereals"),
            ("Groundnuts", "Legumes"),
            ("Cabbage", "Vegetables"),
            ("Oranges", "Fruits"),
            ("Tomatoes", "Vegetables"),
            ("Tobacco", "Other")
        ]

        provinces = db.query(Province).all()
        
        print(f"Generating data for {len(provinces)} provinces...")

        for p in provinces:
            districts = db.query(District).filter(District.province_id == p.id).all()
            
            # Generate 3-5 National Reports per province
            for i in range(random.randint(3, 5)):
                # Randomly pick 3-6 crops
                selected_crops = random.sample(crop_options, random.randint(3, 6))
                
                total_f = random.randint(500, 2000)
                participating = random.randint(int(total_f * 0.6), int(total_f * 0.95))
                spoiled = random.randint(5, 50)
                
                crops_data = []
                for crop_name, family in selected_crops:
                    crops_data.append({
                        "crop_name": crop_name,
                        "family_name": family,
                        "yield_tonnes": round(random.uniform(100.0, 1000.0), 1)
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
                    title=f"National Survey - {p.name} #{i+1}",
                    description=f"Comprehensive dummy data for {p.name}",
                    status=ReportStatus.APPROVED,
                    gps_lat=random.uniform(-18.0, -8.0),
                    gps_lng=random.uniform(22.0, 33.0),
                    confirmation_no=f"NAT-{uuid.uuid4().hex[:6].upper()}",
                    survey_data=json.dumps(survey_data),
                    province_id=p.id
                )
                db.add(report)

            # Generate Regional Reports for each district/region
            for d in districts:
                regions = db.query(Region).filter(Region.district_id == d.id).all()
                for r in regions:
                    # 1-2 Regional reports per region
                    for k in range(random.randint(1, 2)):
                        selected_crops = random.sample(crop_options, random.randint(2, 4))
                        
                        total_f = random.randint(50, 300)
                        participating = random.randint(int(total_f * 0.7), int(total_f * 0.98))
                        spoiled = random.randint(0, 10)
                        
                        crops_data = []
                        for crop_name, family in selected_crops:
                            crops_data.append({
                                "crop_name": crop_name,
                                "family_name": family,
                                "yield_tonnes": round(random.uniform(10.0, 150.0), 1)
                            })
                        
                        survey_data = {
                            "total_farmers": total_f,
                            "participating_farmers": participating,
                            "spoiled_responses": spoiled,
                            "crops": crops_data
                        }
                        
                        report = Report(
                            agent_id=agent.id,
                            survey_id=regional_survey.id,
                            title=f"Regional Survey - {r.name}",
                            description=f"Tally data for {r.name}, {d.name}",
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
