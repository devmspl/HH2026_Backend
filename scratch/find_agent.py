import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import User, Customer, Camp

db = SessionLocal()
agent = db.query(User).filter(User.email == 'agent_101001000801@example.com').first()

if agent:
    print(f"Agent Name: {agent.full_name}")
    print(f"Camp ID: {agent.camp_id}")
    print(f"Region ID: {agent.region_id}")
    
    camp = db.query(Camp).filter(Camp.id == agent.camp_id).first() if agent.camp_id else None
    if camp:
        print(f"Camp Name: {camp.name}")
        print(f"Camp total_customers: {camp.total_customers}")
    
    customers_by_camp = db.query(Customer).filter(Customer.camp_id == agent.camp_id).count() if agent.camp_id else 0
    print(f"Customers by Camp ID: {customers_by_camp}")
    
    customers_by_region = db.query(Customer).filter(Customer.region_id == agent.region_id).count() if agent.region_id else 0
    print(f"Customers in Region: {customers_by_region}")
else:
    print("Agent not found.")
