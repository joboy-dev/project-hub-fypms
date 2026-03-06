import os
from typing import Optional, List
from fastapi import UploadFile
from sqlalchemy.orm import Session
from decouple import config
import firebase_admin
from firebase_admin import credentials, storage, firestore

from firebase_config import firebase_config
from api.v1.models.document import Document
from api.v1.services.document import DocumentService
from api.utils.loggers import create_logger


logger = create_logger(__name__)

class FirebaseService:
    _instance = None

    def __init__(self):
        # Path to your service account key file
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccount.json")
            firebase_admin.initialize_app(cred, firebase_config)
        
        # self.db = firestore.client()
        self.bucket = storage.bucket()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    async def upload_document(
        self,
        db: Session,
        file: UploadFile,
        title: str,
        project_id: str,
        uploaded_by: str,
        description: Optional[str] = None,
        milestone_id: Optional[str] = None,
        allowed_extensions: Optional[List[str]] = None,
    ) -> Document:
        """Upload a document locally via DocumentService, then push to Firebase Storage."""

        # Step 1: Save locally & create Document record
        document = await DocumentService.upload_document(
            db=db,
            file=file,
            title=title,
            project_id=project_id,
            uploaded_by=uploaded_by,
            description=description,
            milestone_id=milestone_id,
            allowed_extensions=allowed_extensions,
        )

        # Step 2: Push to Firebase Storage
        try:
            app_name = config("APP_NAME", default="ProjectHub")
            firebase_path = f"{app_name}/projects/{project_id}/documents/{document.file_name}"

            blob = self.bucket.blob(firebase_path)
            blob.upload_from_filename(document.file_path)
            download_url = blob.public_url

            # Update document with the Firebase download URL
            Document.update(db=db, id=document.id, file_url=download_url)
            document.file_url = download_url

            logger.info(f"Document uploaded to Firebase: {firebase_path}")
        except Exception as e:
            logger.error(f"Firebase upload failed (local copy preserved): {e}")
            # Document still exists locally even if Firebase fails

        return document
