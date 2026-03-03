import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

def migrate():
    print("Starting Customer table migration...")
    with engine.connect() as conn:
        try:
            # Table name in Postgres might be lowercase or as specified in __tablename__
            table_name = 'customers'
            
            # Check for customer_id
            print(f"Checking for customer_id in {table_name} table...")
            query = text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}' AND column_name='customer_id'")
            result = conn.execute(query)
            if not result.fetchone():
                print("Adding customer_id column...")
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN customer_id VARCHAR(100)"))
                conn.commit()
                print("customer_id added successfully.")
            else:
                print("customer_id already exists.")

            # Ensure photo is TEXT
            print("Ensuring photo column is TEXT type...")
            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN photo TYPE TEXT"))
            conn.commit()
            print("photo column updated to TEXT.")

            print("Migration completed successfully.")
        except Exception as e:
            print(f"Migration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
