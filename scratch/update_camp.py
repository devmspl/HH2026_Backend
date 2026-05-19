import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import Camp, User, Customer

db = SessionLocal()
camp_id = 22630 # Muwanjuni Primary School-01

camp = db.query(Camp).filter(Camp.id == camp_id).first()
if camp:
    print(f"Old total_customers: {camp.total_customers}")
    camp.total_customers = 5
    
    # Also let's link some customers to this camp so 'Total Affiliated' also shows > 0
    # Let's find customers in the same region
    agent = db.query(User).filter(User.email == 'agent_101001000801@example.com').first()
    if agent and agent.region_id:
        customers = db.query(Customer).filter(Customer.region_id == agent.region_id).all()
        print(f"Found {len(customers)} customers in region {agent.region_id}")
        for c in customers[:3]: # Link up to 3 customers
            c.camp_id = camp_id
            print(f"Linked customer {c.id} to camp {camp_id}")
            
    db.commit()
    print("Camp updated successfully!")
    
    # Verify
    db.refresh(camp)
    print(f"New total_customers: {camp.total_customers}")
    affiliated = db.query(Customer).filter(Customer.camp_id == camp_id).count()
    print(f"New Affiliated Count: {affiliated}")
else:
    print("Camp not found!")
