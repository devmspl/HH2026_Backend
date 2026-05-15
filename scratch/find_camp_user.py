from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User, Customer, Camp
from app.core.config import settings

# Database connection
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()
try:
    print("--- CAMP USERS AND THEIR CAMP CUSTOMERS ---")
    results = db.query(User.email, User.full_name, User.camp_id, Camp.name).join(
        Camp, User.camp_id == Camp.id
    ).filter(User.role == "CAMP").limit(10).all()

    for r in results:
        # Count customers in this camp
        camp_cust_count = db.query(Customer).filter(Customer.camp_id == r.camp_id).count()
        # Count customers assigned to this user
        assigned_cust_count = db.query(Customer).filter(Customer.assigned_camp_user_id == db.query(User.id).filter(User.email == r.email).scalar_subquery()).count()
        
        if camp_cust_count > 0 or assigned_cust_count > 0:
            print(f"Email: {r.email}")
            print(f"Name: {r.full_name}")
            print(f"Camp: {r[3]} (ID: {r.camp_id})")
            print(f"Camp Total Customers: {camp_cust_count}")
            print(f"Assigned to User: {assigned_cust_count}")
            print("-" * 30)

finally:
    db.close()
