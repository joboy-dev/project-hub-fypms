from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.core.dependencies.context import add_template_context
from api.db.database import get_db
from api.utils import paginator
from api.utils.loggers import create_logger
from api.v1.services.project import ProjectService
from api.v1.routes.dashboard.helpers import _get_user, _paginate


students_router = APIRouter(prefix='/students', tags=['Students'])
logger = create_logger(__name__)


@students_router.get('')
@add_template_context('pages/dashboard/students/index.html')
async def students_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request)
    page, size = _paginate(request, '/dashboard/students')

    students, count = ProjectService.get_supervised_students(db, user.id, page, size)
    response = paginator.build_paginated_response(
        items=[s.to_dict() for s in students],
        endpoint='/dashboard/students', total=count, page=page, size=size,
    )

    return {
        "page_title": "My Students",
        "page_description": "Students under your supervision",
        "students": response['data'],
        "pagination_data": response['pagination_data'],
    }
