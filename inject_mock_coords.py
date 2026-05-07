from sqlalchemy import create_engine, text
import random

DATABASE_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("Injecting test coordinates into local DB for COPPERBELT (Province ID 37)...")
        # Update agents in Copperbelt with fake coordinates using a subquery for Postgres compatibility
        query = """
        UPDATE users 
        SET last_lat = -12.8 + (random() * 2), 
            last_lng = 28.2 + (random() * 2),
            is_active = true
        WHERE id IN (
            SELECT id FROM users 
            WHERE province_id = 37 AND role = 'AGENT' 
            LIMIT 200
        )
        """
        conn.execute(text(query))
        conn.commit()
        print("Successfully injected coordinates for 200 agents in Copperbelt.")
            
except Exception as e:
    print(f"Error: {e}")
