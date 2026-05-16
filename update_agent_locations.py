import random
from app.db.session import SessionLocal
from app.models.user import User, Province, District, Region, Camp
from datetime import datetime, timedelta

def update_agents():
    db = SessionLocal()
    try:
        # 1. Update Provinces, Districts, Regions, and Camps first (Anchors)
        print("Updating location anchors (Provinces, Districts, Regions, Camps)...")
        for model in [Province, District, Region, Camp]:
            entities = db.query(model).all()
            for ent in entities:
                ent.lat = random.uniform(-18.0, -8.0)
                ent.lng = random.uniform(23.0, 33.0)
            db.flush()
            print(f"✅ Updated {model.__tablename__}")

        # 2. Fetch all existing agents (case-insensitive role check)
        agents = db.query(User).filter(User.is_deleted == False, User.role.ilike('%AGENT%')).all()
        
        if not agents:
            print("❌ No agents found in the database to update.")
        else:
            print(f"Updating location data for {len(agents)} existing agents...")
            for agent in agents:
                # Set random location within Zambia's bounds
                agent.last_lat = random.uniform(-18.0, -8.0)
                agent.last_lng = random.uniform(23.0, 33.0)
                agent.last_seen = datetime.utcnow() - timedelta(minutes=random.randint(0, 60))
                agent.is_active = True
                print(f"✅ Updated Agent: {agent.full_name}")
            
        db.commit()
        print("\n🚀 Successfully updated all anchors and agents! Distance should now show up.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating agents: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_agents()
