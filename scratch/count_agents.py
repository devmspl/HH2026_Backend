import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
total_agents = db.query(User).filter(User.is_deleted == False, User.role.ilike('%AGENT%')).count()
print(f"Total active agents in DB: {total_agents}")
