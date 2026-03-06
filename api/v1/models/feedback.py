import sqlalchemy as sa

from api.core.base.base_model import BaseTableModel


class Feedback(BaseTableModel):
    __tablename__ = 'feedbacks'
    
    content = sa.Column(sa.Text, nullable=False)
    grade = sa.Column(sa.String(10), nullable=True)
    
    submission_id = sa.Column(sa.String, sa.ForeignKey('submissions.id'), nullable=True, index=True)
    project_id = sa.Column(sa.String, sa.ForeignKey('projects.id'), nullable=False, index=True)
    given_by = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
