"""
Pydantic models for API request/response schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# ============================================
# Request Models
# ============================================

class MemoryRetrievalRequest(BaseModel):
    """Request model for memory retrieval"""
    query: str = Field(..., description="Natural language query to search user's personal data", example="emails from John about project deadline")
    mode: Literal["rag", "mixed", "react"] = Field(default="rag", description="Retrieval mode: 'rag' (fast), 'mixed' (flexible), or 'react' (reasoning)")


# ============================================
# Response Models
# ============================================

class HealthResponse(BaseModel):
    """Simple health check response"""
    status: str = Field(..., description="Service status", example="ok")


class MonitoringStats(BaseModel):
    """Monitoring statistics for a time range"""
    total_requests: int = Field(..., description="Total number of requests")
    total_errors: int = Field(..., description="Total number of errors")
    total_retries: int = Field(..., description="Total number of retries")


class TimelinePoint(BaseModel):
    """Single point in timeline data"""
    timestamp: str = Field(..., description="ISO timestamp")
    requests: int = Field(..., description="Number of requests")
    errors: int = Field(..., description="Number of errors")


class MonitoringData(BaseModel):
    """Monitoring data structure"""
    risk_level: int = Field(..., description="Risk level (0-100)", ge=0, le=100)
    risk_reason: str = Field(..., description="Reason for risk level")
    stats: Dict[str, MonitoringStats] = Field(..., description="Statistics by time range")
    timeline: Dict[str, List[TimelinePoint]] = Field(..., description="Timeline data for graphing")


class HealthStatusResponse(BaseModel):
    """Detailed health status response"""
    message: str = Field(..., description="Service message")
    status: str = Field(..., description="Service status")
    monitoring: MonitoringData = Field(..., description="Monitoring data")


class EmailReference(BaseModel):
    """Email reference data"""
    type: Literal["email"] = Field(..., description="Reference type")
    id: str = Field(..., description="Email ID")
    user_id: str = Field(..., description="User UUID")
    thread_id: Optional[str] = Field(None, description="Thread ID")
    body: str = Field(..., description="Email body content")
    subject: str = Field(..., description="Email subject")
    from_user: str = Field(..., description="Sender email address", alias="from")
    to_user: str = Field(..., description="Recipient email address", alias="to")
    cc: Optional[str] = Field(None, description="CC recipients")
    bcc: Optional[str] = Field(None, description="BCC recipients")
    date: Optional[str] = Field(None, description="Email date (ISO format)")


class ScheduleReference(BaseModel):
    """Calendar event reference data"""
    type: Literal["schedule"] = Field(..., description="Reference type")
    id: str = Field(..., description="Event ID")
    user_id: str = Field(..., description="User UUID")
    summary: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    start_time: Optional[str] = Field(None, description="Start time (ISO format)")
    end_time: Optional[str] = Field(None, description="End time (ISO format)")
    creator_email: Optional[str] = Field(None, description="Creator email")
    organizer_email: Optional[str] = Field(None, description="Organizer email")


class FileReference(BaseModel):
    """File reference data"""
    type: Literal["file"] = Field(..., description="Reference type")
    id: str = Field(..., description="File ID")
    user_id: str = Field(..., description="User UUID")
    name: str = Field(..., description="File name")
    path: str = Field(..., description="File path in Drive")
    mime_type: str = Field(..., description="MIME type")
    size: Optional[int] = Field(None, description="File size in bytes")
    modified_time: Optional[str] = Field(None, description="Last modified time")
    summary: Optional[str] = Field(None, description="File content summary")


class AttachmentReference(BaseModel):
    """Email attachment reference data"""
    type: Literal["attachment"] = Field(..., description="Reference type")
    id: str = Field(..., description="Attachment ID")
    user_id: str = Field(..., description="User UUID")
    email_id: str = Field(..., description="Parent email ID")
    filename: str = Field(..., description="Attachment filename")
    mime_type: str = Field(..., description="MIME type")
    size: Optional[int] = Field(None, description="File size in bytes")
    summary: Optional[str] = Field(None, description="Attachment content summary")


class MemoryRetrievalResponse(BaseModel):
    """Response model for memory retrieval"""
    content: str = Field(..., description="Third-person context summary", example="User has 2 emails about project deadline from John. Meeting scheduled Dec 5 at 2PM.")
    references: List[Dict[str, Any]] = Field(..., description="List of reference objects (emails, schedules, files, attachments)")
    process: Optional[List[Dict[str, Any]]] = Field(None, description="Processing steps (only when VERBOSE_OUTPUT=true)")


class AuthStatusResponse(BaseModel):
    """Authentication status response"""
    authenticated: bool = Field(..., description="Whether user is authenticated")
    user: Optional[Dict[str, Any]] = Field(None, description="User information if authenticated")
    status: Optional[str] = Field(None, description="User initialization status: 'pending', 'processing', 'active', 'error'")
    init_phase: Optional[str] = Field(None, description="Current initialization phase")
    init_progress: Optional[int] = Field(None, description="Initialization progress (0-100)", ge=0, le=100)


class UserStatusResponse(BaseModel):
    """User status response"""
    user_id: str = Field(..., description="User UUID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User name")
    status: str = Field(..., description="User status: 'processing', 'active', 'error'")
    progress: int = Field(..., description="Initialization progress (0-100)", ge=0, le=100)
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")


class SuccessResponse(BaseModel):
    """Generic success response"""
    message: str = Field(..., description="Success message")
