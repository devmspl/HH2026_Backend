from sqlalchemy import create_engine, text
from app.core.config import settings

def fix_columns():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("Checking for missing columns in provinces table...")
        try:
            # Add lat and lng columns to provinces table if they don't exist
            conn.execute(text("ALTER TABLE provinces ADD COLUMN IF NOT EXISTS lat FLOAT;"))
            conn.execute(text("ALTER TABLE provinces ADD COLUMN IF NOT EXISTS lng FLOAT;"))
            conn.commit()
            print("✅ Successfully added missing columns (lat, lng) to provinces table.")
        except Exception as e:
            print(f"❌ Error updating table: {e}")

if __name__ == "__main__":
    fix_columns()
