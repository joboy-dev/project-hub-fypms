from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from decouple import config

from api.core.dependencies.context import add_template_context
from api.core.dependencies.flash_messages import MessageCategory, flash
from api.db.database import get_db
from api.utils.loggers import create_logger
from api.v1.models.user import User, UserRole
from api.v1.models.document import Document
from api.v1.models.project import Project
from api.v1.models.project_member import ProjectMember
from api.utils.firebase_service import FirebaseService
from api.v1.routes.dashboard.helpers import _get_user


# Router for project-scoped actions (upload, delete)
documents_router = APIRouter(prefix='/projects/{project_id}/documents', tags=['Documents'])

# Router for standalone document viewing
document_view_router = APIRouter(prefix='/documents', tags=['Documents'])

logger = create_logger(__name__)


# ─── View Document ────────────────────────────────────

@document_view_router.get('/{document_id}')
@add_template_context('pages/dashboard/documents/view.html')
async def document_view(request: Request, document_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    document = Document.fetch_by_id(db, document_id)
    project = Project.fetch_by_id(db, document.project_id)
    uploader = User.fetch_by_id(db, document.uploaded_by)

    # Resolve the viewable URL: prefer file_url (Firebase), fall back to local path
    filestorage = config("FILESTORAGE", default="filestorage")
    if document.file_url:
        view_url = document.file_url
    elif document.file_path:
        # Local files are served via StaticFiles mount at /{FILESTORAGE}
        view_url = f"/{document.file_path}"
    else:
        view_url = None

    # Determine if the file is viewable inline in the browser
    viewable_types = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'txt', 'md', 'html', 'css', 'js', 'py', 'csv'}
    is_viewable = document.file_type and document.file_type.lower() in viewable_types
    is_image = document.file_type and document.file_type.lower() in {'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'}
    is_pdf = document.file_type and document.file_type.lower() == 'pdf'
    is_text = document.file_type and document.file_type.lower() in {'txt', 'md', 'html', 'css', 'js', 'py', 'csv'}

    return {
        "page_title": document.title or document.file_name,
        "page_description": "View document",
        "document": document.to_dict(),
        "project": project.to_dict(),
        "uploader": uploader.to_dict(),
        "view_url": view_url,
        "is_viewable": is_viewable,
        "is_image": is_image,
        "is_pdf": is_pdf,
        "is_text": is_text,
    }


# ─── Upload ───────────────────────────────────────────

@documents_router.post('/upload')
async def document_upload(
    request: Request,
    project_id: str,
    db: Session = Depends(get_db),
):
    user = _get_user(request)
    try:
        form = await request.form()
        file = form.get('file')
        if not file:
            raise HTTPException(400, "No file provided")

        title = form.get('title', '').strip() or file.filename
        description = form.get('description', '').strip() or None
        milestone_id = form.get('milestone_id') or None

        document = await FirebaseService.upload_document(
            db=db,
            file=file,
            title=title,
            project_id=project_id,
            uploaded_by=user.id,
            description=description,
            milestone_id=milestone_id,
        )

        flash(request, f'Document "{document.title}" uploaded successfully', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        flash(request, 'Failed to upload document', MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)


# ─── Delete ───────────────────────────────────────────

@documents_router.post('/{document_id}/delete')
async def document_delete(request: Request, project_id: str, document_id: str, db: Session = Depends(get_db)):
    user = _get_user(request)
    try:
        document = Document.fetch_by_id(db, document_id)

        # Only uploader, project owner, or admin can delete
        if document.uploaded_by != user.id and user.role != UserRole.ADMIN.value:
            member = ProjectMember.fetch_one_by_field(
                db, throw_error=False, project_id=project_id, user_id=user.id
            )
            if not member or member.role != 'owner':
                raise HTTPException(403, "You don't have permission to delete this document")

        Document.soft_delete(db, document_id)
        flash(request, 'Document deleted', MessageCategory.SUCCESS)
    except HTTPException as e:
        flash(request, e.detail, MessageCategory.ERROR)
    return RedirectResponse(url=f"/dashboard/projects/{project_id}", status_code=303)
