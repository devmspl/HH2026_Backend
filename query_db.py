import sys
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:123456789@localhost:5432/ccns_customer_180")
with engine.connect() as conn:
    result = conn.execute("SELECT id, name, form_type, status FROM surveys")
    for row in result:
        print(row)
