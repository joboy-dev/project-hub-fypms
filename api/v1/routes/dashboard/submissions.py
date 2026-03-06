from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.models.user import User, UserRole
from api.v1.models.project import Project
from api.v1.models.project_member import ProjectMember
from api.v1.models.submission import Submission, SubmissionStatus
from api.v1.models.milestone import Milestone
from api.v1.models.document import Document
from api.v1.models.feedback import Feedback
from api.v1.services.project import ProjectService
from api.utils.firebase_service import FirebaseService
from api.v1.routes.dashboard.helpers import _get_user, _paginate


submissions_router = APIRouter(prefix='/submissions', tags=['Submissions'])
logger = create_logger(__name__)


# ─── List ─────────────────────────────────────────────

@submissions_router.get('')
@add_template_context('pages/dashboard/submissions/index.html')
async def submissions_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    page, size = _paginate(request, '/dashboard/submissions')

    if user.role == UserRole.ADMIN.value:
        _, items, count = Submission.all(db, page=page, per_page=size)
        response = paginator.build_paginated_response(
            items=[s.to_dict() for s in items],
            endpoint='/dashboard/submissions', total=count, page=page, size=size,
        )
    elif user.role == UserRole.SUPERVISOR.value:
        project_ids = [
            p.id for p in db.query(Project.id).filter(
                Project.supervisor_id == user.id, Project.is_deleted == False,
            ).all()
        ]
        if project_ids:
            query = db.query(Submission).filter(
                Submission.project_id.in_(project_ids),
                Submission.is_deleted == False,
            ).order_by(Submission.created_at.desc())
            count = query.count()
            offset = (page - 1) * size
            items = query.offset(offset).limit(size).all()
        else:
            items, count = [], 0
        response = paginator.build_paginated_response(
            items=[s.to_dict() for s in items],
            endpoint='/dashboard/submissions', total=count, page=page, size=size,
        )
    else:
        _, items, count = Submission.fetch_by_field(
            db, page=page, per_page=size, submitted_by=user.id,
        )
        response = paginator.build_paginated_response(
            items=[s.to_dict() for s in items],
            endpoint='/dashboard/submissions', total=count, page=page, size=size,
        )

    # Map project titles and submitter names
    project_ids = list(set(s.get('project_id') for s in response['data'] if s.get('project_id')))
    submitter_ids = list(set(s.get('submitted_by') for s in response['data'] if s.get('submitted_by')))
    project_map = {}
    submitter_map = {}
    if project_ids:
        for p in db.query(Project).filter(Project.id.in_(project_ids)).all():
            project_map[p.id] = p.title
    if submitter_ids:
        for u in db.query(User).filter(User.id.in_(submitter_ids)).all():
            submitter_map[u.id] = f"{u.first_name} {u.last_name}"

    return {
        "page_title": "Submissions" if user.role != UserRole.SUPERVISOR.value else "Reviews",
        "page_description": "View and manage submissions",
        "submissions": response['data'],
        "pagination_data": response['pagination_data'],
        "project_map": project_map,
        "submitter_map": submitter_map,
    }


# ─── Create ───────────────────────────────────────────

@submissions_router.get('/new')
@add_template_context('pages/dashboard/submissions/create.html')
async def submission_create_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)

    # Get projects user is a member of
    if user.role == UserRole.ADMIN.value:
        projects = db.query(Project).filter(Project.is_deleted == False).all()
    else:
        member_records = db.query(ProjectMember).filter(
            ProjectMember.user_id == user.id, ProjectMember.is_deleted == False,
        ).all()
        project_ids = [m.project_id for m in member_records]
        projects = db.query(Project).filter(
            Project.id.in_(project_ids), Project.is_deleted == False,
        ).all() if project_ids else []

    # Pre-select project if passed in query
    selected_project = request.query_params.get('project_id', '')

    # Build per-project documents & milestones map for JS
    project_documents = {}
    project_milestones = {}
    for p in projects:
        docs = db.query(Document).filter(
            Document.project_id == p.id, Document.is_deleted == False,
        ).order_by(Document.created_at.desc()).all()
        project_documents[p.id] = [d.to_dict() for d in docs]

        mstones = db.query(Milestone).filter(
            Milestone.project_id == p.id, Milestone.is_deleted == False,
        ).order_by(Milestone.due_date).all()
        project_milestones[p.id] = [m.to_dict() for m in mstones]

    return {
        "page_title": "New Submission",
        "page_description": "Submit your work",
        "projects": projects,
        "selected_project": selected_project,
        "project_documents": project_documents,
        "project_milestones": project_milestones,
    }


