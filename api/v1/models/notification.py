import sqlalchemy as sa
import enum

from api.core.base.base_model import BaseTableModel


class NotificationType(enum.Enum):
    SUBMISSION = 'submission'
    FEEDBACK = 'feedback'
    MESSAGE = 'message'
    MILESTONE = 'milestone'
    PROJECT_UPDATE = 'project_update'
    SYSTEM = 'system'


class Notification(BaseTableModel):
    __tablename__ = 'notifications'
    
    content = sa.Column(sa.Text, nullable=False)
    type = sa.Column(sa.String, default=NotificationType.SYSTEM.value, index=True)
    user_id = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    is_read = sa.Column(sa.Boolean, default=False)
    link = sa.Column(sa.String, nullable=True)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
