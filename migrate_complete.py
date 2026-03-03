from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    
    # helper to run single command and ignore errors
    def run_cmd(conn, sql):
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"Success: {sql}")
        except Exception as e:
            print(f"Skipped: {sql} - {e}")
            conn.rollback()

    with engine.connect() as conn:
        print("Migrating columns...")
        run_cmd(conn, "ALTER TABLE national_crops ADD COLUMN crop_id VARCHAR(100)")
        run_cmd(conn, "ALTER TABLE regional_crops ADD COLUMN rcrop_id VARCHAR(100)")
        run_cmd(conn, "ALTER TABLE national_crops ALTER COLUMN picture TYPE TEXT")
        run_cmd(conn, "ALTER TABLE regional_crops ALTER COLUMN picture TYPE TEXT")
        run_cmd(conn, "ALTER TABLE crop_families ALTER COLUMN picture TYPE TEXT")
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
