from app.db.session import SessionLocal
from app.models.user import Province, District, Region, Camp, User

db = SessionLocal()

print("Provinces:")
provinces = db.query(Province).limit(5).all()
for p in provinces:
    print(f"ID: {p.id}, Name: {p.name}")

print("\nDistricts:")
districts = db.query(District).limit(5).all()
for d in districts:
    print(f"ID: {d.id}, Name: {d.name}")

print("\nRegions:")
regions = db.query(Region).limit(5).all()
for r in regions:
    print(f"ID: {r.id}, Name: {r.name}")

print("\nCamps:")
camps = db.query(Camp).limit(5).all()
for c in camps:
    print(f"ID: {c.id}, Name: {c.name}")

print("\nUsers (for parent_id):")
users = db.query(User).limit(5).all()
for u in users:
    print(f"ID: {u.id}, Email: {u.email}")

db.close()
