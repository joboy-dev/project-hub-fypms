from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.v1.models.project_member import ProjectMember, ProjectMemberRole
from api.v1.models.notification import NotificationType
from api.v1.services.project import ProjectService
from api.v1.services.notification import NotificationService


external_router = APIRouter(tags=["External"])
logger = create_logger(__name__)

@external_router.get("/")
@add_template_context('pages/index.html')
async def index(request: Request) -> dict:
    return {}


# ─── Project Invite Link ──────────────────────────────────────

@external_router.get("/invite/{invite_code}")
async def join_project_via_invite(
    request: Request,
    invite_code: str,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Public invite link endpoint.
    - If the user is logged in → add them to the project immediately.
    - If not logged in → store the invite code in session and redirect to login.
    """
    user = getattr(request.state, 'current_user', None)

    if not user:
        # Store invite code in session so we can process it after login
        request.session['pending_invite_code'] = invite_code
        flash(request, 'Please log in to join the project.', MessageCategory.INFO)
        return RedirectResponse(url='/auth?role=student', status_code=303)

    try:
        project, message = ProjectService.join_via_invite(db, invite_code, user.id)

        # Notify project owner that someone joined
        owner_member = ProjectMember.fetch_one_by_field(
            db, throw_error=False, project_id=project.id, role=ProjectMemberRole.OWNER.value
        )
        notify_ids = []
        if owner_member and owner_member.user_id != user.id:
            notify_ids.append(owner_member.user_id)
        if project.supervisor_id and project.supervisor_id != user.id:
            notify_ids.append(project.supervisor_id)
        if notify_ids:
            NotificationService.notify_many(
                db=db, bg_tasks=bg_tasks, user_ids=notify_ids,
                title="New Member Joined",
                content=f"{user.full_name} joined the project \"{project.title}\" via invite link.",
                notification_type=NotificationType.PROJECT_UPDATE.value,
                link=f"/dashboard/projects/{project.id}",
            )

        flash(request, message, MessageCategory.SUCCESS)
        return RedirectResponse(url=f'/dashboard/projects/{project.id}', status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url='/dashboard/projects', status_code=303)