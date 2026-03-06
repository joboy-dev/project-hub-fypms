from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.v1.models.user import User
from api.v1.services.user import UserService
from api.v1.services.auth import AuthService
from api.v1.routes.dashboard.helpers import _get_user


settings_router = APIRouter(prefix='/settings', tags=['Settings'])
logger = create_logger(__name__)


@settings_router.get('')
@add_template_context('pages/dashboard/settings/index.html')
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    return {
        "page_title": "Settings",
        "page_description": "Manage your account",
        "profile": user.to_dict(),
    }


@settings_router.post('/profile')
async def update_profile(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        User.update(
            db, user.id,
            first_name=payload.get('first_name', user.first_name).strip(),
            last_name=payload.get('last_name', user.last_name).strip(),
        )
        flash(request, 'Profile updated successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url="/dashboard/settings", status_code=303)


@settings_router.post('/password')
async def change_password(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        old_password = payload.get('old_password', '')
        new_password = payload.get('new_password', '')
        confirm_password = payload.get('confirm_password', '')

        if new_password != confirm_password:
            raise HTTPException(400, 'New passwords do not match')

        password_hash = UserService.verify_password_change(db, user.email, old_password, new_password)
        User.update(db, user.id, password=password_hash)
        flash(request, 'Password changed successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url="/dashboard/settings", status_code=303)
