from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.core.config import settings

def run():
    db = SessionLocal()
    try:
        # 1. Reset Admin (to admin123 as per .env)
        admin_email = str(settings.FIRST_SUPERUSER)
        admin_password = str(settings.FIRST_SUPERUSER_PASSWORD)
        admin = db.query(User).filter(User.email == admin_email).first()
        if admin:
            admin.hashed_password = get_password_hash(admin_password)
            print(f"✅ Updated Admin ({admin_email}) to '{admin_password}'")
        else:
            print(f"❌ Admin {admin_email} not found!")
        
        # 2. Reset everyone else to Capa@123
        other_users = db.query(User).filter(User.email != admin_email).all()
        for user in other_users:
            user.hashed_password = get_password_hash("Capa@123")
            print(f"✅ Reset {user.email} ({user.role}) to 'Capa@123'")
            
        db.commit()
        print("\n--- All passwords updated successfully ---")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run()
