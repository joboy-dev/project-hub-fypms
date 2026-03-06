from sqlalchemy.orm import Session
from sqlalchemy import func

from api.v1.models.project import Project, ProjectStatus
from api.v1.models.project_member import ProjectMember
from api.v1.models.submission import Submission, SubmissionStatus
from api.v1.models.milestone import Milestone, MilestoneStatus
from api.v1.models.message import Message
from api.v1.models.notification import Notification
from api.v1.models.user import User, UserRole
from api.v1.models.department import Department
from api.utils.loggers import create_logger


logger = create_logger(__name__)


class DashboardService:
    """Aggregates stats for role-based dashboard overviews."""

    # ── Student ───────────────────────────────────────
    @classmethod
    def student_stats(cls, db: Session, user_id: str) -> dict:
        # Project IDs the student belongs to
        project_ids = [
            m.project_id for m in db.query(ProjectMember.project_id).filter(
                ProjectMember.user_id == user_id,
                ProjectMember.is_deleted == False,
            ).all()
        ]

        total_projects = len(project_ids)
        active_projects = db.query(Project).filter(
            Project.id.in_(project_ids),
            Project.status.in_([ProjectStatus.IN_PROGRESS.value, ProjectStatus.APPROVED.value]),
            Project.is_deleted == False,
        ).count() if project_ids else 0

        total_submissions = db.query(Submission).filter(
            Submission.submitted_by == user_id,
            Submission.is_deleted == False,
        ).count()

        pending_milestones = db.query(Milestone).filter(
            Milestone.project_id.in_(project_ids),
            Milestone.status.in_([MilestoneStatus.PENDING.value, MilestoneStatus.IN_PROGRESS.value]),
            Milestone.is_deleted == False,
        ).count() if project_ids else 0

        unread_messages = db.query(Message).filter(
            Message.receiver_id == user_id,
            Message.is_read == False,
            Message.is_deleted == False,
        ).count()

        # Recent activity: latest 5 submissions
        recent_submissions = db.query(Submission).filter(
            Submission.submitted_by == user_id,
            Submission.is_deleted == False,
        ).order_by(Submission.created_at.desc()).limit(5).all()

        return {
            "total_projects": total_projects,
            "active_projects": active_projects,
            "total_submissions": total_submissions,
            "pending_milestones": pending_milestones,
            "unread_messages": unread_messages,
            "recent_submissions": recent_submissions,
        }

    # ── Supervisor ────────────────────────────────────
    @classmethod
    def supervisor_stats(cls, db: Session, user_id: str) -> dict:
        supervised_projects = db.query(Project).filter(
            Project.supervisor_id == user_id,
            Project.is_deleted == False,
        ).count()

        active_projects = db.query(Project).filter(
            Project.supervisor_id == user_id,
            Project.status.in_([ProjectStatus.IN_PROGRESS.value, ProjectStatus.APPROVED.value]),
            Project.is_deleted == False,
        ).count()

        # Students under supervision
        project_ids = [
            p.id for p in db.query(Project.id).filter(
                Project.supervisor_id == user_id,
                Project.is_deleted == False,
            ).all()
        ]
        student_ids = set()
        if project_ids:
            student_ids = set(
                m.user_id for m in db.query(ProjectMember.user_id).filter(
                    ProjectMember.project_id.in_(project_ids),
                    ProjectMember.is_deleted == False,
                ).all()
            )

        pending_reviews = db.query(Submission).filter(
            Submission.project_id.in_(project_ids),
            Submission.status == SubmissionStatus.SUBMITTED.value,
            Submission.is_deleted == False,
        ).count() if project_ids else 0

        unread_messages = db.query(Message).filter(
            Message.receiver_id == user_id,
            Message.is_read == False,
            Message.is_deleted == False,
        ).count()

        recent_submissions = db.query(Submission).filter(
            Submission.project_id.in_(project_ids),
            Submission.is_deleted == False,
        ).order_by(Submission.created_at.desc()).limit(5).all() if project_ids else []

        return {
            "supervised_projects": supervised_projects,
            "active_projects": active_projects,
            "total_students": len(student_ids),
            "pending_reviews": pending_reviews,
            "unread_messages": unread_messages,
            "recent_submissions": recent_submissions,
        }

    # ── Admin ─────────────────────────────────────────
    @classmethod
    def admin_stats(cls, db: Session) -> dict:
        total_projects = db.query(Project).filter(Project.is_deleted == False).count()
        active_projects = db.query(Project).filter(
            Project.status.in_([ProjectStatus.IN_PROGRESS.value, ProjectStatus.APPROVED.value]),
            Project.is_deleted == False,
        ).count()
        total_users = db.query(User).filter(User.is_deleted == False).count()
        total_students = db.query(User).filter(
            User.role == UserRole.STUDENT.value,
            User.is_deleted == False,
        ).count()
        total_supervisors = db.query(User).filter(
            User.role == UserRole.SUPERVISOR.value,
            User.is_deleted == False,
        ).count()
        total_departments = db.query(Department).filter(Department.is_deleted == False).count()
        total_submissions = db.query(Submission).filter(Submission.is_deleted == False).count()
        pending_submissions = db.query(Submission).filter(
            Submission.status == SubmissionStatus.SUBMITTED.value,
            Submission.is_deleted == False,
        ).count()

        recent_projects = db.query(Project).filter(
            Project.is_deleted == False,
        ).order_by(Project.created_at.desc()).limit(5).all()

        return {
            "total_projects": total_projects,
            "active_projects": active_projects,
            "total_users": total_users,
            "total_students": total_students,
            "total_supervisors": total_supervisors,
            "total_departments": total_departments,
            "total_submissions": total_submissions,
            "pending_submissions": pending_submissions,
            "recent_projects": recent_projects,
        }
