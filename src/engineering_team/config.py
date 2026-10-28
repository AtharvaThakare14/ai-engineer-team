"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Switch Server Settings
    switch_server_url: str = Field(default="http://localhost:8000", description="Base URL of Switch API bridge")
    switch_api_key: str = Field(default="", description="Bearer API key for the registered agent")
    switch_agent_id: str = Field(default="", description="Registered Switch Agent ID")
    switch_registration_token: str = Field(default="", description="Bootstrap token used for initial registration")
    switch_default_room_id: str = Field(default="room_default", description="Default Switch Room ID")

    # Mattermost Settings
    mattermost_url: str = Field(default="http://localhost:8065", description="Mattermost server URL")
    mattermost_team: str = Field(default="engineering", description="Mattermost team slug")
    mattermost_admin_user: str = Field(default="admin", description="Admin username for bot management")
    mattermost_admin_password: str = Field(default="", description="Admin password")
    mattermost_bot_token: str = Field(default="", description="Direct Mattermost bot token if used")

    # Repository & Security Paths
    target_repo_path: Path = Field(default=Path("./sample_repo"), description="Path to the repository being engineered")
    allowed_repo_paths: List[Path] = Field(
        default_factory=lambda: [Path("./sample_repo").resolve(), Path(".").resolve()],
        description="Whitelisted directories for file operations"
    )

    # Safety Controls
    human_approval_required: bool = Field(default=True, description="Enforce human approval before writing files")
    auto_run_tests: bool = Field(default=True, description="Run pytest automatically after code edits")

    # App & Logging
    app_host: str = Field(default="0.0.0.0", description="FastAPI host")
    app_port: int = Field(default=8082, description="FastAPI port")
    log_level: str = Field(default="INFO", description="Log level")

    @field_validator("target_repo_path", mode="after")
    @classmethod
    def resolve_target_path(cls, v: Path) -> Path:
        return v.resolve()


def get_settings() -> Settings:
    """Return an instantiated Settings object."""
    return Settings()
