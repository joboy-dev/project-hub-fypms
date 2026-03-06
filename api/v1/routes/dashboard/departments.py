from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.models.user import UserRole
from api.v1.models.department import Department
from api.v1.services.user import UserService
from api.v1.routes.dashboard.helpers import _get_user, _paginate


departments_router = APIRouter(prefix='/departments', tags=['Departments'])
logger = create_logger(__name__)


# ─── List ─────────────────────────────────────────────

@departments_router.get('')
@add_template_context('pages/dashboard/departments/index.html')
async def departments_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    UserService.check_user_role(db, user.id, [UserRole.ADMIN.value])
    page, size = _paginate(request, '/dashboard/departments')

    _, items, count = Department.all(db, page=page, per_page=size)
    response = paginator.build_paginated_response(
        items=[d.to_dict() for d in items],
        endpoint='/dashboard/departments', total=count, page=page, size=size,
    )

    return {
        "page_title": "Departments",
        "page_description": "Manage departments",
        "departments": response['data'],
        "pagination_data": response['pagination_data'],
    }


# ─── Create ───────────────────────────────────────────

@departments_router.post('/new')
async def department_create(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    UserService.check_user_role(db, user.id, [UserRole.ADMIN.value])
    try:
        payload = await request.form()
        Department.create(
            db=db,
            name=payload.get('name', '').strip(),
            code=payload.get('code', '').strip().upper(),
            description=payload.get('description', '').strip(),
        )
        flash(request, 'Department created successfully', MessageCategory.SUCCESS)
    except Exception as e:
        flash(request, str(e), MessageCategory.ERROR)
    return RedirectResponse(url="/dashboard/departments", status_code=303)


# ─── Edit ─────────────────────────────────────────────

@departments_router.get('/{department_id}/edit')
@add_template_context('pages/dashboard/departments/edit.html')
async def department_edit_page(request: Request, department_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    UserService.check_user_role(db, user.id, [UserRole.ADMIN.value])

    department = Department.fetch_by_id(db, department_id)

    return {
        "page_title": f"Edit: {department.name}",
        "page_description": "Edit department details",
        "department": department.to_dict(),
    }


@departments_router.post('/{department_id}/edit')
async def department_edit(request: Request, department_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        UserService.check_user_role(db, user.id, [UserRole.ADMIN.value])

        payload = await request.form()
        update_data = {}

        name = payload.get('name', '').strip()
        if name:
            update_data['name'] = name

        code = payload.get('code', '').strip().upper()
        if code:
            update_data['code'] = code

        description = payload.get('description', '')
        update_data['description'] = description.strip()

        Department.update(db, department_id, **update_data)
        flash(request, 'Department updated successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url="/dashboard/departments", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/departments/{department_id}/edit", status_code=303)
    except Exception as e:
        flash(request, str(e), MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/departments/{department_id}/edit", status_code=303)


# ─── Delete ───────────────────────────────────────────

@departments_router.post('/{department_id}/delete')
async def department_delete(request: Request, department_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        UserService.check_user_role(db, user.id, [UserRole.ADMIN.value])
        Department.soft_delete(db, department_id)
        flash(request, 'Department deleted successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url="/dashboard/departments", status_code=303)
