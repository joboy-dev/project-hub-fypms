from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.models.notification import Notification, NotificationType
from api.v1.services.notification import NotificationService
from api.v1.routes.dashboard.helpers import _get_user, _paginate


notifications_router = APIRouter(prefix='/notifications', tags=['Notifications'])
logger = create_logger(__name__)


# ─── Notification Type Metadata ───────────────────────

NOTIFICATION_TYPE_META = {
    NotificationType.SUBMISSION.value: {'icon': 'fa-file-arrow-up', 'color': 'primary', 'label': 'Submission'},
    NotificationType.FEEDBACK.value: {'icon': 'fa-comment-dots', 'color': 'gold', 'label': 'Feedback'},
    NotificationType.MESSAGE.value: {'icon': 'fa-envelope', 'color': 'accent-success', 'label': 'Message'},
    NotificationType.MILESTONE.value: {'icon': 'fa-flag-checkered', 'color': 'purple-600', 'label': 'Milestone'},
    NotificationType.PROJECT_UPDATE.value: {'icon': 'fa-folder-open', 'color': 'primary-700', 'label': 'Project'},
    NotificationType.SYSTEM.value: {'icon': 'fa-bell', 'color': 'secondary', 'label': 'System'},
}


# ─── List ─────────────────────────────────────────────

@notifications_router.get('')
@add_template_context('pages/dashboard/notifications/index.html')
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    page, size = _paginate(request, '/dashboard/notifications')

    type_filter = request.query_params.get('type')
    read_filter = request.query_params.get('read')

    query = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_deleted == False,
    )

    if type_filter and type_filter != 'all':
        query = query.filter(Notification.type == type_filter)

    if read_filter == 'unread':
        query = query.filter(Notification.is_read == False)
    elif read_filter == 'read':
        query = query.filter(Notification.is_read == True)

    count = query.count()
    offset = (page - 1) * size
    notifications = query.order_by(Notification.created_at.desc()).offset(offset).limit(size).all()

    response = paginator.build_paginated_response(
        items=[n.to_dict() for n in notifications],
        endpoint='/dashboard/notifications', total=count, page=page, size=size,
    )

    unread_count = NotificationService.get_unread_count(db, user.id)

    return {
        "page_title": "Notifications",
        "page_description": f"{unread_count} unread notification{'s' if unread_count != 1 else ''}",
        "notifications": response['data'],
        "pagination_data": response['pagination_data'],
        "unread_count": unread_count,
        "type_filter": type_filter or 'all',
        "read_filter": read_filter or 'all',
        "notification_types": NOTIFICATION_TYPE_META,
    }


# ─── Mark Read ────────────────────────────────────────

@notifications_router.get('/{notification_id}/read')
async def notification_mark_read(request: Request, notification_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    notification = Notification.fetch_by_id(db, notification_id)
    if notification.user_id != user.id:
        flash(request, 'Notification not found.', MessageCategory.ERROR)
        return RedirectResponse(url='/dashboard/notifications', status_code=303)

    NotificationService.mark_as_read(db, notification_id, user.id)

    # If the notification has a link, redirect to it
    if notification.link:
        return RedirectResponse(url=notification.link, status_code=303)

    return RedirectResponse(url="/dashboard/notifications", status_code=303)


# ─── Mark All Read ────────────────────────────────────

@notifications_router.post('/read-all')
async def notifications_mark_all_read(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    count = NotificationService.mark_all_as_read(db, user.id)
    flash(request, f'Marked {count} notification{"s" if count != 1 else ""} as read', MessageCategory.SUCCESS)
    return RedirectResponse(url="/dashboard/notifications", status_code=303)


# ─── Unread Count API ─────────────────────────────────

@notifications_router.get('/unread-count')
async def notifications_unread_count(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    count = NotificationService.get_unread_count(db, user.id)
    return JSONResponse(content={"count": count})


# ─── Recent Notifications API (for bell dropdown) ─────

@notifications_router.get('/recent')
async def notifications_recent(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    notifications = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_deleted == False,
    ).order_by(Notification.created_at.desc()).limit(5).all()

    return JSONResponse(content={
        "notifications": [n.to_dict() for n in notifications],
        "unread_count": NotificationService.get_unread_count(db, user.id),
    }, headers={"Cache-Control": "no-store"})
