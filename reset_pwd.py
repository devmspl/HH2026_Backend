from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User
from app.core.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()
try:
    email = "camp_101001000101@example.com"
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.hashed_password = pwd_context.hash("admin123")
        db.commit()
        print(f"Password for {email} has been reset to 'admin123'")
    else:
        print(f"User {email} not found.")
finally:
    db.close()
