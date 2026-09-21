"""Business logic for dashboard data."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.repositories import (
    optimization_result_repository,
    project_repository,
    scenario_config_repository,
    scenario_repository,
)
from app.schemas.dashboard import (
    DashboardProjectResponse,
    DashboardResponse,
    DashboardScenarioResponse,
)


def get_dashboard(
    database_session: Session,
    user_id: str,
) -> DashboardResponse:
    """Return all active projects and scenarios for a user."""

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

    dashboard_projects: list[DashboardProjectResponse] = []

    for project in projects:
        scenarios = scenario_repository.list_scenarios_by_project(
            database_session=database_session,
            project_id=project.project_id,
        )

        dashboard_scenarios: list[DashboardScenarioResponse] = []

        for scenario in scenarios:
            scenario_config = (
                scenario_config_repository.get_config_by_scenario_id(
                    database_session=database_session,
                    scenario_id=scenario.scenario_id,
                )
            )

            optimization_result = (
                optimization_result_repository.get_optimization_result(
                    database_session=database_session,
                    scenario_id=scenario.scenario_id,
                )
            )

            dashboard_scenarios.append(
                DashboardScenarioResponse(
                    scenario_id=scenario.scenario_id,
                    scenario_name=scenario.scenario_name,
                    status=scenario.status,
                    has_config=scenario_config is not None,
                    has_optimization_result=optimization_result is not None,
                    created_at=scenario.created_at,
                    updated_at=scenario.updated_at,
                )
            )

        dashboard_projects.append(
            DashboardProjectResponse(
                project_id=project.project_id,
                project_name=project.project_name,
                markets=project.markets or [],
                mags=project.mags or [],
                retailers=project.retailers or [],
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,
                total_scenarios=len(dashboard_scenarios),
                scenarios=dashboard_scenarios,
            )
        )

    return DashboardResponse(
        user_id=cleaned_user_id,
        total_projects=len(dashboard_projects),
        projects=dashboard_projects,
    )