from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

def migrate():
    print(f"Connecting to database...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            print("Connection successful. Adding is_approved column to regions table...")
            
            try:
                # Add is_approved column to regions table
                conn.execute(text("ALTER TABLE regions ADD COLUMN is_approved BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("✅ Added 'is_approved' column to 'regions' table")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print(f"ℹ️  Column 'is_approved' already exists in 'regions' table.")
                else:
                    print(f"⚠️  Skipping 'is_approved': {e}")
            
            print("\nMigration completed successfully.")
            
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
