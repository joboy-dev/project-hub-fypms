from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.v1.models.user import UserRole
from api.v1.models.project import Project
from api.v1.models.project_member import ProjectMember, ProjectMemberRole
from api.v1.models.milestone import Milestone, MilestoneStatus
from api.v1.routes.dashboard.helpers import _get_user


milestones_router = APIRouter(prefix='/projects/{project_id}/milestones', tags=['Milestones'])
logger = create_logger(__name__)


def _can_manage_project(db, user, project_id):
    """Check if user can manage milestones for this project."""
    if user.role == UserRole.ADMIN.value:
        return True
    # Check if owner
    member = ProjectMember.fetch_one_by_field(
        db, throw_error=False, project_id=project_id, user_id=user.id
    )
    if member and member.role == ProjectMemberRole.OWNER.value:
        return True
    # Supervisor of this project
    project = Project.fetch_by_id(db, project_id)
    return project.supervisor_id == user.id


# ─── Create ───────────────────────────────────────────

@milestones_router.post('/new')
async def milestone_create(request: Request, project_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        if not _can_manage_project(db, user, project_id):
            raise HTTPException(403, "You don't have permission to add milestones")

        payload = await request.form()
        title = payload.get('title', '').strip()
        description = payload.get('description', '').strip()
        due_date = payload.get('due_date', '').strip()

        if not title or not due_date:
            raise HTTPException(400, "Title and due date are required")

        try:
            parsed_due_date = datetime.fromisoformat(due_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format")

        Milestone.create(
            db=db,
            title=title,
            description=description,
            due_date=parsed_due_date,
            project_id=project_id,
            status=MilestoneStatus.PENDING.value,
        )
        flash(request, 'Milestone created successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Update ───────────────────────────────────────────

@milestones_router.post('/{milestone_id}/edit')
async def milestone_edit(request: Request, project_id: str, milestone_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        if not _can_manage_project(db, user, project_id):
            raise HTTPException(403, "You don't have permission to edit milestones")

        payload = await request.form()
        update_data = {}

        title = payload.get('title', '').strip()
        if title:
            update_data['title'] = title

        description = payload.get('description', '')
        update_data['description'] = description.strip()

        due_date = payload.get('due_date', '').strip()
        if due_date:
            try:
                update_data['due_date'] = datetime.fromisoformat(due_date)
            except ValueError:
                raise HTTPException(400, "Invalid date format")

        status = payload.get('status', '').strip()
        if status and status in [s.value for s in MilestoneStatus]:
            update_data['status'] = status

        Milestone.update(db, milestone_id, **update_data)
        flash(request, 'Milestone updated successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Update Status ────────────────────────────────────

@milestones_router.post('/{milestone_id}/status')
async def milestone_update_status(request: Request, project_id: str, milestone_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        status = payload.get('status', '').strip()
        if status not in [s.value for s in MilestoneStatus]:
            raise HTTPException(400, "Invalid status")

        Milestone.update(db, milestone_id, status=status)
        flash(request, f'Milestone marked as {status.replace("_", " ").title()}', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Delete ───────────────────────────────────────────

@milestones_router.post('/{milestone_id}/delete')
async def milestone_delete(request: Request, project_id: str, milestone_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        if not _can_manage_project(db, user, project_id):
            raise HTTPException(403, "You don't have permission to delete milestones")

        Milestone.soft_delete(db, milestone_id)
        flash(request, 'Milestone deleted', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)
