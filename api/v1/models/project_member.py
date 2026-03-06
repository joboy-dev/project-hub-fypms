import sqlalchemy as sa
import enum

from api.core.base.base_model import BaseTableModel


class ProjectMemberRole(enum.Enum):
    OWNER = 'owner'       # The student who created / leads the project
    MEMBER = 'member'     # Additional student collaborators


class ProjectMember(BaseTableModel):
    __tablename__ = 'project_members'

    project_id = sa.Column(sa.String, sa.ForeignKey('projects.id'), nullable=False, index=True)
    user_id = sa.Column(sa.String, sa.ForeignKey('users.id'), nullable=False, index=True)
    role = sa.Column(sa.String, default=ProjectMemberRole.MEMBER.value, nullable=False)

    # Prevent the same user being added to the same project twice
    __table_args__ = (
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_member'),
    )

    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
