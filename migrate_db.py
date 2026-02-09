from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import * # Ensure all models are loaded

def migrate():
    print("Migrating database...")
    # Create all tables that don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Add columns to existing tables if they don't exist
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(255)"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS form_type VARCHAR(255) DEFAULT 'National Crops Survey'"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'draft'"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS description TEXT"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS target_respondents VARCHAR(100) DEFAULT 'All Agents'"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS instructions TEXT"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS allow_edit BOOLEAN DEFAULT FALSE"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS attachment_required VARCHAR(50) DEFAULT 'Optional'"))
        db.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS survey_id INTEGER"))
        db.commit()
        print("Migration successful: all tables and columns verified.")
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
