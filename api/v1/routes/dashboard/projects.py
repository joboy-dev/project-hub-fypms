from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.models.user import User, UserRole
from api.v1.models.project import Project, ProjectStatus
from api.v1.models.project_member import ProjectMember, ProjectMemberRole
from api.v1.models.submission import Submission
from api.v1.models.milestone import Milestone
from api.v1.models.department import Department
from api.v1.models.document import Document
from api.v1.services.project import ProjectService
from api.v1.routes.dashboard.helpers import _get_user, _paginate


projects_router = APIRouter(prefix='/projects', tags=['Projects'])
logger = create_logger(__name__)


# ─── List ─────────────────────────────────────────────

@projects_router.get('')
@add_template_context('pages/dashboard/projects/index.html')
async def projects_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    page, size = _paginate(request, '/dashboard/projects')

    if user.role == UserRole.ADMIN.value:
        _, items, count = Project.all(db, page=page, per_page=size)
        response = paginator.build_paginated_response(
            items=[p.to_dict() for p in items],
            endpoint='/dashboard/projects', total=count, page=page, size=size,
        )
    elif user.role == UserRole.SUPERVISOR.value:
        items, count = ProjectService.get_supervisor_projects(db, user.id, page, size)
        response = paginator.build_paginated_response(
            items=[p.to_dict() for p in items],
            endpoint='/dashboard/projects', total=count, page=page, size=size,
        )
    else:
        items, count = ProjectService.get_student_projects(db, user.id, page, size)
        response = paginator.build_paginated_response(
            items=[p.to_dict() for p in items],
            endpoint='/dashboard/projects', total=count, page=page, size=size,
        )

    return {
        "page_title": "Projects",
        "page_description": "Manage your projects",
        "projects": response['data'],
        "pagination_data": response['pagination_data'],
    }


# ─── Create ───────────────────────────────────────────

@projects_router.get('/new')
@add_template_context('pages/dashboard/projects/create.html')
async def project_create_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    departments = db.query(Department).filter(Department.is_deleted == False).all()
    supervisors = db.query(User).filter(
        User.role == UserRole.SUPERVISOR.value, User.is_deleted == False,
    ).all()

    return {
        "page_title": "New Project",
        "page_description": "Create a new project",
        "departments": departments,
        "supervisors": supervisors,
    }


