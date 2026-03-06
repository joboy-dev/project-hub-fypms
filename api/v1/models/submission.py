import sqlalchemy as sa
import enum

from api.core.base.base_model import BaseTableModel


class SubmissionStatus(enum.Enum):
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REVISION_REQUIRED = 'revision_required'
    REJECTED = 'rejected'


class Submission(BaseTableModel):
    __tablename__ = 'submissions'
    
    title = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    status = sa.Column(sa.String, default=SubmissionStatus.SUBMITTED.value, index=True)
    
    project_id = sa.Column(sa.String, sa.ForeignKey('projects.id'), nullable=False, index=True)
    milestone_id = sa.Column(sa.String, sa.ForeignKey('milestones.id'), nullable=True, index=True)
    submitted_by = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    document_id = sa.Column(sa.String, sa.ForeignKey('documents.id'), nullable=True, index=True)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
