from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

def update_schema():
    print(f"Connecting to database...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            print("Connection successful. Checking columns...")
            
            # 1. account_status
            try:
                # We use VARCHAR because in app/models/user.py we set native_enum=False
                conn.execute(text("ALTER TABLE users ADD COLUMN account_status VARCHAR(50) DEFAULT 'active'"))
                conn.commit()
                print("✅ Added 'account_status' column")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print(f"ℹ️  Column 'account_status' already exists.")
                else:
                    print(f"⚠️  Skipping 'account_status': {e}")
            
            # 2. is_deleted
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("✅ Added 'is_deleted' column")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print(f"ℹ️  Column 'is_deleted' already exists.")
                else:
                    print(f"⚠️  Skipping 'is_deleted': {e}")

            # 3. deleted_at
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL"))
                conn.commit()
                print("✅ Added 'deleted_at' column")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print(f"ℹ️  Column 'deleted_at' already exists.")
                else:
                    print(f"⚠️  Skipping 'deleted_at': {e}")
            
            print("\nSchema update completed successfully.")
            
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update_schema()
