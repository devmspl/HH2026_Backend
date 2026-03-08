from app.db.session import engine
from app.db.base import Base
from app.models.user import User, SystemRole, UserRole # Import all models here
from sqlalchemy import text, inspect

def init_and_migrate():
    print("Ensuring all tables exist...")
    # This will create all tables defined in app.models.user if they don't exist
    Base.metadata.create_all(bind=engine)
    print("Base tables checked/created.")

    ins = inspect(engine)
    if 'users' in ins.get_table_names():
        columns = [c['name'] for c in ins.get_columns('users')]
        if 'role_id' not in columns:
            print("Adding role_id column to users table...")
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES system_roles(id)'))
                conn.commit()
                print("role_id column added successfully.")
        else:
            print("role_id column already exists.")
    else:
        print("CRITICAL: users table not found even after create_all!")

if __name__ == "__main__":
    init_and_migrate()
