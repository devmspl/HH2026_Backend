from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.config import settings

def seed_superuser():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
        if not user:
            print(f"Creating superuser {settings.FIRST_SUPERUSER}...")
            superuser = User(
                email=settings.FIRST_SUPERUSER,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                full_name="System Super Admin",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_superuser=True
            )
            db.add(superuser)
            db.commit()
            print("Superuser created successfully.")
        else:
            print("Superuser already exists.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_superuser()
