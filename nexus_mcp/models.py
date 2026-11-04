from typing import Any

from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    available: bool
    status_code: int
    auth_valid: bool | None
    auth_error: str | None = None


class Repository(BaseModel):
    name: str
    format: str
    type: str
    online: bool
    url: str | None = None


class Component(BaseModel):
    id: str
    repository: str
    format: str
    group: str | None = None
    name: str
    version: str | None = None
    assets: list[dict[str, Any]] = Field(default_factory=list)


class Asset(BaseModel):
    id: str
    repository: str
    format: str
    name: str
    path: str
    size: int | None = None
    content_type: str | None = None
    last_modified: str | None = None
    last_downloaded: str | None = None


class CleanupPolicy(BaseModel):
    name: str
    notes: str | None = None
    format: str
    mode: str
    criteria: dict[str, Any]


# Tool input models


class SearchComponentsInput(BaseModel):
    repository: str | None = None
    format: str | None = None
    group: str | None = None
    name: str | None = None
    version: str | None = None
    keyword: str | None = None
    continuation_token: str | None = None


class UploadComponentInput(BaseModel):
    repository: str
    format: str
    file_path: str | None = None
    file_base64: str | None = None
    filename: str | None = None
    group_id: str | None = None
    artifact_id: str | None = None
    version: str | None = None
    packaging: str | None = None


class DownloadComponentInput(BaseModel):
    repository: str
    name: str
    version: str | None = None
    group: str | None = None
    format: str | None = None
    save_dir: str | None = None


class LatestArtifactsInput(BaseModel):
    repository: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class DownloadAssetInput(BaseModel):
    asset_id: str
    save_path: str | None = None
    max_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)


class ComponentVersionsInput(BaseModel):
    repository: str
    name: str
    group: str | None = None
    format: str | None = None


class LatestReleaseInput(BaseModel):
    repository: str
    name: str | None = None
    group: str | None = None
    format: str | None = None
    include_snapshots: bool = False


class DependencySnippetInput(BaseModel):
    repository: str
    name: str | None = None
    group: str | None = None
    version: str | None = None
    format: str | None = None
    build_tool: str | None = None


class ArtifactAgeReportInput(BaseModel):
    repository: str
    name: str | None = None
    group: str | None = None
    format: str | None = None
    stale_after_days: int = Field(default=90, ge=1, le=3650)
    limit: int = Field(default=50, ge=1, le=200)


class NexusInfoInput(BaseModel):
    query: str | None = None


class CheckArtifactExistsInput(BaseModel):
    repository: str
    name: str
    version: str | None = None
    group: str | None = None
    format: str | None = None


class GetDownloadUrlInput(BaseModel):
    asset_id: str | None = None
    repository: str | None = None
    name: str | None = None
    version: str | None = None
    group: str | None = None
    format: str | None = None


class RepositoryOwnerInput(BaseModel):
    repository: str = Field(..., min_length=1)
