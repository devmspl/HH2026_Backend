from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("Checking agents for 'Chafye Primary School'...")
        # First find the camp ID
        query = "SELECT id, name, province_id, district_id, region_id FROM camps WHERE name ILIKE '%Chafye%'"
        res = conn.execute(text(query)).fetchall()
        for r in res:
            print(f"Camp ID: {r[0]}, Name: {r[1]}, ProvinceID: {r[2]}, DistrictID: {r[3]}, RegionID: {r[4]}")
            camp_id = r[0]
            
            # Now check agents in this camp
            query_agents = f"SELECT id, full_name, last_lat, last_lng FROM users WHERE camp_id = {camp_id}"
            agents = conn.execute(text(query_agents)).fetchall()
            print(f"Total Agents in this camp: {len(agents)}")
            for a in agents:
                print(f"Agent ID: {a[0]}, Name: {a[1]}, Lat: {a[2]}, Lng: {a[3]}")
            
except Exception as e:
    print(f"Error: {e}")