@submissions_router.post('/new')
async def submission_create(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        payload = await request.form()
        title = payload.get('title', '').strip()
        description = payload.get('description', '').strip()
        project_id = payload.get('project_id')
        milestone_id = payload.get('milestone_id') or None

        if not title or not project_id:
            raise HTTPException(400, "Title and project are required")

        # Handle document: either upload new or select existing
        document_id = None
        doc_source = payload.get('doc_source', 'none')  # 'none', 'upload', 'existing'

        if doc_source == 'upload':
            file = payload.get('file')
            if file and hasattr(file, 'filename') and file.filename:
                doc_title = payload.get('doc_title', '').strip() or file.filename
                document = await FirebaseService.upload_document(
                    db=db,
                    file=file,
                    title=doc_title,
                    project_id=project_id,
                    uploaded_by=user.id,
                    description=f"Uploaded with submission: {title}",
                    milestone_id=milestone_id,
                )
                document_id = document.id
            else:
                raise HTTPException(400, "Please select a file to upload")
        elif doc_source == 'existing':
            existing_doc_id = payload.get('existing_document_id', '').strip()
            if existing_doc_id:
                # Verify the document belongs to this project
                doc = Document.fetch_one_by_field(
                    db, throw_error=False,
                    id=existing_doc_id, project_id=project_id,
                )
                if not doc:
                    raise HTTPException(400, "Selected document not found in this project")
                document_id = existing_doc_id
            else:
                raise HTTPException(400, "Please select an existing document")

        submission = Submission.create(
            db=db,
            title=title,
            description=description,
            project_id=project_id,
            milestone_id=milestone_id,
            submitted_by=user.id,
            document_id=document_id,
            status=SubmissionStatus.SUBMITTED.value,
        )

        flash(request, 'Submission created successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url=f"/dashboard/submissions/{submission.id}", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url="/dashboard/submissions/new", status_code=303)


# ─── Detail ───────────────────────────────────────────

@submissions_router.get('/{submission_id}')
@add_template_context('pages/dashboard/submissions/detail.html')
async def submission_detail(request: Request, submission_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    submission = Submission.fetch_by_id(db, submission_id)

    project = Project.fetch_by_id(db, submission.project_id)
    submitter = User.fetch_by_id(db, submission.submitted_by)

    # Associated document
    document = None
    if submission.document_id:
        document = Document.fetch_one_by_field(db, throw_error=False, id=submission.document_id)

    # Milestone
    milestone = None
    if submission.milestone_id:
        milestone = Milestone.fetch_one_by_field(db, throw_error=False, id=submission.milestone_id)

    # Feedback for this submission
    feedbacks = db.query(Feedback, User).join(
        User, Feedback.given_by == User.id
    ).filter(
        Feedback.submission_id == submission_id,
        Feedback.is_deleted == False,
    ).order_by(Feedback.created_at.desc()).all()

    feedback_list = [{
        "feedback": f.to_dict(),
        "reviewer": u.to_dict(),
    } for f, u in feedbacks]

    status_choices = [s.value for s in SubmissionStatus]
    can_review = user.role in [UserRole.SUPERVISOR.value, UserRole.ADMIN.value]

    return {
        "page_title": submission.title,
        "page_description": "Submission details",
        "submission": submission.to_dict(),
        "project": project.to_dict(),
        "submitter": submitter.to_dict(),
        "document": document.to_dict() if document else None,
        "milestone": milestone.to_dict() if milestone else None,
        "feedbacks": feedback_list,
        "status_choices": status_choices,
        "can_review": can_review,
    }


# ─── Edit ─────────────────────────────────────────────

@submissions_router.get('/{submission_id}/edit')
@add_template_context('pages/dashboard/submissions/edit.html')
async def submission_edit_page(request: Request, submission_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    submission = Submission.fetch_by_id(db, submission_id)

    # Only submitter or admin can edit
    if submission.submitted_by != user.id and user.role != UserRole.ADMIN.value:
        raise HTTPException(403, "You can only edit your own submissions")

    project = Project.fetch_by_id(db, submission.project_id)
    milestones = db.query(Milestone).filter(
        Milestone.project_id == submission.project_id,
        Milestone.is_deleted == False,
    ).all()

    # Current document
    current_document = None
    if submission.document_id:
        current_document = Document.fetch_one_by_field(db, throw_error=False, id=submission.document_id)

    # Available documents in this project
    documents = db.query(Document).filter(
        Document.project_id == submission.project_id,
        Document.is_deleted == False,
    ).order_by(Document.created_at.desc()).all()

    return {
        "page_title": f"Edit: {submission.title}",
        "page_description": "Edit submission",
        "submission": submission.to_dict(),
        "project": project.to_dict(),
        "milestones": milestones,
        "current_document": current_document.to_dict() if current_document else None,
        "documents": [d.to_dict() for d in documents],
    }


@submissions_router.post('/{submission_id}/edit')
async def submission_edit(request: Request, submission_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        submission = Submission.fetch_by_id(db, submission_id)

        if submission.submitted_by != user.id and user.role != UserRole.ADMIN.value:
            raise HTTPException(403, "You can only edit your own submissions")

        payload = await request.form()
        update_data = {}

        title = payload.get('title', '').strip()
        if title:
            update_data['title'] = title

        description = payload.get('description', '')
        update_data['description'] = description.strip()

        milestone_id = payload.get('milestone_id')
        update_data['milestone_id'] = milestone_id or None

        # Handle document change
        doc_source = payload.get('doc_source', 'keep')  # 'keep', 'upload', 'existing', 'remove'

        if doc_source == 'upload':
            file = payload.get('file')
            if file and hasattr(file, 'filename') and file.filename:
                doc_title = payload.get('doc_title', '').strip() or file.filename
                document = await FirebaseService.upload_document(
                    db=db,
                    file=file,
                    title=doc_title,
                    project_id=submission.project_id,
                    uploaded_by=user.id,
                    description=f"Uploaded with submission: {title or submission.title}",
                    milestone_id=update_data.get('milestone_id', submission.milestone_id),
                )
                update_data['document_id'] = document.id
        elif doc_source == 'existing':
            existing_doc_id = payload.get('existing_document_id', '').strip()
            if existing_doc_id:
                doc = Document.fetch_one_by_field(
                    db, throw_error=False,
                    id=existing_doc_id, project_id=submission.project_id,
                )
                if doc:
                    update_data['document_id'] = existing_doc_id
        elif doc_source == 'remove':
            update_data['document_id'] = None

        Submission.update(db, submission_id, **update_data)
        flash(request, 'Submission updated successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url=f"/dashboard/submissions/{submission_id}", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/submissions/{submission_id}/edit", status_code=303)


# ─── Update Status (Review) ──────────────────────────

@submissions_router.post('/{submission_id}/status')
async def submission_update_status(request: Request, submission_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        if user.role not in [UserRole.SUPERVISOR.value, UserRole.ADMIN.value]:
            raise HTTPException(403, "Only supervisors and admins can review submissions")

        payload = await request.form()
        status = payload.get('status', '').strip()
        if status not in [s.value for s in SubmissionStatus]:
            raise HTTPException(400, "Invalid status")

        Submission.update(db, submission_id, status=status)
        flash(request, f'Submission marked as {status.replace("_", " ").title()}', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/submissions/{submission_id}", status_code=303)


# ─── Delete ───────────────────────────────────────────

@submissions_router.post('/{submission_id}/delete')
async def submission_delete(request: Request, submission_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        submission = Submission.fetch_by_id(db, submission_id)
        if submission.submitted_by != user.id and user.role != UserRole.ADMIN.value:
            raise HTTPException(403, "You can only delete your own submissions")

        Submission.soft_delete(db, submission_id)
        flash(request, 'Submission deleted successfully', MessageCategory.SUCCESS)
        return RedirectResponse(url="/dashboard/submissions", status_code=303)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
        return RedirectResponse(url=f"/dashboard/submissions/{submission_id}", status_code=303)
