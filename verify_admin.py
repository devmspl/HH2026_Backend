from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import verify_password
from app.core.config import settings

def run():
    db = SessionLocal()
    try:
        admin_email = str(settings.FIRST_SUPERUSER)
        print(f"\n[DEBUG] Checking for SuperAdmin: {admin_email}")
        
        user = db.query(User).filter(User.email == admin_email).first()
        
        if not user:
            print(f"❌ User '{admin_email}' NOT FOUND in the database.")
            
            # List any potential admin accounts to help identify the correct email
            print("\nSearching for any users with SUPER_ADMIN or ADMINISTRATOR roles:")
            admins = db.query(User).filter(User.role.in_(["SUPER_ADMIN", "ADMINISTRATOR"])).all()
            if not admins:
                print("No admin users found at all!")
            else:
                for a in admins:
                    print(f" - Found Admin: {a.email} (Role: {a.role})")
            return

        print(f"\n--- Admin Info Found ---")
        print(f"Email: {user.email}")
        print(f"Full Name: {user.full_name}")
        print(f"Role: {user.role}")
        print(f"Is Active: {user.is_active}")
        print(f"Hashed Password Prefix: {user.hashed_password[:15]}...")
        
        # Test common passwords
        test_pwds = ["admin123", "password123", "Capa@123", "password"]
        found = False
        for pwd in test_pwds:
            if verify_password(pwd, user.hashed_password):
                print(f"✅ VERIFIED: The password is '{pwd}'")
                found = True
                break
        
        if not found:
            print("❌ NO MATCH: None of the standard passwords match this hash.")
            print("Suggestion: Run reset_all_passwords.py again to ensure the hash is correct.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run()
