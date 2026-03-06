from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.models.user import User, UserRole
from api.v1.models.department import Department
from api.v1.models.project import Project
from api.v1.models.project_member import ProjectMember
from api.v1.models.notification import NotificationType
from api.v1.services.user import UserService
from api.v1.services.notification import NotificationService
from api.v1.routes.dashboard.helpers import _get_user, _paginate


users_router = APIRouter(prefix='/users', tags=['Users Management'])
logger = create_logger(__name__)


# ─── List ─────────────────────────────────────────────

@users_router.get('')
@add_template_context('pages/dashboard/users/index.html')
async def users_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    UserService.check_user_role(db, user.id, [UserRole.ADMIN.value])
    page, size = _paginate(request, '/dashboard/users')

    role_filter = request.query_params.get('role')
    search_query = request.query_params.get('q')

    filters = {}
    search_fields = {}
    if role_filter and role_filter != 'all':
        filters['role'] = role_filter
    if search_query:
        search_fields = {'first_name': search_query, 'last_name': search_query, 'email': search_query}

    if search_fields:
        _, items, count = User.fetch_by_field(
            db, page=page, per_page=size,
            search_fields=search_fields,
            **(filters if filters else {}),
        )
    elif filters:
        _, items, count = User.fetch_by_field(
            db, page=page, per_page=size, **filters,
        )
    else:
        _, items, count = User.all(db, page=page, per_page=size)

    response = paginator.build_paginated_response(
        items=[u.to_dict() for u in items],
        endpoint='/dashboard/users', total=count, page=page, size=size,
    )

    return {
        "page_title": "Users",
        "page_description": "Manage all users",
        "users": response['data'],
        "pagination_data": response['pagination_data'],
        "role_filter": role_filter or 'all',
        "search_query": search_query or '',
    }


# ─── Detail ───────────────────────────────────────────

@users_router.get('/{user_id}')
@add_template_context('pages/dashboard/users/detail.html')
async def user_detail(request: Request, user_id: str, db: Session = Depends(get_db)):
    current_user = _get_user(request)
    UserService.check_user_role(db, current_user.id, [UserRole.ADMIN.value])

    target_user = User.fetch_by_id(db, user_id)
    department = None
    if target_user.department_id:
        department = Department.fetch_one_by_field(db, throw_error=False, id=target_user.department_id)

    # Get user's projects
    member_records = db.query(ProjectMember).filter(
        ProjectMember.user_id == user_id, ProjectMember.is_deleted == False,
    ).all()
    project_ids = [m.project_id for m in member_records]
    projects = db.query(Project).filter(
        Project.id.in_(project_ids), Project.is_deleted == False,
    ).all() if project_ids else []

    return {
        "page_title": f"{target_user.first_name} {target_user.last_name}",
        "page_description": "User details",
        "target_user": target_user.to_dict(),
        "department": department.to_dict() if department else None,
        "projects": [p.to_dict() for p in projects],
    }


# ─── Edit ─────────────────────────────────────────────

@users_router.get('/{user_id}/edit')
@add_template_context('pages/dashboard/users/edit.html')
async def user_edit_page(request: Request, user_id: str, db: Session = Depends(get_db)):
    current_user = _get_user(request)
    UserService.check_user_role(db, current_user.id, [UserRole.ADMIN.value])

    target_user = User.fetch_by_id(db, user_id)
    departments = db.query(Department).filter(Department.is_deleted == False).all()
    role_choices = [r.value for r in UserRole]

    return {
        "page_title": f"Edit: {target_user.first_name} {target_user.last_name}",
        "page_description": "Edit user details",
        "target_user": target_user.to_dict(),
        "departments": departments,
        "role_choices": role_choices,
    }


@users_router.post('/{user_id}/edit')
async def user_edit(request: Request, user_id: str, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    current_user = _get_user(request)
    try:
        UserService.check_user_role(db, current_user.id, [UserRole.ADMIN.value])

        target_user = User.fetch_by_id(db, user_id)
        payload = await request.form()
        update_data = {}

        first_name = payload.get('first_name', '').strip()
        if first_name:
            update_data['first_name'] = first_name

        last_name = payload.get('last_name', '').strip()
        if last_name:
            update_data['last_name'] = last_name

        role = payload.get('role', '').strip()
        if role and role in [r.value for r in UserRole]:
            update_data['role'] = role

        department_id = payload.get('department_id')
        update_data['department_id'] = department_id or None

        is_active = payload.get('is_active')
        update_data['is_active'] = is_active == 'on' or is_active == 'true'

        # Check what changed for notifications
        role_changed = role and role != target_user.role
        active_changed = update_data['is_active'] != target_user.is_active

        User.update(db, user_id, **update_data)

        # Notify user about account changes
        if role_changed:
            NotificationService.notify(
                db=db, bg_tasks=bg_tasks, user_id=user_id,
                title="Account Role Updated",
                content=f"Your account role has been changed to {role.title()} by an administrator.",
                notification_type=NotificationType.SYSTEM.value,
                link="/dashboard/settings",
            )
        if active_changed:
            status_word = "activated" if update_data['is_active'] else "deactivated"
            NotificationService.notify(
                db=db, bg_tasks=bg_tasks, user_id=user_id,
                title=f"Account {status_word.title()}",
                content=f"Your account has been {status_word} by an administrator.",
                notification_type=NotificationType.SYSTEM.value,
                link="/dashboard",
            )

        flash(request, 'User updated successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url=f"/dashboard/users/{user_id}", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/users/{user_id}/edit", status_code=303)


# ─── Toggle Active ────────────────────────────────────

@users_router.post('/{user_id}/toggle-active')
async def user_toggle_active(request: Request, user_id: str, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    current_user = _get_user(request)
    try:
        UserService.check_user_role(db, current_user.id, [UserRole.ADMIN.value])
        target_user = User.fetch_by_id(db, user_id)
        User.update(db, user_id, is_active=not target_user.is_active)
        status = "activated" if not target_user.is_active else "deactivated"

        # Notify the user about account status change
        NotificationService.notify(
            db=db, bg_tasks=bg_tasks, user_id=user_id,
            title=f"Account {status.title()}",
            content=f"Your account has been {status} by an administrator.",
            notification_type=NotificationType.SYSTEM.value,
            link="/dashboard",
        )

        flash(request, f'User {status} successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/users/{user_id}", status_code=303)


# ─── Delete ───────────────────────────────────────────

@users_router.post('/{user_id}/delete')
async def user_delete(request: Request, user_id: str, db: Session = Depends(get_db)):
    current_user = _get_user(request)
    try:
        UserService.check_user_role(db, current_user.id, [UserRole.ADMIN.value])

        if user_id == current_user.id:
            raise HTTPException(400, "You cannot delete your own account")

        User.soft_delete(db, user_id)
        flash(request, 'User deleted successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url="/dashboard/users", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/users/{user_id}", status_code=303)
