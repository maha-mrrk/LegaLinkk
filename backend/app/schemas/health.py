"""Health-check response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response returned by the ``/health`` endpoint."""

    status: str = Field(description="Overall service status", examples=["ok"])
    app_name: str = Field(description="Application name")
    version: str = Field(description="Application version")
    environment: str = Field(description="Current runtime environment")
    timestamp: datetime = Field(description="UTC timestamp of the health check")
    database: str = Field(description="Database connectivity status", examples=["connected"])
