from typing import List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from api.core.dependencies.email_sending_service import send_email
from api.utils.loggers import create_logger
from api.v1.models.notification import Notification, NotificationType
from api.v1.models.user import User


logger = create_logger(__name__)


class NotificationService:
    """Centralized notification service that creates in-app notifications
    and sends email notifications."""

    @classmethod
    def notify(
        cls,
        db: Session,
        bg_tasks: BackgroundTasks,
        user_id: str,
        title: str,
        content: str,
        notification_type: str = NotificationType.SYSTEM.value,
        link: Optional[str] = None,
        send_email_notification: bool = True,
    ) -> Notification:
        """Create an in-app notification and optionally send an email.

        Args:
            db: Database session.
            bg_tasks: FastAPI BackgroundTasks for async email sending.
            user_id: The user to notify.
            title: Short title for the notification (used as email subject too).
            content: Notification body text.
            notification_type: One of NotificationType enum values.
            link: Optional link the notification points to.
            send_email_notification: Whether to also send an email.

        Returns:
            The created Notification object.
        """
        # Create in-app notification
        notification = Notification.create(
            db=db,
            title=title,
            content=content,
            type=notification_type,
            user_id=user_id,
            link=link,
        )
        logger.info(f"Notification created for user {user_id}: {title}")

        # Send email notification
        if send_email_notification:
            try:
                user = User.fetch_one_by_field(db, throw_error=False, id=user_id)
                if user and user.email:
                    bg_tasks.add_task(
                        send_email,
                        recipients=[user.email],
                        subject=f"ProjectHub - {title}",
                        template_name="notification.html",
                        template_data={
                            "user_name": user.first_name,
                            "notification_title": title,
                            "notification_content": content,
                            "notification_type": notification_type,
                            "action_url": link,
                        },
                    )
                    logger.info(f"Email notification queued for {user.email}")
            except Exception as e:
                logger.error(f"Failed to queue email notification: {e}")

        return notification

    @classmethod
    def notify_many(
        cls,
        db: Session,
        bg_tasks: BackgroundTasks,
        user_ids: List[str],
        title: str,
        content: str,
        notification_type: str = NotificationType.SYSTEM.value,
        link: Optional[str] = None,
        send_email_notification: bool = True,
        exclude_user_id: Optional[str] = None,
    ) -> List[Notification]:
        """Send the same notification to multiple users.

        Args:
            db: Database session.
            bg_tasks: FastAPI BackgroundTasks.
            user_ids: List of user IDs to notify.
            title: Short title.
            content: Notification body.
            notification_type: Notification type.
            link: Optional action link.
            send_email_notification: Whether to also send emails.
            exclude_user_id: Optional user ID to exclude (e.g. the actor).

        Returns:
            List of created Notification objects.
        """
        notifications = []
        for uid in user_ids:
            if exclude_user_id and uid == exclude_user_id:
                continue
            notification = cls.notify(
                db=db,
                bg_tasks=bg_tasks,
                user_id=uid,
                title=title,
                content=content,
                notification_type=notification_type,
                link=link,
                send_email_notification=send_email_notification,
            )
            notifications.append(notification)
        return notifications

    @classmethod
    def get_unread_count(cls, db: Session, user_id: str) -> int:
        """Get the count of unread notifications for a user."""
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_deleted == False,
        ).count()

    @classmethod
    def mark_as_read(cls, db: Session, notification_id: str, user_id: str) -> None:
        """Mark a single notification as read."""
        notification = Notification.fetch_by_id(db, notification_id)
        if notification.user_id == user_id:
            Notification.update(db, notification_id, is_read=True)

    @classmethod
    def mark_all_as_read(cls, db: Session, user_id: str) -> int:
        """Mark all unread notifications as read for a user. Returns count updated."""
        count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_deleted == False,
        ).update({"is_read": True})
        db.commit()
        return count
