"""
Reset Super Admin password to match .env (FIRST_SUPERUSER_PASSWORD).
Use when "Superuser already exists" but login fails – DB me purana password hai.

Run: python reset_superadmin_password.py
"""
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.core.config import settings

def run():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == str(settings.FIRST_SUPERUSER)).first()
        if not user:
            print(f"ERROR: User '{settings.FIRST_SUPERUSER}' not found. Run seed_db.py first.")
            return
        new_hash = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
        user.hashed_password = new_hash
        db.commit()
        print(f"Password updated for {settings.FIRST_SUPERUSER}. Ab .env wala password se login karo.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run()
