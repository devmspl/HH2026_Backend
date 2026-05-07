from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("Checking active agents by province...")
        query = """
        SELECT p.name, count(u.id) 
        FROM users u 
        JOIN provinces p ON u.province_id = p.id 
        WHERE u.last_lat IS NOT NULL 
        GROUP BY p.name
        """
        result = conn.execute(text(query))
        rows = result.fetchall()
        if not rows:
            print("No provinces found with active agents.")
        for row in rows:
            print(f"Province: {row[0]}, Active Agents: {row[1]}")
            
except Exception as e:
    print(f"Error: {e}")
