from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
import app.models.user
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

def run_migrations():
    with engine.begin() as con:
        from sqlalchemy import text
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50);"))
        except Exception:
            pass
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN province_id INTEGER REFERENCES provinces(id);"))
        except Exception:
            pass
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN district_id INTEGER REFERENCES districts(id);"))
        except Exception:
            pass
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id);"))
        except Exception:
            pass
        try:
            con.execute(text("ALTER TABLE chat_groups ADD COLUMN camp_id INTEGER REFERENCES camps(id);"))
        except Exception:
            pass
        try:
            con.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::text;"))
        except Exception:
            pass

# run_migrations()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"GLOBAL ERROR: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error",
            "error": str(exc)
        },
    )

# Middleware for unexpected errors
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(f"MIDDLEWARE ERROR: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Critical Server Error",
                "error": str(exc)
            },
        )

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to CCNS Customer 180 API", "docs": "/docs"}
