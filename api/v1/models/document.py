import sqlalchemy as sa

from api.core.base.base_model import BaseTableModel


class Document(BaseTableModel):
    __tablename__ = 'documents'
    
    title = sa.Column(sa.String(255), nullable=False)
    file_name = sa.Column(sa.String(255), nullable=False)
    file_path = sa.Column(sa.String(1000), nullable=False)
    file_size = sa.Column(sa.Integer, nullable=True)
    file_type = sa.Column(sa.String(50), nullable=True)
    file_url = sa.Column(sa.String(1000), nullable=True)
    version = sa.Column(sa.Integer, default=1)
    description = sa.Column(sa.Text, nullable=True)
    
    project_id = sa.Column(sa.String, sa.ForeignKey('projects.id'), nullable=False, index=True)
    uploaded_by = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    milestone_id = sa.Column(sa.String, sa.ForeignKey('milestones.id'), nullable=True, index=True)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
