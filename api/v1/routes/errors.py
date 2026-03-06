from fastapi import APIRouter, Request
from api.core.dependencies.context import add_template_context
from api.utils.loggers import create_logger

error_router = APIRouter(tags=["Errors"])
logger = create_logger(__name__)


@error_router.get("/404")
@add_template_context('pages/errors/404.html')
async def not_found_page(request: Request):
    return {}

@error_router.get("/500")
@add_template_context('pages/errors/500.html')
async def error_page(request: Request):
    return {}
