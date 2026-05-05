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
            db.commit()
            print(f"✅ Admin ({admin_email}) password updated.")
        else:
            print(f"❌ Admin {admin_email} not found!")
        
        # 2. Reset everyone else to Capa@123 (Optimized for thousands of users)
        print("\nStarting batch update for other users...")
        password_hash = get_password_hash("Capa@123") # Hashing once to save CPU time
        
        batch_size = 100
        count = 0
        
        # Count total users to process
        total_users = db.query(User).filter(User.email != admin_email).count()
        print(f"Total users to update: {total_users}")

        for i in range(0, total_users, batch_size):
            batch = db.query(User).filter(User.email != admin_email).offset(i).limit(batch_size).all()
            for user in batch:
                user.hashed_password = password_hash
                count += 1
            
            db.commit() # Commit each batch
            print(f"Progress: {count}/{total_users} users processed...")
            
        print(f"\n--- SUCCESS: {count} passwords updated successfully ---")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run()
