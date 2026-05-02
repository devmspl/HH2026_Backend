import sys
import os

# Add the project root to sys.path
sys.path.append('/Users/meandersoftware/Desktop/ReactNative/customer-accounting-planner-backend')

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.api.v1.endpoints.dashboard import get_dashboard_stats

def simulate_get_stats(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print("User not found")
            return
            
        stats = get_dashboard_stats(db=db, current_user=user)
        print(f"Stats for {user.full_name} ({user.role}):")
        print(f"Total Agents: {stats['total_agents']}")
        print(f"Active Agents: {stats['active_agents']}")
        print(f"Inactive Agents: {stats['inactive_agents']}")
        print(f"Total Reports: {stats['total_reports']}")
        
    finally:
        db.close()

if __name__ == "__main__":
    simulate_get_stats("region_chavuma@example.com")
