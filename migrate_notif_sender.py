from sqlalchemy import create_engine, text

db_url = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
engine = create_engine(db_url)

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE notification_logs 
        ADD COLUMN IF NOT EXISTS sender_id INTEGER REFERENCES users(id)
    """))
    conn.commit()
    print("Migration done! sender_id column added to notification_logs.")
