from app.db.session import SessionLocal
from sqlalchemy import text

def fix_schema():
    db = SessionLocal()
    tables = ["provinces", "districts", "regions", "camps"]
    
    try:
        for table in tables:
            print(f"Checking table: {table}")
            # Use raw SQL to add columns if they don't exist
            # Note: PostgreSQL syntax. For SQLite, it's slightly different.
            # Assuming PostgreSQL based on psycopg2 in error log.
            try:
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS lat FLOAT;"))
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS lng FLOAT;"))
                db.commit()
                print(f"Successfully updated {table}")
            except Exception as e:
                db.rollback()
                print(f"Error updating {table}: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_schema()
