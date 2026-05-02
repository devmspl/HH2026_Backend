import sys
import os

# Add the project root to sys.path
sys.path.append('/Users/meandersoftware/Desktop/ReactNative/customer-accounting-planner-backend')

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User

def find_users_by_name(name):
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.full_name == name).all()
        print(f"Found {len(users)} users with name '{name}':")
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Role: {user.role}, is_superuser: {user.is_superuser}")
    finally:
        db.close()

if __name__ == "__main__":
    find_users_by_name("Region Manager - CHAVUMA")
