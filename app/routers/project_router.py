"""Project API routes."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services import project_service


router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
def create_project(
    project_data: ProjectCreate,
    database_session: Session = Depends(get_db),
) -> ProjectResponse:
    """Create a new project."""

    return project_service.create_project(
        database_session=database_session,
        project_data=project_data,
    )


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
)
def list_projects(
    user_id: str = Query(
        ...,
        min_length=1,
        description=(
            "User ID used to fetch projects. "
            "This will later come from the JWT token."
        ),
    ),
    database_session: Session = Depends(get_db),
) -> ProjectListResponse:
    """Return all active projects for a user."""

    return project_service.list_projects(
        database_session=database_session,
        user_id=user_id,
    )


@router.get(
    "/deleted",
    response_model=ProjectListResponse,
    summary="List deleted projects",
)
def list_deleted_projects(
    user_id: str = Query(...),
    database_session: Session = Depends(get_db),
) -> ProjectListResponse:
    """Return soft-deleted projects."""

    return project_service.list_deleted_projects(
        database_session=database_session,
        user_id=user_id,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project",
)
def get_project(
    project_id: str,
    database_session: Session = Depends(get_db),
) -> ProjectResponse:
    """Return one active project."""

    return project_service.get_project(
        database_session=database_session,
        project_id=project_id,
    )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    database_session: Session = Depends(get_db),
) -> ProjectResponse:
    """Update an existing project."""

    return project_service.update_project(
        database_session=database_session,
        project_id=project_id,
        project_data=project_data,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
def delete_project(
    project_id: str,
    delete_permanently: bool = Query(
        default=False,
        description=(
            "Set to true to permanently delete an already "
            "soft-deleted project."
        ),
    ),
    database_session: Session = Depends(get_db),
) -> Response:
    """Soft-delete or permanently delete a project."""

    project_service.delete_project(
        database_session=database_session,
        project_id=project_id,
        delete_permanently=delete_permanently,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )