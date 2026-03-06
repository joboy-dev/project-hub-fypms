from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.v1.models.user import User, UserRole
from api.v1.models.submission import Submission
from api.v1.models.feedback import Feedback
from api.v1.models.notification import NotificationType
from api.v1.services.notification import NotificationService
from api.v1.routes.dashboard.helpers import _get_user


feedback_router = APIRouter(prefix='/submissions/{submission_id}/feedback', tags=['Feedback'])
logger = create_logger(__name__)


# ─── Create ───────────────────────────────────────────

@feedback_router.post('/new')
async def feedback_create(request: Request, submission_id: str, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        if user.role not in [UserRole.SUPERVISOR.value, UserRole.ADMIN.value]:
            raise HTTPException(403, "Only supervisors and admins can give feedback")

        submission = Submission.fetch_by_id(db, submission_id)
        payload = await request.form()
        content = payload.get('content', '').strip()
        grade = payload.get('grade', '').strip() or None

        if not content:
            raise HTTPException(400, "Feedback content is required")

        Feedback.create(
            db=db,
            content=content,
            grade=grade,
            submission_id=submission_id,
            project_id=submission.project_id,
            given_by=user.id,
        )

        # Notify the submitter about new feedback
        NotificationService.notify(
            db=db, bg_tasks=bg_tasks, user_id=submission.submitted_by,
            title="New Feedback Received",
            content=f"{user.full_name} gave feedback on your submission \"{submission.title}\"{(' — Grade: ' + grade) if grade else ''}.",
            notification_type=NotificationType.FEEDBACK.value,
            link=f"/dashboard/submissions/{submission_id}",
        )

        flash(request, 'Feedback submitted successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/submissions/{submission_id}", status_code=303)


# ─── Edit ─────────────────────────────────────────────

@feedback_router.post('/{feedback_id}/edit')
async def feedback_edit(request: Request, submission_id: str, feedback_id: str, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        feedback = Feedback.fetch_by_id(db, feedback_id)
        if feedback.given_by != user.id and user.role != UserRole.ADMIN.value:
            raise HTTPException(403, "You can only edit your own feedback")

        payload = await request.form()
        update_data = {}

        content = payload.get('content', '').strip()
        if content:
            update_data['content'] = content

        grade = payload.get('grade', '').strip()
        update_data['grade'] = grade or None

        Feedback.update(db, feedback_id, **update_data)

        # Notify the submitter about updated feedback
        submission = Submission.fetch_by_id(db, submission_id)
        if submission.submitted_by != user.id:
            NotificationService.notify(
                db=db, bg_tasks=bg_tasks, user_id=submission.submitted_by,
                title="Feedback Updated",
                content=f"{user.full_name} updated their feedback on your submission \"{submission.title}\".",
                notification_type=NotificationType.FEEDBACK.value,
                link=f"/dashboard/submissions/{submission_id}",
            )

        flash(request, 'Feedback updated successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/submissions/{submission_id}", status_code=303)


# ─── Delete ───────────────────────────────────────────

@feedback_router.post('/{feedback_id}/delete')
async def feedback_delete(request: Request, submission_id: str, feedback_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        feedback = Feedback.fetch_by_id(db, feedback_id)
        if feedback.given_by != user.id and user.role != UserRole.ADMIN.value:
            raise HTTPException(403, "You can only delete your own feedback")

        Feedback.soft_delete(db, feedback_id)
        flash(request, 'Feedback deleted', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/submissions/{submission_id}", status_code=303)
