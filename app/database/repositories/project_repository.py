"""Database operations for projects."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


def create_project(
    database_session: Session,
    project_data: ProjectCreate,
) -> Project:
    """Create and save a new project."""

    project = Project(
        user_id=project_data.user_id,
        project_name=project_data.project_name,
        markets=project_data.markets,
        mags=project_data.mags,
        retailers=project_data.retailers,
        description=project_data.description,
    )

    database_session.add(project)
    database_session.commit()
    database_session.refresh(project)

    return project


def get_project_by_id(
    database_session: Session,
    project_id: str,
) -> Project | None:
    """Return one active project by ID."""

    statement = select(Project).where(
        Project.project_id == project_id,
        # Project.is_deleted.is_(False),
    )

    return database_session.scalar(statement)


def list_projects_by_user(
    database_session: Session,
    user_id: str,
) -> list[Project]:
    """Return all active projects belonging to a user."""

    statement = (
        select(Project)
        .where(
            Project.user_id == user_id,
            # Project.is_deleted.is_(False),
        )
        .order_by(Project.updated_at.desc())
    )

    return list(
        database_session.scalars(statement).all()
    )


def list_deleted_projects_by_user(
    database_session: Session,
    user_id: str,
) -> list[Project]:
    """Return soft-deleted projects belonging to a user."""

    statement = (
        select(Project)
        .where(
            Project.user_id == user_id,
            Project.is_deleted.is_(True),
        )
        .order_by(Project.updated_at.desc())
    )

    return list(
        database_session.scalars(statement).all()
    )


def update_project(
    database_session: Session,
    project: Project,
    project_data: ProjectUpdate,
) -> Project:
    """Update an existing project."""

    update_values = project_data.model_dump(
        exclude_unset=True,
    )

    for field_name, field_value in update_values.items():
        setattr(
            project,
            field_name,
            field_value,
        )

    database_session.add(project)
    database_session.commit()
    database_session.refresh(project)

    return project


def soft_delete_project(
    database_session: Session,
    project: Project,
) -> Project:
    """Soft-delete a project."""

    project.is_deleted = True

    database_session.add(project)
    database_session.commit()
    database_session.refresh(project)

    return project


def project_name_exists_for_user(
    database_session: Session,
    user_id: str,
    project_name: str,
    exclude_project_id: str | None = None,
) -> bool:
    """Check whether an active project name already exists for a user."""

    statement = select(Project.project_id).where(
        Project.user_id == user_id,
        Project.project_name == project_name,
        # Project.is_deleted.is_(False),
    )

    if exclude_project_id:
        statement = statement.where(
            Project.project_id != exclude_project_id,
        )

    return database_session.scalar(statement) is not None




def get_project_by_id_including_deleted(
    database_session: Session,
    project_id: str,
) -> Project | None:
    """Return a project by ID, including soft-deleted projects."""

    statement = select(Project).where(
        Project.project_id == project_id,
    )

    return database_session.scalar(statement)


def permanently_delete_project(
    database_session: Session,
    project: Project,
) -> None:
    """Permanently remove a project from the database."""

    database_session.delete(project)
    database_session.commit()