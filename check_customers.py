from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User, Customer
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()
try:
    total_customers = db.query(Customer).count()
    unassigned_customers = db.query(Customer).filter(Customer.assigned_camp_user_id == None).count()
    print(f"Total Customers: {total_customers}")
    print(f"Unassigned Customers: {unassigned_customers}")
    
    if unassigned_customers == 0:
        print("No unassigned customers found. Need to create some.")
    else:
        sample = db.query(Customer).filter(Customer.assigned_camp_user_id == None).limit(3).all()
        for c in sample:
            print(f"Name: {c.full_name} | Camp ID: {c.camp_id}")
finally:
    db.close()
