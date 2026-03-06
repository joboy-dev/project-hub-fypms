from typing import Optional, List
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, field_validator

from api.utils.form_factory import as_form_factory


# @as_form
class FileBase(BaseModel):
    
    file: UploadFile = File(...)
    organization_id: str = Form(...)
    file_name: Optional[str] = Form(None)
    model_id: str = Form(...)
    model_name: str = Form(...)
    url: Optional[str] = Form(None)
    description: Optional[str] = Form(None)
    label: Optional[str] = Form(None)
    
    @field_validator("model_name", "label", mode="before")
    @classmethod
    def strip_and_lower(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if isinstance(v, str) else v
    

# @as_form
class UpdateFile(BaseModel):
    
    file: Optional[UploadFile] = File(None)
    file_name: Optional[str] = Form(None)
    url: Optional[str] = Form(None)
    description: Optional[str] = Form(None)
    label: Optional[str] = Form(None)
    position: Optional[int] = Form(None)
    
    @field_validator("label", mode="before")
    @classmethod
    def strip_and_lower(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if isinstance(v, str) else v


class FolderBase(BaseModel):

    name: str
    organization_id: str
    parent_id: Optional[str] = None


class UpdateFolder(BaseModel):
    
    name: Optional[str] = None
    parent_id: Optional[str] = None


# Bulk file upload schema
class BulkFileUpload(BaseModel):
    files: List[UploadFile]
    organization_id: str
    model_id: str
    model_name: str

    @field_validator("model_name", mode="before")
    @classmethod
    def strip_and_lower_model_name(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if isinstance(v, str) else v


FileBase.as_form = as_form_factory(FileBase)
UpdateFile.as_form = as_form_factory(UpdateFile)
BulkFileUpload.as_form = as_form_factory(BulkFileUpload)