import sys
import os
import json
import uuid
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User, Report, Survey, ReportStatus

db = SessionLocal()

# 1. Find the agent
agent = db.query(User).filter(User.email == 'agent_101001000801@example.com').first()
if not agent:
    print("Agent not found!")
    sys.exit(1)

# 2. Find or create a survey
survey = db.query(Survey).filter(Survey.form_type == "National Crops Survey").first()
if not survey:
    survey = Survey(
        title="National Crops Survey Mock",
        form_type="National Crops Survey",
        status="active",
        fields_schema="[]"
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    print(f"Created mock survey with ID: {survey.id}")
else:
    print(f"Found survey with ID: {survey.id}")

# 3. Create an approved report
report_data = {
    "total_farmers": 100,
    "participating_farmers": 50,
    "spoiled_responses": 5,
    "crops": [
        {"crop_name": "Maize", "yield_tonnes": 10},
        {"crop_name": "Wheat", "yield_tonnes": 5}
    ]
}

# Check if agent has last_lat/last_lng
lat = getattr(agent, 'last_lat', 31.5204) or 31.5204
lng = getattr(agent, 'last_lng', 74.3587) or 74.3587

report = Report(
    agent_id=agent.id,
    survey_id=survey.id,
    title=f"Mock Approved Report - {agent.full_name}",
    description="Mock report added for testing purposes to increase total_farmers count.",
    status=ReportStatus.APPROVED,
    gps_lat=lat,
    gps_lng=lng,
    confirmation_no=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
    survey_data=json.dumps(report_data),
    province_id=agent.province_id,
    district_id=agent.district_id,
    region_id=agent.region_id,
    camp_id=agent.camp_id
)

db.add(report)
db.commit()
print(f"Mock approved report created successfully! ID: {report.id}")
print("You should now see 100 as Total Farmers in the survey form (or sum of all approved reports).")
