from app.db.session import SessionLocal
from app.models.user import User

def list_all_active_users():
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_deleted == False).all()
        print(f"--- ALL ACTIVE USERS --- ({len(users)})")
        print(f"{'ID':<4} | {'Email':<30} | {'Name':<20} | {'Role':<20}")
        print("-" * 85)
        for u in users:
            print(f"{u.id:<4} | {u.email:<30} | {u.full_name or 'N/A':<20} | {u.role:<20}")
    finally:
        db.close()

if __name__ == "__main__":
    list_all_active_users()
