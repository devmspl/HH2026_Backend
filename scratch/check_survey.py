import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import Survey

db = SessionLocal()
surveys = db.query(Survey).all()

print(f"Total surveys found: {len(surveys)}")
for s in surveys:
    print(f"ID: {s.id}, Type: {s.form_type}, Status: {s.status}")
