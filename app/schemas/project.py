"""Pydantic schemas for project APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectBase(BaseModel):
    """Common project fields."""

    project_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    markets: list[str] = Field(
        default_factory=list,
    )

    mags: list[str] = Field(
        default_factory=list,
    )

    retailers: list[str] = Field(
        default_factory=list,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "project_name",
        "description",
        mode="before",
    )
    @classmethod
    def trim_text(
        cls,
        value: str | None,
    ) -> str | None:
        """Trim surrounding whitespace from text fields."""

        if isinstance(value, str):
            value = value.strip()

        return value

    @field_validator(
        "markets",
        "mags",
        "retailers",
        mode="before",
    )
    @classmethod
    def clean_list_values(
        cls,
        value: list[str] | None,
    ) -> list[str]:
        """Trim list values and remove duplicates."""

        if not value:
            return []

        cleaned_values: list[str] = []

        for item in value:
            cleaned_item = str(item).strip()

            if (
                cleaned_item
                and cleaned_item not in cleaned_values
            ):
                cleaned_values.append(
                    cleaned_item
                )

        return cleaned_values


class ProjectCreate(ProjectBase):
    """Request schema for creating a project."""

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    @field_validator(
        "user_id",
        mode="before",
    )
    @classmethod
    def trim_user_id(
        cls,
        value: str,
    ) -> str:
        """Trim the user ID."""

        return str(value).strip()


class ProjectUpdate(BaseModel):
    """Request schema for updating a project."""

    project_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    markets: list[str] | None = None
    mags: list[str] | None = None
    retailers: list[str] | None = None

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "project_name",
        "description",
        mode="before",
    )
    @classmethod
    def trim_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        """Trim optional text fields."""

        if isinstance(value, str):
            value = value.strip()

        return value

    @field_validator(
        "markets",
        "mags",
        "retailers",
        mode="before",
    )
    @classmethod
    def clean_optional_lists(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        """Trim optional list values and remove duplicates."""

        if value is None:
            return None

        cleaned_values: list[str] = []

        for item in value:
            cleaned_item = str(item).strip()

            if (
                cleaned_item
                and cleaned_item not in cleaned_values
            ):
                cleaned_values.append(
                    cleaned_item
                )

        return cleaned_values


class ProjectResponse(ProjectBase):
    """Response schema for a project."""

    project_id: str
    user_id: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ProjectListResponse(BaseModel):
    """Response schema for listing projects."""

    total: int
    projects: list[ProjectResponse]