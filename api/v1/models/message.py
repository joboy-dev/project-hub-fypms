import sqlalchemy as sa

from api.core.base.base_model import BaseTableModel


class Message(BaseTableModel):
    __tablename__ = 'messages'
    
    content = sa.Column(sa.Text, nullable=False)
    sender_id = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    project_id = sa.Column(sa.String, sa.ForeignKey('projects.id'), nullable=True, index=True)
    is_read = sa.Column(sa.Boolean, default=False)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
