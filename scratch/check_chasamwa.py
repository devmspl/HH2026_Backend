import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User, Camp, Region

db = SessionLocal()
camp = db.query(Camp).filter(Camp.name.ilike('%Chasamwa%')).first()
if camp:
    print(f"Camp: {camp.name}, ID: {camp.id}, Lat: {camp.lat}, Lng: {camp.lng}")
    agents = db.query(User).filter(User.camp_id == camp.id, User.role.ilike('%AGENT%')).all()
    print(f"Number of agents in this camp: {len(agents)}")
    for a in agents:
        print(f"Agent Name: {a.full_name}, Email: {a.email}, Lat: {a.last_lat}, Lng: {a.last_lng}")
else:
    print("Camp not found")
