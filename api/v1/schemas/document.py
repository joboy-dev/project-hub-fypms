from typing import Optional
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, field_validator

from api.utils.form_factory import as_form_factory


class DocumentUpload(BaseModel):
    """Schema for uploading a document to a project."""

    file: UploadFile = File(...)
    title: str = Form(...)
    description: Optional[str] = Form(None)
    project_id: str = Form(...)
    milestone_id: Optional[str] = Form(None)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v


class DocumentUpdate(BaseModel):
    """Schema for updating document metadata."""

    title: Optional[str] = Form(None)
    description: Optional[str] = Form(None)
    milestone_id: Optional[str] = Form(None)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v


DocumentUpload.as_form = as_form_factory(DocumentUpload)
DocumentUpdate.as_form = as_form_factory(DocumentUpdate)
