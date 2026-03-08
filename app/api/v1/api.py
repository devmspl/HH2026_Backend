from fastapi import APIRouter
from app.api.v1.endpoints import login, agents, reports, dashboard, surveys, notifications, chat, customers, search, locations, roles

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(surveys.router, prefix="/surveys", tags=["surveys"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
from app.api.v1.endpoints import upload
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
