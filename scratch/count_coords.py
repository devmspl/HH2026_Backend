import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
total = db.query(User).filter(User.is_deleted == False, User.role.ilike('%AGENT%')).count()
has_coords = db.query(User).filter(
    User.is_deleted == False, 
    User.role.ilike('%AGENT%'),
    User.last_lat.isnot(None),
    User.last_lng.isnot(None)
).count()
print(f"Total active agents: {total}")
print(f"Active agents with coordinates: {has_coords}")
