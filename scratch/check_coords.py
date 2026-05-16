from app.db.session import SessionLocal
from app.models.user import User

def check():
    db = SessionLocal()
    agents = db.query(User).filter(User.role == "AGENT").all()
    has_coords = [a for a in agents if a.last_lat and a.last_lng]
    print(f"RESULT: TOTAL={len(agents)}, WITH_COORDS={len(has_coords)}")
    db.close()

if __name__ == "__main__":
    check()
