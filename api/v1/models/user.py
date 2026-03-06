import sqlalchemy as sa
import enum
from sqlalchemy import event
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, timezone

from api.core.base.base_model import BaseTableModel


class UserRole(enum.Enum):
    ADMIN = 'admin'
    STUDENT = 'student'
    SUPERVISOR = 'supervisor'


class User(BaseTableModel):
    __tablename__ = 'users'
    
    first_name = sa.Column(sa.String(100), nullable=False)
    last_name = sa.Column(sa.String(100), nullable=False)
    email = sa.Column(sa.String, nullable=False, unique=True, index=True)
    password = sa.Column(sa.String, nullable=True)
    role = sa.Column(sa.String, nullable=False, default=UserRole.STUDENT.value, index=True)
    profile_picture = sa.Column(sa.String, nullable=True)
    is_active = sa.Column(sa.Boolean, default=True, index=True)
    last_login = sa.Column(sa.DateTime(timezone=True), nullable=True)
    
    department_id = sa.Column(sa.String, sa.ForeignKey('departments.id'), nullable=True, index=True)
    
    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes+['password'])
