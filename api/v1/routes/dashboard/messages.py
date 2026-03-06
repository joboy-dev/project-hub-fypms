from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.models.user import User
from api.v1.models.message import Message
from api.v1.models.notification import NotificationType
from api.v1.services.notification import NotificationService
from api.v1.routes.dashboard.helpers import _get_user


messages_router = APIRouter(prefix='/messages', tags=['Messages'])
logger = create_logger(__name__)


@messages_router.get('')
@add_template_context('pages/dashboard/messages/index.html')
async def messages_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)

    sent = db.query(Message.receiver_id).filter(
        Message.sender_id == user.id, Message.is_deleted == False,
    ).distinct().all()
    received = db.query(Message.sender_id).filter(
        Message.receiver_id == user.id, Message.is_deleted == False,
    ).distinct().all()
    contact_ids = list(set([r[0] for r in sent] + [r[0] for r in received]))

    contacts = []
    for cid in contact_ids:
        contact_user = User.fetch_one_by_field(db, throw_error=False, id=cid)
        if not contact_user:
            continue
        last_msg = db.query(Message).filter(
            Message.is_deleted == False,
            ((Message.sender_id == user.id) & (Message.receiver_id == cid)) |
            ((Message.sender_id == cid) & (Message.receiver_id == user.id))
        ).order_by(Message.created_at.desc()).first()
        unread = db.query(Message).filter(
            Message.sender_id == cid,
            Message.receiver_id == user.id,
            Message.is_read == False,
            Message.is_deleted == False,
        ).count()
        contacts.append({
            "user": contact_user.to_dict(),
            "last_message": last_msg.to_dict() if last_msg else None,
            "unread_count": unread,
        })

    contacts.sort(key=lambda c: c['last_message']['created_at'] if c['last_message'] else '', reverse=True)

    return {
        "page_title": "Messages",
        "page_description": "Your conversations",
        "contacts": contacts,
    }


@messages_router.get('/new')
@add_template_context('pages/dashboard/messages/new.html')
async def new_message_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)

    # Get all users except self
    users = db.query(User).filter(
        User.id != user.id,
        User.is_deleted == False,
        User.is_active == True,
    ).order_by(User.first_name).all()

    return {
        "page_title": "New Message",
        "page_description": "Start a new conversation",
        "users": users,
    }


@messages_router.get('/{contact_id}')
@add_template_context('pages/dashboard/messages/conversation.html')
async def message_conversation(request: Request, contact_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    page = int(request.query_params.get('page', 1))
    size = 30

    contact = User.fetch_by_id(db, contact_id)

    query = db.query(Message).filter(
        Message.is_deleted == False,
        ((Message.sender_id == user.id) & (Message.receiver_id == contact_id)) |
        ((Message.sender_id == contact_id) & (Message.receiver_id == user.id))
    ).order_by(Message.created_at.desc())

    count = query.count()
    offset = (page - 1) * size
    messages = query.offset(offset).limit(size).all()
    messages.reverse()

    # Mark as read
    db.query(Message).filter(
        Message.sender_id == contact_id,
        Message.receiver_id == user.id,
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()

    pagination = paginator.build_paginated_response(
        items=[], endpoint=f'/dashboard/messages/{contact_id}',
        total=count, page=page, size=size,
    )

    return {
        "page_title": f"{contact.first_name} {contact.last_name}",
        "page_description": "Conversation",
        "contact": contact.to_dict(),
        "messages": [m.to_dict() for m in messages],
        "pagination_data": pagination['pagination_data'],
    }


@messages_router.post('/{contact_id}')
async def send_message(request: Request, contact_id: str, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = _get_user(request)
    payload = await request.form()
    content = payload.get('content', '').strip()
    if not content:
        flash(request, 'Message cannot be empty', MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/messages/{contact_id}", status_code=303)

    Message.create(
        db=db,
        content=content,
        sender_id=user.id,
        receiver_id=contact_id,
        project_id=payload.get('project_id') or None,
    )

    # Notify the receiver
    preview = content[:80] + ('...' if len(content) > 80 else '')
    NotificationService.notify(
        db=db, bg_tasks=bg_tasks, user_id=contact_id,
        title="New Message",
        content=f"{user.full_name} sent you a message: \"{preview}\"",
        notification_type=NotificationType.MESSAGE.value,
        link=f"/dashboard/messages/{user.id}",
        send_email_notification=False,  # Messages are frequent, skip email
    )

    return RedirectResponse(url=f"/dashboard/messages/{contact_id}", status_code=303)


@messages_router.post('/{contact_id}/delete/{message_id}')
async def delete_message(request: Request, contact_id: str, message_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        message = Message.fetch_by_id(db, message_id)
        if message.sender_id != user.id:
            flash(request, 'You can only delete your own messages', MessageCategory.ERROR)
        else:
            Message.soft_delete(db, message_id)
            flash(request, 'Message deleted', MessageCategory.SUCCESS)
    except Exception as e:
        flash(request, str(e), MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/messages/{contact_id}", status_code=303)
