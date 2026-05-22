from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine("postgresql://postgres:123456789@localhost:5432/ccns_customer_180")
Session = sessionmaker(bind=engine)
db = Session()

result = db.execute(text("SELECT family_name FROM crop_families"))
families = [row[0] for row in result]
print("Families in DB:", families)
