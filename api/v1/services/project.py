from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from api.v1.models.project import Project, ProjectStatus
from api.v1.models.project_member import ProjectMember, ProjectMemberRole
from api.v1.models.user import User, UserRole
from api.utils.loggers import create_logger


logger = create_logger(__name__)


class ProjectService:

    @classmethod
    def create_project(
        cls,
        db: Session,
        title: str,
        description: str,
        owner_id: str,
        department_id: Optional[str] = None,
    ):
        """Create a new project and add the creator as owner."""

        project = Project.create(
            db=db,
            title=title,
            description=description,
            status=ProjectStatus.DRAFT.value,
            department_id=department_id,
        )

        # Add creator as project owner
        ProjectMember.create(
            db=db,
            project_id=project.id,
            user_id=owner_id,
            role=ProjectMemberRole.OWNER.value,
        )

        return project

    @classmethod
    def add_member(cls, db: Session, project_id: str, user_id: str, role: str = ProjectMemberRole.MEMBER.value):
        """Add a student member to a project."""
        existing = ProjectMember.fetch_one_by_field(
            db, throw_error=False, project_id=project_id, user_id=user_id
        )
        if existing:
            raise HTTPException(400, "User is already a member of this project")

        return ProjectMember.create(db=db, project_id=project_id, user_id=user_id, role=role)

    @classmethod
    def join_via_invite(cls, db: Session, invite_code: str, user_id: str):
        """Join a project using an invite code. Returns (project, message)."""

        project = Project.fetch_one_by_field(db, throw_error=False, invite_code=invite_code)
        if not project:
            raise HTTPException(404, "Invalid invite link. The project was not found.")

        # Only students can join via invite
        user = User.fetch_by_id(db, user_id)
        if user.role != UserRole.STUDENT.value:
            raise HTTPException(403, "Only students can join projects via invite link.")

        # Check if already a member
        existing = ProjectMember.fetch_one_by_field(
            db, throw_error=False, project_id=project.id, user_id=user_id
        )
        if existing:
            return project, "You are already a member of this project."

        ProjectMember.create(
            db=db,
            project_id=project.id,
            user_id=user_id,
            role=ProjectMemberRole.MEMBER.value,
        )
        return project, "You have been added to the project successfully!"

    @classmethod
    def regenerate_invite_code(cls, db: Session, project_id: str, user_id: str):
        """Regenerate the invite code for a project. Only the owner can do this."""
        import secrets

        member = ProjectMember.fetch_one_by_field(
            db, throw_error=False, project_id=project_id, user_id=user_id
        )
        if not member or member.role != ProjectMemberRole.OWNER.value:
            raise HTTPException(403, "Only the project owner can regenerate the invite link.")

        new_code = secrets.token_urlsafe(12)
        Project.update(db, project_id, invite_code=new_code)
        return new_code

    @classmethod
    def remove_member(cls, db: Session, project_id: str, user_id: str):
        member = ProjectMember.fetch_one_by_field(db, project_id=project_id, user_id=user_id)
        ProjectMember.hard_delete(db, member.id)

    @classmethod
    def assign_supervisor(cls, db: Session, project_id: str, supervisor_id: str):
        return Project.update(db, project_id, supervisor_id=supervisor_id)

    @classmethod
    def update_status(cls, db: Session, project_id: str, status: str):
        return Project.update(db, project_id, status=status)

    @classmethod
    def get_student_projects(cls, db: Session, user_id: str, page: int = 1, per_page: int = 10):
        """Get all projects where user is a member."""
        member_records = db.query(ProjectMember).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.is_deleted == False,
        ).all()
        project_ids = [m.project_id for m in member_records]
        if not project_ids:
            return [], 0

        query = db.query(Project).filter(
            Project.id.in_(project_ids),
            Project.is_deleted == False,
        ).order_by(Project.created_at.desc())

        count = query.count()
        offset = (page - 1) * per_page
        projects = query.offset(offset).limit(per_page).all()
        return projects, count

    @classmethod
    def get_supervisor_projects(cls, db: Session, supervisor_id: str, page: int = 1, per_page: int = 10):
        """Get all projects supervised by a user."""
        query = db.query(Project).filter(
            Project.supervisor_id == supervisor_id,
            Project.is_deleted == False,
        ).order_by(Project.created_at.desc())

        count = query.count()
        offset = (page - 1) * per_page
        projects = query.offset(offset).limit(per_page).all()
        return projects, count

    @classmethod
    def get_supervised_students(cls, db: Session, supervisor_id: str, page: int = 1, per_page: int = 10):
        """Get all students whose projects are supervised by this supervisor."""
        project_ids = [
            p.id for p in db.query(Project.id).filter(
                Project.supervisor_id == supervisor_id,
                Project.is_deleted == False,
            ).all()
        ]
        if not project_ids:
            return [], 0

        student_ids = list(set(
            m.user_id for m in db.query(ProjectMember.user_id).filter(
                ProjectMember.project_id.in_(project_ids),
                ProjectMember.is_deleted == False,
            ).all()
        ))
        if not student_ids:
            return [], 0

        query = db.query(User).filter(
            User.id.in_(student_ids),
            User.is_deleted == False,
        ).order_by(User.created_at.desc())

        count = query.count()
        offset = (page - 1) * per_page
        students = query.offset(offset).limit(per_page).all()
        return students, count
