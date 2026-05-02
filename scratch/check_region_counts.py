import sys
import os

# Add the project root to sys.path
sys.path.append('/Users/meandersoftware/Desktop/ReactNative/customer-accounting-planner-backend')

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole

def check_region_counts(region_id):
    db = SessionLocal()
    try:
        total_users = db.query(User).filter(User.region_id == region_id, User.is_deleted == False).count()
        total_agents = db.query(User).filter(
            User.region_id == region_id, 
            User.role.ilike('%AGENT%'), 
            User.is_deleted == False
        ).count()
        total_camp_users = db.query(User).filter(
            User.region_id == region_id, 
            User.role.ilike('%CAMP%'), 
            User.is_deleted == False
        ).count()
        
        global_total_users = db.query(User).filter(User.is_deleted == False).count()
        global_total_agents = db.query(User).filter(User.role.ilike('%AGENT%'), User.is_deleted == False).count()
        
        print(f"Region {region_id} counts:")
        print(f"Total Users in Region: {total_users}")
        print(f"Total Agents in Region: {total_agents}")
        print(f"Total Camp Users in Region: {total_camp_users}")
        print("\nGlobal counts:")
        print(f"Global Total Users: {global_total_users}")
        print(f"Global Total Agents: {global_total_agents}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_region_counts(438) # Chavuma
