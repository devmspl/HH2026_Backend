from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    db_url = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"

print(f"Connecting to: {db_url}")
engine = create_engine(db_url)

try:
    with engine.connect() as conn:
        # Check how many unnamed customers exist
        count_query = text("SELECT COUNT(*) FROM customers WHERE full_name = 'Unnamed' OR full_name IS NULL OR full_name = '';")
        result = conn.execute(count_query)
        count = result.scalar()
        
        print(f"Found {count} 'Unnamed' or empty customer records.")
        
        if count > 0:
            # Delete them
            delete_query = text("DELETE FROM customers WHERE full_name = 'Unnamed' OR full_name IS NULL OR full_name = '';")
            conn.execute(delete_query)
            conn.commit()
            print(f"Successfully deleted {count} records.")
        else:
            print("No records to delete.")
            
except Exception as e:
    print(f"Error: {e}")
