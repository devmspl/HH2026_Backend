from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User, Customer, Camp
from app.core.config import settings
import random
import string

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def generate_cid():
    return ''.join(random.choices(string.ascii_uppercase, k=5))

db = SessionLocal()
try:
    TARGET_CAMP_ID = 22621
    camp = db.query(Camp).filter(Camp.id == TARGET_CAMP_ID).first()
    
    if not camp:
        print(f"Camp {TARGET_CAMP_ID} not found.")
    else:
        for i in range(1, 6):
            new_cust = Customer(
                full_name=f"Test Farmer {i}",
                customer_id=generate_cid(),
                farmer_id=f"F-TEST-{i:03d}",
                phone=f"097000000{i}",
                camp_id=camp.id,
                region_id=camp.region_id,
                district_id=camp.district_id,
                province_id=camp.province_id,
                membership_status="No",
                assigned_camp_user_id=None
            )
            db.add(new_cust)
        
        db.commit()
        print(f"Successfully created 5 unassigned customers for Camp ID: {TARGET_CAMP_ID} ({camp.name})")
finally:
    db.close()
