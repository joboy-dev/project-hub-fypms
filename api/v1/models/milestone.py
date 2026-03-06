import sqlalchemy as sa
import enum

from api.core.base.base_model import BaseTableModel


class MilestoneStatus(enum.Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    OVERDUE = 'overdue'


class Milestone(BaseTableModel):
    __tablename__ = 'milestones'
    
    title = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    due_date = sa.Column(sa.DateTime(timezone=True), nullable=False)
    status = sa.Column(sa.String, default=MilestoneStatus.PENDING.value, index=True)
    
    project_id = sa.Column(sa.String, sa.ForeignKey('projects.id'), nullable=False, index=True)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
