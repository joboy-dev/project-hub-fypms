import os
import secrets
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from decouple import config

from api.utils.loggers import create_logger
from api.v1.models.document import Document


logger = create_logger(__name__)

# Allowed document extensions for academic submissions
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
    'txt', 'md', 'csv', 'zip', 'rar', '7z',
    'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp',
    'py', 'js', 'ts', 'java', 'cpp', 'c', 'h', 'html', 'css',
}


class DocumentService:

    @classmethod
    async def upload_document(
        cls,
        db: Session,
        file: UploadFile,
        title: str,
        project_id: str,
        uploaded_by: str,
        description: Optional[str] = None,
        milestone_id: Optional[str] = None,
        allowed_extensions: Optional[List[str]] = None,
    ) -> Document:
        """Upload a file and create a Document record."""

        if file.file is None or not file.filename:
            raise HTTPException(400, "No file provided")

        filename = file.filename
        file_extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        # Check extension
        exts = set(allowed_extensions) if allowed_extensions else ALLOWED_EXTENSIONS
        if file_extension not in exts:
            raise HTTPException(
                400,
                f"File extension '.{file_extension}' is not allowed. "
                f"Allowed: {', '.join(sorted(exts))}",
            )

        # Check size
        max_mb = config("FILE_UPLOAD_LIMIT_MB", cast=int, default=10)
        max_bytes = max_mb * 1024 * 1024
        if file.size and file.size > max_bytes:
            raise HTTPException(400, f"File size exceeds the {max_mb} MB limit")

        # Build safe filename & local path
        safe_name = f"{filename.rsplit('.', 1)[0]}_{secrets.token_hex(6)}.{file_extension}"
        safe_name = safe_name.replace(' ', '_')

        storage_dir = config("FILESTORAGE", default="filestorage")
        file_path = f"{storage_dir}/projects/{project_id}/documents/{safe_name}"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save locally
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        logger.info(f"Document saved to {file_path}")

        # Determine version (increment if same title exists in project)
        existing = Document.fetch_one_by_field(
            db, throw_error=False,
            title=title, project_id=project_id,
        )
        version = (existing.version + 1) if existing else 1

        # Create Document record
        document = Document.create(
            db=db,
            title=title,
            file_name=safe_name,
            file_path=file_path,
            file_size=file.size or len(contents),
            file_type=file_extension,
            file_url=None,  # Will be set after Firebase upload
            version=version,
            description=description,
            project_id=project_id,
            uploaded_by=uploaded_by,
            milestone_id=milestone_id,
        )

        return document

    @classmethod
    def get_project_documents(
        cls,
        db: Session,
        project_id: str,
        page: int = 1,
        per_page: int = 20,
    ):
        """Get all documents for a project."""
        _, items, count = Document.fetch_by_field(
            db, page=page, per_page=per_page,
            project_id=project_id,
        )
        return items, count

    @classmethod
    def delete_document(cls, db: Session, document_id: str):
        """Soft-delete a document."""
        Document.soft_delete(db, document_id)

    @classmethod
    def update_document(cls, db: Session, document_id: str, **kwargs):
        """Update document metadata."""
        return Document.update(db, document_id, **kwargs)
