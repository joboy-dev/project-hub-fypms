import sqlalchemy as sa
from sqlalchemy.orm import relationship

from api.core.base.base_model import BaseTableModel


class Department(BaseTableModel):
    __tablename__ = 'departments'
    
    name = sa.Column(sa.String(255), nullable=False, unique=True)
    code = sa.Column(sa.String(20), nullable=False, unique=True, index=True)
    description = sa.Column(sa.Text, nullable=True)
    
    def to_dict(self, excludes=[]):
        return super().to_dict(excludes=excludes)
