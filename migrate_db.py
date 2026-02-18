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
        # --- users: all columns the User model expects ---
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(255)"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS camp_id INTEGER"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS region_id INTEGER"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS province_id INTEGER"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS district_id INTEGER"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS sex VARCHAR(20)"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profession VARCHAR(255)"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS nrc VARCHAR(50)"))
        # --- surveys ---
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS form_type VARCHAR(255) DEFAULT 'National Crops Survey'"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'draft'"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS description TEXT"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS target_respondents VARCHAR(100) DEFAULT 'All Agents'"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS instructions TEXT"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS allow_edit BOOLEAN DEFAULT FALSE"))
        db.execute(text("ALTER TABLE surveys ADD COLUMN IF NOT EXISTS attachment_required VARCHAR(50) DEFAULT 'Optional'"))
        # --- reports ---
        db.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS survey_id INTEGER"))
        db.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS province_id INTEGER"))
        db.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS district_id INTEGER"))
        db.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS region_id INTEGER"))
        db.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS camp_id INTEGER"))
        # --- customers ---
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS assigned_camp_user_id INTEGER"))
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS farmer_id VARCHAR(50)"))
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS membership_status VARCHAR(50)"))
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS household VARCHAR(255)"))
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS education_level VARCHAR(100)"))
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS emp_status VARCHAR(100)"))
        db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS photo VARCHAR(500)"))
        # If surveys.status is a PostgreSQL ENUM, convert to VARCHAR so we can store 'draft'/'active'/'ended'
        try:
            db.execute(text("ALTER TABLE surveys ALTER COLUMN status TYPE VARCHAR(50) USING lower(status::text)"))
            print("Converted surveys.status from enum to VARCHAR(50).")
        except Exception as e:
            if "type of column" in str(e).lower() or "already" in str(e).lower():
                pass  # already varchar or no enum
            else:
                print(f"Note: surveys.status conversion skipped: {e}")
        db.commit()
        print("Migration successful: all tables and columns verified.")
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