@projects_router.post('/new')
async def project_create(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        project = ProjectService.create_project(
            db=db,
            title=payload.get('title', '').strip(),
            description=payload.get('description', '').strip(),
            owner_id=user.id,
            department_id=payload.get('department_id') or None,
        )
        supervisor_id = payload.get('supervisor_id')
        if supervisor_id:
            ProjectService.assign_supervisor(db, project.id, supervisor_id)

        flash(request, 'Project created successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url=f"/dashboard/projects/{project.id}", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url="/dashboard/projects/new", status_code=303)


# ─── Detail ───────────────────────────────────────────

@projects_router.get('/{project_id}')
@add_template_context('pages/dashboard/projects/detail.html')
async def project_detail(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    project = Project.fetch_by_id(db, project_id)

    # Members with user details
    members_raw = db.query(ProjectMember, User).join(
        User, ProjectMember.user_id == User.id
    ).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.is_deleted == False,
    ).all()
    members = [{"member": pm.to_dict(), "user": u.to_dict()} for pm, u in members_raw]

    is_owner = any(
        pm.user_id == user.id and pm.role == ProjectMemberRole.OWNER.value
        for pm, _ in members_raw
    )

    is_member = any(pm.user_id == user.id for pm, _ in members_raw)

    # Build invite URL
    base_url = str(request.base_url).rstrip('/')
    invite_url = f"{base_url}/invite/{project.invite_code}" if project.invite_code else ""

    # Supervisor details
    supervisor = None
    if project.supervisor_id:
        supervisor = User.fetch_by_id(db, project.supervisor_id)

    # Milestones
    milestones = db.query(Milestone).filter(
        Milestone.project_id == project_id, Milestone.is_deleted == False,
    ).order_by(Milestone.due_date).all()

    # Recent submissions
    submissions = db.query(Submission).filter(
        Submission.project_id == project_id, Submission.is_deleted == False,
    ).order_by(Submission.created_at.desc()).limit(10).all()

    # Documents
    documents = db.query(Document).filter(
        Document.project_id == project_id, Document.is_deleted == False,
    ).order_by(Document.created_at.desc()).all()

    # Status choices for dropdown
    status_choices = [s.value for s in ProjectStatus]

    return {
        "page_title": project.title,
        "page_description": "Project details",
        "project": project.to_dict(),
        "members": members,
        "is_owner": is_owner,
        "is_member": is_member,
        "invite_url": invite_url,
        "supervisor": supervisor.to_dict() if supervisor else None,
        "milestones": [m.to_dict() for m in milestones],
        "submissions": [s.to_dict() for s in submissions],
        "documents": [d.to_dict() for d in documents],
        "status_choices": status_choices,
    }


# ─── Edit ─────────────────────────────────────────────

@projects_router.get('/{project_id}/edit')
@add_template_context('pages/dashboard/projects/edit.html')
async def project_edit_page(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    project = Project.fetch_by_id(db, project_id)

    departments = db.query(Department).filter(Department.is_deleted == False).all()
    supervisors = db.query(User).filter(
        User.role == UserRole.SUPERVISOR.value, User.is_deleted == False,
    ).all()
    status_choices = [s.value for s in ProjectStatus]

    return {
        "page_title": f"Edit: {project.title}",
        "page_description": "Edit project details",
        "project": project.to_dict(),
        "departments": departments,
        "supervisors": supervisors,
        "status_choices": status_choices,
    }


@projects_router.post('/{project_id}/edit')
async def project_edit(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        update_data = {}

        title = payload.get('title', '').strip()
        if title:
            update_data['title'] = title

        description = payload.get('description', '').strip()
        if description is not None:
            update_data['description'] = description

        department_id = payload.get('department_id')
        update_data['department_id'] = department_id or None

        status = payload.get('status')
        if status and status in [s.value for s in ProjectStatus]:
            update_data['status'] = status

        Project.update(db, project_id, **update_data)

        supervisor_id = payload.get('supervisor_id')
        if supervisor_id:
            ProjectService.assign_supervisor(db, project_id, supervisor_id)

        flash(request, 'Project updated successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/projects/{project_id}/edit", status_code=303)


# ─── Update Status ────────────────────────────────────

@projects_router.post('/{project_id}/status')
async def project_update_status(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        status = payload.get('status', '').strip()
        if status not in [s.value for s in ProjectStatus]:
            raise HTTPException(400, "Invalid status")

        ProjectService.update_status(db, project_id, status)
        flash(request, 'Project status updated', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Delete ───────────────────────────────────────────

@projects_router.post('/{project_id}/delete')
async def project_delete(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        # Only owner or admin can delete
        if user.role != UserRole.ADMIN.value:
            member = ProjectMember.fetch_one_by_field(
                db, throw_error=False, project_id=project_id, user_id=user.id
            )
            if not member or member.role != ProjectMemberRole.OWNER.value:
                raise HTTPException(403, "Only the project owner or admin can delete this project")

        Project.soft_delete(db, project_id)
        flash(request, 'Project deleted successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url="/dashboard/projects", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Regenerate Invite ────────────────────────────────

@projects_router.post('/{project_id}/regenerate-invite')
async def regenerate_invite(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        ProjectService.regenerate_invite_code(db, project_id, user.id)
        flash(request, 'Invite link regenerated. The old link no longer works.', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Remove Member ────────────────────────────────────

@projects_router.post('/{project_id}/members/{member_user_id}/remove')
async def remove_member(request: Request, project_id: str, member_user_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        # Only owner or admin
        if user.role != UserRole.ADMIN.value:
            member = ProjectMember.fetch_one_by_field(
                db, throw_error=False, project_id=project_id, user_id=user.id
            )
            if not member or member.role != ProjectMemberRole.OWNER.value:
                raise HTTPException(403, "Only the project owner can remove members")

        ProjectService.remove_member(db, project_id, member_user_id)
        flash(request, 'Member removed successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)
