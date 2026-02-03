import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/customer_management")

def fix_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("Checking for 'category' column in 'customers' table...")
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='customers' AND column_name='category';")
        if not cur.fetchone():
            print("Adding 'category' column...")
            cur.execute("ALTER TABLE customers ADD COLUMN category VARCHAR(100);")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_db()
