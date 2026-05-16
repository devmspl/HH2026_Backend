from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
try:
    print("Listing unique roles in the system...")
    roles = db.query(User.role).distinct().all()
    for r in roles:
        print(f"Role found: '{r[0]}'")
        
    print("\nChecking users who are currently appearing but shouldn't...")
    users = db.query(User.full_name, User.role).filter(User.is_deleted == False).limit(10).all()
    for u in users:
        print(f"User: {u.full_name} | Role: {u.role}")
finally:
    db.close()
