from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT count(*) FROM users"))
        count = res.fetchone()[0]
        print(f"Total Users in local DB: {count}")
        
        res = conn.execute(text("SELECT count(*) FROM provinces"))
        count = res.fetchone()[0]
        print(f"Total Provinces in local DB: {count}")
            
except Exception as e:
    print(f"Error: {e}")
