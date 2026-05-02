import sys
import os

# Add the project root to sys.path
sys.path.append('/Users/meandersoftware/Desktop/ReactNative/customer-accounting-planner-backend')

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User

def list_region_users():
    db = SessionLocal()
    try:
        # Search for users with role REGION (case-insensitive-ish)
        region_users = db.query(User).filter(User.role.ilike('%REGION%')).all()
        
        print(f"Found {len(region_users)} Region Users:\n")
        for user in region_users:
            print(f"ID: {user.id}")
            print(f"Name: {user.full_name}")
            print(f"Email: {user.email}")
            print(f"Role: {user.role}")
            print(f"Region ID: {user.region_id}")
            print(f"District ID: {user.district_id}")
            print("-" * 20)
            
    finally:
        db.close()

if __name__ == "__main__":
    list_region_users()
