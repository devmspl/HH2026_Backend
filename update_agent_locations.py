import random
from app.db.session import SessionLocal
from app.models.user import User
from datetime import datetime, timedelta

def update_agents():
    db = SessionLocal()
    try:
        # 1. Fetch all existing agents (case-insensitive role check)
        agents = db.query(User).filter(User.is_deleted == False, User.role.ilike('%AGENT%')).all()
        
        if not agents:
            print("❌ No agents found in the database to update.")
            return

        print(f"Updating location data for {len(agents)} existing agents...")

        for agent in agents:
            # Set random location within Zambia's bounds
            # This will make them show up on the map and calculate distance
            agent.last_lat = random.uniform(-18.0, -8.0)
            agent.last_lng = random.uniform(23.0, 33.0)
            agent.last_seen = datetime.utcnow() - timedelta(minutes=random.randint(0, 60))
            agent.is_active = True # Make them online for testing
            
            print(f"✅ Updated Agent: {agent.full_name} (ID: {agent.id})")
            
        db.commit()
        print("\n🚀 Successfully updated existing agents with dummy location data!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating agents: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_agents()
