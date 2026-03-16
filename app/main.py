from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
import app.models.user  # Import models to ensure they are registered

from sqlalchemy import text

# Create database tables
Base.metadata.create_all(bind=engine)

def run_migrations():
    with engine.begin() as con:
        # Chat Groups Migration
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50);"))
        except Exception:
            pass
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id);"))
        except Exception:
            pass
            
        # User Role Migration (Enum to String) to fix InvalidTextRepresentation
        try:
            con.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::text;"))
        except Exception:
            pass

run_migrations()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to CCNS Customer 180 API", "docs": "/docs"}
