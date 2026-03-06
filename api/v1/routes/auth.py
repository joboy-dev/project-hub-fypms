from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from decouple import config

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.core.dependencies.form_builder import build_form
from api.db.database import get_db
from api.utils.settings import settings
from api.utils.loggers import create_logger
from api.utils.responses import success_response
from api.utils.telex_notification import TelexNotification
from api.v1.models.user import User, UserRole
from api.v1.services.auth import AuthService
from api.v1.services.user import UserService


auth_router = APIRouter(prefix='/auth', tags=['Auth'])
logger = create_logger(__name__)


def _pop_pending_invite(request: Request):
    """Check session for a pending invite code and return the redirect URL if found."""
    invite_code = request.session.pop('pending_invite_code', None)
    if invite_code:
        return f"/invite/{invite_code}"
    return None


def _set_auth_cookies(response: RedirectResponse, access_token: str, refresh_token: str):
    """Helper to set authentication cookies on a response."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        expires=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        httponly=True,
        secure=True,
        samesite="none",
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        expires=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        httponly=True,
        secure=True,
        samesite="none",
    )
    return response


def _handle_login(request: Request, db: Session, payload, role: str):
    """Handle login logic for any role."""
    user, access_token, refresh_token = AuthService.authenticate(
        db, 
        email=payload.get('email'), 
        password=payload.get('password')
    )
    
    # Verify user has the correct role
    if user.role != role:
        raise HTTPException(400, f"This account is not registered as a {role}. Please use the correct login page.")
    
    logger.info(f'User {user.email} ({role}) logged in successfully')
    flash(request, 'Logged in successfully', MessageCategory.SUCCESS)
    
    # Check for pending invite code
    redirect_url = _pop_pending_invite(request) or "/dashboard"
    
    response = RedirectResponse(url=redirect_url, status_code=303)
    return _set_auth_cookies(response, access_token, refresh_token)


def _handle_register(request: Request, db: Session, payload, bg_tasks: BackgroundTasks, role: str):
    """Handle registration logic for any role."""
    is_active = role == UserRole.ADMIN.value
    
    new_user, access_token, refresh_token = UserService.create(
        db=db,
        payload=payload,
        bg_tasks=bg_tasks,
        role=role,
        is_active=is_active,
        create_token=True
    )
    
    logger.info(f'User {new_user.email} ({role}) created successfully')
    flash(request, 'Account created successfully', MessageCategory.SUCCESS)
    
    # Check for pending invite code
    redirect_url = _pop_pending_invite(request) or "/dashboard"
    
    response = RedirectResponse(url=redirect_url, status_code=303)
    return _set_auth_cookies(response, access_token, refresh_token)


# ─── Student Auth ──────────────────────────────────────────────

@auth_router.api_route('/student', methods=["GET", "POST"])
@add_template_context('pages/auth/role_auth.html')
async def student_auth(
    request: Request,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Student authentication page with tabbed login/register."""
    
    context = {
        'role': UserRole.STUDENT.value,
        'role_label': 'Student',
        'role_icon': 'fa-graduation-cap',
        'action_url': '/auth/student',
    }
    
    if request.method == 'POST':
        payload = await request.form()
        action = payload.get('action', 'login')
        
        try:
            if action == 'register':
                return _handle_register(request, db, payload, bg_tasks, UserRole.STUDENT.value)
            else:
                return _handle_login(request, db, payload, UserRole.STUDENT.value)
        except HTTPException as e:
            flash(request, e.detail, MessageCategory.ERROR)
            context['form_data'] = dict(payload)
            context['active_tab'] = action
            return context
    
    return context


# ─── Supervisor Auth ───────────────────────────────────────────

@auth_router.api_route('/supervisor', methods=["GET", "POST"])
@add_template_context('pages/auth/role_auth.html')
async def supervisor_auth(
    request: Request,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Supervisor authentication page with tabbed login/register."""
    
    context = {
        'role': UserRole.SUPERVISOR.value,
        'role_label': 'Supervisor',
        'role_icon': 'fa-chalkboard-teacher',
        'action_url': '/auth/supervisor',
    }
    
    if request.method == 'POST':
        payload = await request.form()
        action = payload.get('action', 'login')
        
        try:
            if action == 'register':
                return _handle_register(request, db, payload, bg_tasks, UserRole.SUPERVISOR.value)
            else:
                return _handle_login(request, db, payload, UserRole.SUPERVISOR.value)
        except HTTPException as e:
            flash(request, e.detail, MessageCategory.ERROR)
            context['form_data'] = dict(payload)
            context['active_tab'] = action
            return context
    
    return context


# ─── Admin Auth ────────────────────────────────────────────────

@auth_router.api_route('/admin', methods=["GET", "POST"])
@add_template_context('pages/auth/role_auth.html')
async def admin_auth(
    request: Request,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Admin authentication page with tabbed login/register."""
    
    context = {
        'role': UserRole.ADMIN.value,
        'role_label': 'Administrator',
        'role_icon': 'fa-shield-halved',
        'action_url': '/auth/admin',
    }
    
    if request.method == 'POST':
        payload = await request.form()
        action = payload.get('action', 'login')
        
        try:
            if action == 'register':
                return _handle_register(request, db, payload, bg_tasks, UserRole.ADMIN.value)
            else:
                return _handle_login(request, db, payload, UserRole.ADMIN.value)
        except HTTPException as e:
            flash(request, e.detail, MessageCategory.ERROR)
            context['form_data'] = dict(payload)
            context['active_tab'] = action
            return context
    
    return context


# ─── Logout ────────────────────────────────────────────────────

@auth_router.post('/logout')
async def logout(request: Request, db: Session = Depends(get_db)):
    """Endpoint to log a user out."""
    
    current_user = request.state.current_user
    
    AuthService.logout(db, current_user.id)
    request.state.current_user = None
    
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie('refresh_token')
    response.delete_cookie('access_token')
    
    return response
