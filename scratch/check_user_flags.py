import sys
import os

# Add the project root to sys.path
sys.path.append('/Users/meandersoftware/Desktop/ReactNative/customer-accounting-planner-backend')

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User

def check_user_flags(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User: {user.full_name}")
            print(f"Role: {user.role}")
            print(f"is_superuser: {user.is_superuser}")
            print(f"region_id: {user.region_id}")
            print(f"camp_id: {user.camp_id}")
        else:
            print("User not found")
    finally:
        db.close()

if __name__ == "__main__":
    check_user_flags("region_chavuma@example.com")
