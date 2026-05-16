import json
import random
import uuid
from app.db.session import SessionLocal
from app.models.user import Province, Report, User, ReportStatus

db = SessionLocal()

agent = db.query(User).filter(User.role == "agent").first()
if not agent:
    agent = db.query(User).first()

provinces = db.query(Province).all()

crop_families = [
    ("Maize", "Cereals"),
    ("Wheat", "Cereals"),
    ("Rice", "Cereals"),
    ("Soybeans", "Legumes"),
    ("Cassava", "Tubers"),
    ("Sorghum", "Cereals"),
    ("Millet", "Cereals"),
    ("Groundnuts", "Legumes"),
    ("Cotton", "Other"),
    ("Tobacco", "Other"),
    ("Sunflower", "Other"),
    ("Cabbage", "Vegetables"),
    ("Oranges", "Fruits")
]

for p in provinces:
    # We already have Eastern
    if p.name.upper() == "EASTERN":
        continue
    
    # 5 to 15 reports for each remaining province
    for i in range(random.randint(5, 15)):
        chosen_crop, family = random.choice(crop_families)
        yield_t = round(random.uniform(50.0, 500.0), 2)
        
        survey_data = {
            "crops": [
                {
                    "crop_name": chosen_crop,
                    "family_name": family,
                    "yield_tonnes": yield_t
                }
            ]
        }
        
        report = Report(
            agent_id=agent.id,
            title=f"Dummy Survey {p.name} {i}",
            description="Generated for Analytics Map testing",
            status=ReportStatus.APPROVED,
            gps_lat=-13.133,
            gps_lng=27.849,
            confirmation_no=str(uuid.uuid4())[:8].upper(),
            survey_data=json.dumps(survey_data),
            province_id=p.id
        )
        db.add(report)

db.commit()
print("✅ Successfully generated dummy crop survey data for all provinces!")
