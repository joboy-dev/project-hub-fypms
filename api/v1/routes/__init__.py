from fastapi import APIRouter

from api.v1.routes.auth import auth_router
from api.v1.routes.user import user_router
from api.v1.routes.external import external_router
from api.v1.routes.errors import error_router
from api.v1.routes.dashboard import dashboard_router

v1_router = APIRouter()

# Register all routes
v1_router.include_router(auth_router)
v1_router.include_router(user_router)
v1_router.include_router(external_router)
v1_router.include_router(error_router)
v1_router.include_router(dashboard_router)
