from sqlalchemy import create_all, text
import json
from app.db.session import SessionLocal
from app.models.user import Province, District, Region, Camp

db = SessionLocal()
try:
    print("Checking for existing location data...")
    for model in [Province, District, Region, Camp]:
        count = db.query(model).count()
        print(f"{model.__tablename__}: {count} records")
        first = db.query(model).first()
        if first:
            print(f"  First {model.__tablename__}: {first.name}")
finally:
    db.close()
