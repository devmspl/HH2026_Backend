from app.db.session import SessionLocal
from app.models.user import Survey

db = SessionLocal()
surveys = db.query(Survey).all()
for s in surveys:
    print(f"ID: {s.id} | Name: {s.name} | Type: {s.form_type} | Status: {s.status}")
db.close()
