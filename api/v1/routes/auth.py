from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils.settings import settings
from api.utils.loggers import create_logger
from api.v1.models.user import User, UserRole
from api.v1.services.auth import AuthService
from api.v1.services.user import UserService


auth_router = APIRouter(prefix='/auth', tags=['Auth'])
logger = create_logger(__name__)

ROLE_META = {
    UserRole.STUDENT.value: {
        'label': 'Student',
        'icon': 'fa-graduation-cap',
    },
    UserRole.SUPERVISOR.value: {
        'label': 'Supervisor',
        'icon': 'fa-chalkboard-teacher',
    },
    UserRole.ADMIN.value: {
        'label': 'Administrator',
        'icon': 'fa-shield-halved',
    },
}


def _pop_pending_invite(request: Request):
    """Check session for a pending invite code and return the redirect URL if found."""
    invite_code = request.session.pop('pending_invite_code', None)
    if invite_code:
        return f"/invite/{invite_code}"
    return None


def _set_auth_cookies(
    response: RedirectResponse,
    access_token: str,
    refresh_token: str,
    remember_me: bool = False,
):
    """Helper to set authentication cookies on a response."""
    access_expiry = timedelta(days=30) if remember_me else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expiry = timedelta(days=45) if remember_me else timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        expires=refresh_expiry,
        httponly=True,
        secure=True,
        samesite="none",
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        expires=access_expiry,
        httponly=True,
        secure=True,
        samesite="none",
    )
    return response


def _handle_login(request: Request, db: Session, payload, role: str):
    """Handle login logic for any role."""
    remember_me = str(payload.get('remember_me', '')).lower() in {'on', 'true', '1', 'yes'}

    user, _, _ = AuthService.authenticate(
        db, 
        email=payload.get('email'), 
        password=payload.get('password'),
        create_token=False,
    )
    
    # Verify user has the correct role
    if user.role != role:
        raise HTTPException(400, f"This account is not registered as a {role}. Please use the correct login page.")
    
    logger.info(f'User {user.email} ({role}) logged in successfully')
    flash(request, 'Logged in successfully', MessageCategory.SUCCESS)

    access_expiry_minutes = (30 * 24 * 60) if remember_me else None
    refresh_expiry_minutes = (45 * 24 * 60) if remember_me else None
    access_token = AuthService.create_access_token(db, user.id, expiry_in_minutes=access_expiry_minutes)
    refresh_token = AuthService.create_refresh_token(db, user.id, expiry_in_minutes=refresh_expiry_minutes)
    
    # Check for pending invite code
    redirect_url = _pop_pending_invite(request) or "/dashboard"
    
    response = RedirectResponse(url=redirect_url, status_code=303)
    return _set_auth_cookies(response, access_token, refresh_token, remember_me=remember_me)


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


def _resolve_role(request: Request) -> str:
    role = (request.query_params.get('role') or '').strip().lower()
    if role not in ROLE_META:
        return UserRole.STUDENT.value
    return role


@auth_router.api_route('', methods=["GET", "POST"])
@add_template_context('pages/auth/role_auth.html')
async def auth_portal(
    request: Request,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Single RBAC auth page for student, supervisor and admin."""
    role = _resolve_role(request)
    mode = request.query_params.get('mode', 'login').strip().lower()
    mode = mode if mode in {'login', 'register'} else 'login'

    context = {
        'role': role,
        'role_label': ROLE_META[role]['label'],
        'role_icon': ROLE_META[role]['icon'],
        'action_url': f'/auth?role={role}&mode={mode}',
        'active_mode': mode,
    }

    if request.method == 'POST':
        payload = await request.form()
        action = (payload.get('action') or mode).strip().lower()

        try:
            if action == 'forgot_password':
                email = (payload.get('email') or '').strip().lower()
                if not email:
                    raise HTTPException(400, 'Please provide your account email address.')

                user = User.fetch_one_by_field(db, throw_error=False, email=email)
                if user:
                    await AuthService.send_password_reset_link(db, email, bg_tasks)

                flash(request, 'If this email exists, password reset instructions have been initiated.', MessageCategory.INFO)
                return RedirectResponse(url=f'/auth?role={role}&mode=login', status_code=303)

            if action == 'register':
                return _handle_register(request, db, payload, bg_tasks, role)
            return _handle_login(request, db, payload, role)
        except HTTPException as e:
            flash(request, e.detail, MessageCategory.ERROR)
            redirect_mode = 'register' if action == 'register' else 'login'
            return RedirectResponse(url=f'/auth?role={role}&mode={redirect_mode}', status_code=303)

    return context


@auth_router.api_route('/student', methods=['GET', 'POST'])
async def student_auth():
    return RedirectResponse(url='/auth?role=student', status_code=303)


@auth_router.api_route('/supervisor', methods=['GET', 'POST'])
async def supervisor_auth():
    return RedirectResponse(url='/auth?role=supervisor', status_code=303)


@auth_router.api_route('/admin', methods=['GET', 'POST'])
async def admin_auth():
    return RedirectResponse(url='/auth?role=admin', status_code=303)


@auth_router.post('/forgot-password')
async def forgot_password(
    request: Request,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = await request.form()
    email = (payload.get('email') or '').strip().lower()
    role = (payload.get('role') or UserRole.STUDENT.value).strip().lower()

    if not email:
        flash(request, 'Please provide your account email address.', MessageCategory.ERROR)
        return RedirectResponse(url=f'/auth?role={role}&mode=login', status_code=303)

    user = User.fetch_one_by_field(db, throw_error=False, email=email)
    if user:
        await AuthService.send_password_reset_link(db, email, bg_tasks)

    flash(request, 'If this email exists, password reset instructions have been initiated.', MessageCategory.INFO)
    return RedirectResponse(url=f'/auth?role={role}&mode=login', status_code=303)


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
