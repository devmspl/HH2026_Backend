import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import Report

db = SessionLocal()
reports = db.query(Report).filter(Report.agent_id == 49764).all()

print(f"Total reports found for agent ID 49764: {len(reports)}")
for r in reports:
    print(f"ID: {r.id}, Status: {r.status}, Survey ID: {r.survey_id}")
