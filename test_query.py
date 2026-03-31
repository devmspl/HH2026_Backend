from app.db.session import SessionLocal
from app.models.user import User

def test_query():
    db = SessionLocal()
    try:
        ELIGIBLE_PROVINCIAL_ROLES = ["DISTRICT", "District", "district", "District User", "DISTRICT USER"]
        users = db.query(User).filter(
            User.role.in_(ELIGIBLE_PROVINCIAL_ROLES),
            User.is_deleted == False
        ).all()
        print(f"Users matches: {len(users)}")
        for u in users:
            print(f"- {u.id}: {u.full_name} ({u.role})")
    finally:
        db.close()

if __name__ == "__main__":
    test_query()
