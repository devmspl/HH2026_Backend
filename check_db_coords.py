import os
import sys

# Add backend to path to import models
sys.path.append('/Users/meandersoftware/Desktop/ReactNative/customer-accounting-planner-backend')

from app.db.session import SessionLocal
from app.models.user import User

def check_agent_coordinates():
    db = SessionLocal()
    try:
        # Check total agents
        total_agents = db.query(User).filter(User.role.ilike('%AGENT%')).count()
        print(f"Total Agents: {total_agents}")

        # Check agents with coordinates
        agents_with_coords = db.query(User).filter(
            User.last_lat.isnot(None),
            User.last_lng.isnot(None)
        ).all()
        
        print(f"Users with Coordinates: {len(agents_with_coords)}")
        
        for user in agents_with_coords:
            print(f"User ID: {user.id}, Name: {user.full_name}, Role: {user.role}, Lat: {user.last_lat}, Lng: {user.last_lng}")

    finally:
        db.close()

if __name__ == "__main__":
    check_agent_coordinates()
