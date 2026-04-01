from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def reset_passwords():
    db = SessionLocal()
    try:
        users_to_reset = ["dinesh@gmail.com", "parveshh@gmail.com", "parvesh@gmail.com", "nitin@gmail.com"]
        for email in users_to_reset:
            user = db.query(User).filter(User.email == email).first()
            if user:
                user.hashed_password = get_password_hash("password")
                print(f"✅ Reset password for {email} ({user.role})")
            else:
                print(f"❌ User {email} not found")
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    reset_passwords()
