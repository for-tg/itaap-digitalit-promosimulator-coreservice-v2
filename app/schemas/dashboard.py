"""Pydantic schemas for dashboard APIs."""

from datetime import datetime

from pydantic import BaseModel


class DashboardScenarioResponse(BaseModel):
    """Scenario summary shown on the dashboard."""

    scenario_id: str
    scenario_name: str
    status: str
    has_config: bool
    has_optimization_result: bool
    created_at: datetime
    updated_at: datetime


class DashboardProjectResponse(BaseModel):
    """Project summary with its scenarios."""

    project_id: str
    project_name: str
    markets: list[str]
    mags: list[str]
    retailers: list[str]
    description: str | None
    created_at: datetime
    updated_at: datetime
    total_scenarios: int
    scenarios: list[DashboardScenarioResponse]


class DashboardResponse(BaseModel):
    """Dashboard response for one user."""

    user_id: str
    total_projects: int
    projects: list[DashboardProjectResponse]