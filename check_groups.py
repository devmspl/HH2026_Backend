from app.db.session import SessionLocal
from app.models.user import User, ChatGroup

def check_memberships():
    db = SessionLocal()
    try:
        groups = db.query(ChatGroup).all()
        print("--- ALL GROUPS & MEMBERS ---")
        for g in groups:
            member_names = [m.full_name for m in g.members]
            print(f"Group: {g.name}, Type: {g.group_type}, Members: {member_names}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_memberships()
