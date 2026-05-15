from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()
try:
    users = db.query(User).filter(User.role == "CAMP").limit(5).all()
    print("--- CAMP USERS & THEIR CAMPS ---")
    for u in users:
        print(f"Email: {u.email} | Camp ID: {u.camp_id} | Name: {u.full_name}")
finally:
    db.close()
