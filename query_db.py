from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
camp_users = db.query(User).filter(User.role == 'CAMP').all()
for u in camp_users:
    print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}, CampID: {u.camp_id}, SuperUser: {u.is_superuser}")
