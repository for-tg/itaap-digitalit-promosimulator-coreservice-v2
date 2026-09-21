"""Business logic for project management."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models.project import Project
from app.database.repositories import project_repository
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)


def create_project(
    database_session: Session,
    project_data: ProjectCreate,
) -> ProjectResponse:
    """Create a new project."""

    project_name_exists = (
        project_repository.project_name_exists_for_user(
            database_session=database_session,
            user_id=project_data.user_id,
            project_name=project_data.project_name,
        )
    )

    if project_name_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A project with this name already exists "
                "for the selected user."
            ),
        )

    project = project_repository.create_project(
        database_session=database_session,
        project_data=project_data,
    )

    return ProjectResponse.model_validate(project)


def get_project(
    database_session: Session,
    project_id: str,
) -> ProjectResponse:
    """Return a project by ID."""

    project = _get_existing_project(
        database_session=database_session,
        project_id=project_id,
    )

    return ProjectResponse.model_validate(project)


def list_projects(
    database_session: Session,
    user_id: str,
) -> ProjectListResponse:
    """Return all active projects for a user."""

    cleaned_user_id = user_id.strip()

    if not cleaned_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must not be empty.",
        )

    projects = project_repository.list_projects_by_user(
        database_session=database_session,
        user_id=cleaned_user_id,
    )

    project_responses = [
        ProjectResponse.model_validate(project)
        for project in projects
    ]

    return ProjectListResponse(
        total=len(project_responses),
        projects=project_responses,
    )


def update_project(
    database_session: Session,
    project_id: str,
    project_data: ProjectUpdate,
) -> ProjectResponse:
    """Update an existing project."""

    project = _get_existing_project(
        database_session=database_session,
        project_id=project_id,
    )

    update_values = project_data.model_dump(
        exclude_unset=True,
    )

    if not update_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update.",
        )

    if (
        project_data.project_name is not None
        and project_data.project_name != project.project_name
    ):
        project_name_exists = (
            project_repository.project_name_exists_for_user(
                database_session=database_session,
                user_id=project.user_id,
                project_name=project_data.project_name,
                exclude_project_id=project.project_id,
            )
        )

        if project_name_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A project with this name already exists "
                    "for the selected user."
                ),
            )

    updated_project = project_repository.update_project(
        database_session=database_session,
        project=project,
        project_data=project_data,
    )

    return ProjectResponse.model_validate(
        updated_project
    )


def delete_project(
    database_session: Session,
    project_id: str,
    delete_permanently: bool = False,
) -> None:
    """Soft-delete or permanently delete a project."""

    cleaned_project_id = project_id.strip()

    if not cleaned_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must not be empty.",
        )

    project = (
        project_repository.get_project_by_id_including_deleted(
            database_session=database_session,
            project_id=cleaned_project_id,
        )
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if delete_permanently:
        if not project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Project must be soft deleted before "
                    "it can be permanently deleted."
                ),
            )

        project_repository.permanently_delete_project(
            database_session=database_session,
            project=project,
        )

        return

    if project.is_deleted:
        return

    project_repository.soft_delete_project(
        database_session=database_session,
        project=project,
    )

def _get_existing_project(
    database_session: Session,
    project_id: str,
) -> Project:
    """Return an active project or raise a 404 error."""

    cleaned_project_id = project_id.strip()

    if not cleaned_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must not be empty.",
        )

    project = project_repository.get_project_by_id(
        database_session=database_session,
        project_id=cleaned_project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    return project


def list_deleted_projects(
    database_session: Session,
    user_id: str,
) -> ProjectListResponse:
    """Return soft-deleted projects for a user."""

    cleaned_user_id = user_id.strip()

    if not cleaned_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must not be empty.",
        )

    projects = project_repository.list_deleted_projects_by_user(
        database_session=database_session,
        user_id=cleaned_user_id,
    )

    project_responses = [
        ProjectResponse.model_validate(project)
        for project in projects
    ]

    return ProjectListResponse(
        total=len(project_responses),
        projects=project_responses,
    )


def restore_project(
    database_session: Session,
    project_id: str,
) -> ProjectResponse:
    """Restore a soft-deleted project."""

    cleaned_project_id = project_id.strip()

    if not cleaned_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must not be empty.",
        )

    project = (
        project_repository.get_project_by_id_including_deleted(
            database_session=database_session,
            project_id=cleaned_project_id,
        )
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    if not project.is_deleted:
        return ProjectResponse.model_validate(project)

    restored_project = project_repository.restore_project(
        database_session=database_session,
        project=project,
    )

    return ProjectResponse.model_validate(
        restored_project
    )