from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

def add_approval_tracking():
    print(f"Connecting to database...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            print("Connection successful. Adding approval tracking columns...")
            
            # 1. approved_by
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN approved_by INTEGER REFERENCES users(id)"))
                conn.commit()
                print("✅ Added 'approved_by' column")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print(f"ℹ️  Column 'approved_by' already exists.")
                else:
                    print(f"⚠️  Skipping 'approved_by': {e}")
            
            # 2. approved_at
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN approved_at TIMESTAMP WITH TIME ZONE DEFAULT NULL"))
                conn.commit()
                print("✅ Added 'approved_at' column")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print(f"ℹ️  Column 'approved_at' already exists.")
                else:
                    print(f"⚠️  Skipping 'approved_at': {e}")
            
            print("\nApproval tracking columns added successfully.")
            
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    add_approval_tracking()
