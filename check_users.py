from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import func

def check_district_users():
    db = SessionLocal()
    try:
        # Check all roles to see what's in the DB
        roles = db.query(User.role, func.count(User.id)).group_by(User.role).all()
        print("--- USER ROLES IN DB ---")
        for role, count in roles:
            print(f"Role: {role}, Count: {count}")
            
        print("\n--- DETAILED DISTRICT USERS ---")
        district_users = db.query(User).filter(User.role.ilike('%district%')).all()
        if not district_users:
            print("No District users found.")
        else:
            for u in district_users:
                print(f"ID: {u.id}, Name: {u.full_name}, Role: {u.role}, Province ID: {u.province_id}, Deleted: {u.is_deleted}")
    finally:
        db.close()

if __name__ == "__main__":
    check_district_users()
