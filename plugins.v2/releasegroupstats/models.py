"""Explicit JSON contracts for authenticated plugin APIs."""
from typing import List, Literal
from pydantic import BaseModel, Field


class ScanStatus(BaseModel):
    """Current task state, independent of the last successful snapshot."""
    enabled: bool
    running: bool
    state: str
    checked_files: int = 0
    video_files: int = 0
    error_count: int = 0
    message: str = ''
    warnings: List[str] = Field(default_factory=list)
    last_scan_time: str = ''


class StatusResponse(BaseModel):
    """Stable response envelope for task controls and polling."""
    success: bool = True
    message: str = ''
    data: ScanStatus


class RankingView(BaseModel):
    """Validated native table sorting and pagination request."""
    sort: Literal['name', 'count', 'bytes'] = 'count'
    descending: bool = True
    page: int = Field(default=1, ge=1)
