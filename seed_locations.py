from app.db.session import SessionLocal
from app.models.user import User
from app.core.config import settings
from datetime import datetime
import random

def update_locations():
    print(f"Connecting to: {settings.DATABASE_URL}")
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Found {len(users)} users")
        for u in users:
            # Percentage based logic used in GISMap.tsx (top/left %)
            u.last_lat = random.uniform(20.0, 70.0)
            u.last_lng = random.uniform(20.0, 80.0)
            u.last_seen = datetime.now()
            # Ensure they are active
            u.is_active = True
            print(f"Updating {u.full_name}: {u.last_lat}, {u.last_lng}")
        db.commit()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_locations()
