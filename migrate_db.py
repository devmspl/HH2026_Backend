from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User, ChatGroup, ChatMessage # Ensure models are loaded

def migrate():
    print("Migrating database...")
    # Create all tables that don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Add location column to users table if it doesn't exist (for existing tables)
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(255)"))
        db.commit()
        print("Migration successful: all tables and columns verified.")
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
