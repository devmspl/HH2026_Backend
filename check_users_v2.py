from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import func

def check_members():
    db = SessionLocal()
    try:
        # Check District Roles (inclusive)
        ELIGIBLE_PROVINCIAL_ROLES = ["DISTRICT", "District", "district", "District User", "DISTRICT USER"]
        users = db.query(User).filter(
            User.role.in_(ELIGIBLE_PROVINCIAL_ROLES),
            User.is_deleted == False
        ).all()
        print(f"--- DISTRICT USERS (ELIGIBLE FOR PROVINCIAL) --- count: {len(users)}")
        for u in users:
            print(f"ID: {u.id}, Name: {u.full_name}, Role: {u.role}")

        # Check Provincial Roles
        ELIGIBLE_MY_ROLES = ["PROVINCIAL", "Provincial", "provincial", "Provincial User", "PROVINCIAL USER"]
        my_users = db.query(User).filter(
            User.role.in_(ELIGIBLE_MY_ROLES),
            User.is_deleted == False
        ).all()
        print(f"\n--- PROVINCIAL USERS --- count: {len(my_users)}")
        for u in my_users:
            print(f"ID: {u.id}, Name: {u.full_name}, Role: {u.role}")

    finally:
        db.close()

if __name__ == "__main__":
    check_members()
