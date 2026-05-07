from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("Creating performance indexes...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_location ON users(last_lat, last_lng) WHERE last_lat IS NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_geo_filters ON users(province_id, district_id, region_id, camp_id)"))
        conn.commit()
        print("Indexes created successfully.")
            
except Exception as e:
    print(f"Error: {e}")
