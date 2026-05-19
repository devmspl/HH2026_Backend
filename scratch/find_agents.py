import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User, Customer

db = SessionLocal()

# Find all agents
agents = db.query(User).filter(User.role.in_(['AGENT', 'Agent'])).all()

print(f"Total Agents found: {len(agents)}")
print("-" * 50)

found_any = False
for agent in agents:
    # Check directly assigned customers
    direct_customers = db.query(Customer).filter(Customer.agent_id == agent.id).count()
    
    # Check customers in same camp
    camp_customers = 0
    if agent.camp_id:
        camp_customers = db.query(Customer).filter(Customer.camp_id == agent.camp_id).count()
        
    if direct_customers > 0 or camp_customers > 0:
        found_any = True
        print(f"Agent: {agent.full_name} ({agent.email})")
        print(f"  ID: {agent.id}")
        print(f"  Directly Assigned Customers: {direct_customers}")
        print(f"  Customers in Camp (ID {agent.camp_id}): {camp_customers}")
        print("-" * 50)

if not found_any:
    print("No agents found with assigned customers or customers in their camp.")
    print("Let's look for ANY customers and see who they are assigned to.")
    
    customers = db.query(Customer).filter(Customer.agent_id.isnot(None)).limit(5).all()
    for c in customers:
        print(f"Customer ID: {c.id}, Agent ID: {c.agent_id}")
