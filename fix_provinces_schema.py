from sqlalchemy import create_engine, text
from app.core.config import settings

def fix_columns():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("Checking for missing columns in provinces table...")
        try:
            # Provinces
            conn.execute(text("ALTER TABLE provinces ADD COLUMN IF NOT EXISTS lat FLOAT;"))
            conn.execute(text("ALTER TABLE provinces ADD COLUMN IF NOT EXISTS lng FLOAT;"))
            
            # Districts
            conn.execute(text("ALTER TABLE districts ADD COLUMN IF NOT EXISTS lat FLOAT;"))
            conn.execute(text("ALTER TABLE districts ADD COLUMN IF NOT EXISTS lng FLOAT;"))
            
            # Regions
            conn.execute(text("ALTER TABLE regions ADD COLUMN IF NOT EXISTS lat FLOAT;"))
            conn.execute(text("ALTER TABLE regions ADD COLUMN IF NOT EXISTS lng FLOAT;"))
            
            conn.commit()
            print("✅ Successfully added missing columns (lat, lng) to provinces, districts, and regions tables.")
        except Exception as e:
            print(f"❌ Error updating table: {e}")

if __name__ == "__main__":
    fix_columns()
