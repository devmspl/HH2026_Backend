from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("Altering crop_families...")
        conn.execute(text("ALTER TABLE crop_families ALTER COLUMN picture TYPE TEXT"))
        print("Altering national_crops...")
        conn.execute(text("ALTER TABLE national_crops ALTER COLUMN picture TYPE TEXT"))
        print("Altering regional_crops...")
        conn.execute(text("ALTER TABLE regional_crops ALTER COLUMN picture TYPE TEXT"))
        conn.commit()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
