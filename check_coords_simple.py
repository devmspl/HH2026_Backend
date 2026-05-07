from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Check all agents
        result = conn.execute(text("SELECT id, full_name, role, last_lat, last_lng FROM users WHERE role ILIKE '%AGENT%'"))
        agents = result.fetchall()
        print(f"Total Agents in DB: {len(agents)}")
        
        # Check agents with coordinates
        result = conn.execute(text("SELECT id, full_name, role, last_lat, last_lng FROM users WHERE last_lat IS NOT NULL"))
        users_with_coords = result.fetchall()
        print(f"Users with Coordinates: {len(users_with_coords)}")
        
        for user in users_with_coords:
            print(f"ID: {user[0]}, Name: {user[1]}, Role: {user[2]}, Lat: {user[3]}, Lng: {user[4]}")
            
except Exception as e:
    print(f"Error: {e}")
