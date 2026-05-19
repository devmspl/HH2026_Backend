import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
# Find recent login/active users
users = db.query(User).filter(User.is_deleted == False).order_by(User.last_seen.desc().nullslast()).limit(5).all()
print("Most recently active users:")
for u in users:
    print(f"ID: {u.id}, Name: {u.full_name}, Email: {u.email}, Role: {u.role}, Province: {u.province_id}, District: {u.district_id}, Region: {u.region_id}, Camp: {u.camp_id}")
