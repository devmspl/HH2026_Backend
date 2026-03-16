from app.db.session import engine
from sqlalchemy import text

def migrate():
    print("Adding columns to chat_groups table...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50)"))
            print("group_type added.")
        except Exception as e:
            print(f"Error or already exists: {e}")
            
        try:
            conn.execute(text("ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id)"))
            print("region_id added.")
        except Exception as e:
            print(f"Error or already exists: {e}")
        
        conn.commit()

if __name__ == "__main__":
    migrate()
