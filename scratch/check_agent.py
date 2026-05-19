import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
agent = db.query(User).filter(User.email == 'agent_101001000801@example.com').first()

if agent:
    print(f"Name: {agent.full_name}")
    print(f"Role: {agent.role}")
    print(f"ID: {agent.id}")
else:
    print("Agent not found.")
