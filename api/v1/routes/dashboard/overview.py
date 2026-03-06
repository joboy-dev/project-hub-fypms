from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.v1.models.user import UserRole
from api.v1.models.notification import Notification
from api.v1.services.dashboard import DashboardService
from api.v1.routes.dashboard.helpers import _get_user


overview_router = APIRouter(tags=['Dashboard Overview'])
logger = create_logger(__name__)


@overview_router.get('/')
@add_template_context('pages/dashboard/index.html')
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)

    if user.role == UserRole.ADMIN.value:
        stats = DashboardService.admin_stats(db)
    elif user.role == UserRole.SUPERVISOR.value:
        stats = DashboardService.supervisor_stats(db, user.id)
    else:
        stats = DashboardService.student_stats(db, user.id)

    unread_notifications_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
        Notification.is_deleted == False,
    ).count()

    return {
        "page_title": "Dashboard",
        "page_description": f"Welcome back, {user.first_name}",
        "stats": stats,
        "unread_notifications_count": unread_notifications_count,
    }
