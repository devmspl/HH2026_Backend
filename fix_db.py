from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    db_url = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"

print(f"Connecting to: {db_url}")
engine = create_engine(db_url)

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE report_images ALTER COLUMN image_url TYPE TEXT;"))
    conn.commit()
    print("Column image_url altered to TEXT successfully.")
