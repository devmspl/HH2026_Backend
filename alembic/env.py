import os
import sys

# 1. SPECIAL FIX FOR MAC/PYTHON 3.12 HASHLIB ISSUE
try:
    import hashlib
except ValueError:
    # If hashlib crashes due to blake2b/OpenSSL issues, we mock it
    from unittest.mock import MagicMock
    mock_hashlib = MagicMock()
    sys.modules['hashlib'] = mock_hashlib
    print("[DEBUG] Hashlib mocked to bypass OpenSSL issue")

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# 2. Add app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), ".")))

# 3. Import your metadata and settings
from app.db.base import Base
from app.models.user import User, ChatGroup, ChatMessage, Province, District, Region, Camp
from app.core.config import settings

config = context.config
# 3. Set the database URL dynamically from settings (Escaping % for configparser)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
