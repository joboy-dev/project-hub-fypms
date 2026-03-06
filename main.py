import sys
from fastapi import templating, staticfiles
import uvicorn, os, time
from typing import Optional
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, StreamingResponse
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware  # required by google oauth
from decouple import config
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jinja2.exceptions import TemplateNotFound

from api.core.dependencies.flash_messages import MessageCategory, flash, get_flashed_messages
from api.core.dependencies.middleware import AuthMiddleware
from api.db.database import create_database
from api.utils.loggers import create_logger
from api.utils.log_streamer import log_streamer
from api.utils.port_checker import find_free_port
from api.v1.routes import v1_router
from api.utils.settings import settings


os.makedirs("./logs", exist_ok=True)

create_database()

logger = create_logger(__name__, log_file='logs/error.log')
# performance_logger = create_logger(__name__, log_file='logs/performance.log')

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    lifespan=lifespan,
    title='API Documentation'
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

TEMP_DIR = './tmp/media'
os.makedirs(TEMP_DIR, exist_ok=True)
app.mount('/tmp/media', StaticFiles(directory=TEMP_DIR), name='tmp')

FILESTORAGE = f'./{config("FILESTORAGE")}'
os.makedirs(FILESTORAGE, exist_ok=True)
app.mount(f'/{config("FILESTORAGE")}', StaticFiles(directory=FILESTORAGE), name='files')

# Set up frontend templates
frontend = templating.Jinja2Templates('frontend/app')
frontend.env.globals['get_flashed_messages'] = get_flashed_messages

# Store frontend in app state for use in decorators
app.state.frontend = frontend

# Mount static files
os.makedirs("./frontend/static", exist_ok=True)
app.mount("/static", staticfiles.StaticFiles(directory="frontend/static"), name="static")

# Register Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=3600)
app.add_middleware(AuthMiddleware)

# Middleware to log details after each request
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Capture request start time
    start_time = time.time()

    # Process the request
    response = await call_next(request)

    # Calculate processing time
    process_time = time.time() - start_time
    formatted_process_time = f"{process_time:.3f}s"
    
    response.headers["X-Process-Time"] = formatted_process_time

    # Capture request and response details
    client_ip = request.client.host
    method = request.method
    url = request.url.path
    status_code = response.status_code

    # Format the log string similar to your example
    log_string = (
        f"{client_ip} - \"{method} {url}\" {status_code} - {formatted_process_time}"
    )

    # Log the formatted string
    logger.info(log_string)

    return response

# Load the router
app.include_router(v1_router)

@app.get("/logs", tags=["Home"])
async def stream_logs(
    lines: Optional[int] = Query(None), 
    log_file: Optional[str] = Query('app_logs')
) -> StreamingResponse:
    '''Endpoint to stream logs'''
    
    return StreamingResponse(log_streamer(f'logs/{log_file}.log', lines), media_type="text/event-stream")


# REGISTER EXCEPTION HANDLERS
@app.exception_handler(TemplateNotFound)
async def template_not_found_exception(request: Request, exc: TemplateNotFound):
    """Template not found exception handler"""
    
    logger.error(f"TemplateNotFound: {request.url.path} | {exc}", stacklevel=2)
    return RedirectResponse(url="/404", status_code=303)


@app.exception_handler(HTTPException)
async def http_exception(request: Request, exc: HTTPException):
    """HTTP exception handler"""

    exc_type, exc_obj, exc_tb = sys.exc_info()
    logger.error(f"HTTPException: {request.url.path} | {exc.status_code} | {exc.detail}", stacklevel=2)
    # logger.error(f"[ERROR] - An error occured | {exc}, {exc_type} {exc_obj} line {exc_tb.tb_lineno}", stacklevel=2)
    
    flash(request, exc.detail, MessageCategory.ERROR)   
    return RedirectResponse(url=request.url.path, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception(request: Request, exc: RequestValidationError):
    """Validation exception handler"""

    errors = [
        f"{error['type'].capitalize()} {error['loc'][0]}: {error['loc'][1]}- {error['msg'].split(',')[-1].strip()}"
        for error in exc.errors()
    ]

    exc_type, exc_obj, exc_tb = sys.exc_info()
    logger.error(f"RequestValidationError: {request.url.path} | {errors}", stacklevel=2)
    logger.error(f"[ERROR] - An error occured | {exc}\n{exc_type}\n{exc_obj}\nLine {exc_tb.tb_lineno}", stacklevel=2)    

    flash(request, 'Invalid input', MessageCategory.ERROR)
    return RedirectResponse(url=request.url.path, status_code=303)


@app.exception_handler(IntegrityError)
async def integrity_exception(request: Request, exc: IntegrityError):
    """Integrity error exception handlers"""

    exc_type, exc_obj, exc_tb = sys.exc_info()
    logger.error(f"Integrity error occured | {request.url.path} | 500", stacklevel=2)
    logger.error(f"[ERROR] - An error occured | {exc}\n{exc_type}\n{exc_obj}\nLine {exc_tb.tb_lineno}", stacklevel=2)
    
    if isinstance(exc.orig, UniqueViolation):
        constraint = getattr(exc.orig.diag, "constraint_name", None)
        
        flash(request, f"{constraint.split('_')[-1].capitalize()} with the provided value already exists", MessageCategory.ERROR)
        return RedirectResponse(url=request.url.path, status_code=303)
    
    flash(request, 'An unexpected error occurred', MessageCategory.ERROR)
    return RedirectResponse(url="/500", status_code=303)


@app.exception_handler(Exception)
async def exception(request: Request, exc: Exception):
    """Other exception handlers"""

    exc_type, exc_obj, exc_tb = sys.exc_info()
    logger.error(f"Exception occured | {request.url.path} | 500", stacklevel=2)
    logger.error(f"[ERROR] - An error occured | {exc}\n{exc_type}\n{exc_obj}\nLine {exc_tb.tb_lineno}", stacklevel=2)    

    flash(request, 'An unexpected error occurred', MessageCategory.ERROR)
    return RedirectResponse(url="/500", status_code=303)


if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host='0.0.0.0',
        port=find_free_port(
            port=config('PORT', cast=int, default=7001),
            is_production=config('PYTHON_ENV') == "production"
        ), 
        reload=True,
        workers=4,
        reload_excludes=['logs/']
    )
