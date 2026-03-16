from app.db.session import engine
from sqlalchemy import text
with engine.begin() as con:
    try:
        con.execute(text("ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50);"))
        con.execute(text("ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id);"))
        print("Success!")
    except Exception as e:
        print("Error:", e)
