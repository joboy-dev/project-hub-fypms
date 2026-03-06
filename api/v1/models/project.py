import sqlalchemy as sa
import enum
import secrets
from sqlalchemy.orm import relationship

from api.core.base.base_model import BaseTableModel


def _generate_invite_code():
    """Generate a short, URL-safe invite code."""
    return secrets.token_urlsafe(12)


class ProjectStatus(enum.Enum):
    DRAFT = 'draft'
    PROPOSED = 'proposed'
    APPROVED = 'approved'
    IN_PROGRESS = 'in_progress'
    UNDER_REVIEW = 'under_review'
    COMPLETED = 'completed'
    REJECTED = 'rejected'


class Project(BaseTableModel):
    __tablename__ = 'projects'
    
    title = sa.Column(sa.String(500), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    status = sa.Column(sa.String, default=ProjectStatus.DRAFT.value, index=True)
    invite_code = sa.Column(sa.String(24), unique=True, index=True, default=_generate_invite_code)
    
    supervisor_id = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=True, index=True)
    department_id = sa.Column(sa.String, sa.ForeignKey('departments.id'), nullable=True, index=True)
    
    start_date = sa.Column(sa.DateTime(timezone=True), nullable=True)
    end_date = sa.Column(sa.DateTime(timezone=True), nullable=True)
    grade = sa.Column(sa.String(10), nullable=True)
    
    # Relationships
    members = relationship('ProjectMember', backref='project', lazy='selectin',
                           foreign_keys='ProjectMember.project_id')
    supervisor = relationship('User', foreign_keys=[supervisor_id], lazy='selectin')
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
