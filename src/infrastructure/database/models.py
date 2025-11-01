"""
Database Models - Pydantic models for database entities.

Location: src/infrastructure/database/models.py

These models represent data structures from the PostgreSQL database.
Following Clean Architecture, they are in the Infrastructure layer
and can be converted to/from Domain models.
"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class CandidateDB(BaseModel):
    """
    Database model for candidate entity.

    Maps to: candidate table
    """
    id: str = Field(..., description="Candidate ID (e.g., 'C01')")
    name: str
    surname: str
    email: EmailStr
    phone: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobDB(BaseModel):
    """
    Database model for job entity.

    Maps to: jobs table
    """
    id: str = Field(..., description="Job ID (e.g., 'J001')")
    title: str
    description: str
    requirements: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CandidateApplicationDB(BaseModel):
    """
    Database model for candidate application.

    Maps to: candidate_applications table
    """
    candidate_id: str
    job_id: str
    cv_filename: str
    cv_content: Optional[str] = None
    application_date: Optional[datetime] = None
    status: Optional[str] = "pending"

    class Config:
        from_attributes = True


class UserDataByEmail(BaseModel):
    """
    Aggregated view model for user data retrieval by email.

    Maps to: candidate_applications_view (database view)

    This combines data from candidate, job, and application tables.
    """
    name: str
    surname: str
    cv_content: Optional[str] = None
    jobdescription: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None

    @classmethod
    def from_db_row(cls, row: dict) -> "UserDataByEmail":
        """
        Create instance from database row.

        Args:
            row: Dictionary from database query (RealDictRow)

        Returns:
            UserDataByEmail instance
        """
        return cls(
            name=row.get("name", ""),
            surname=row.get("surname", ""),
            cv_content=row.get("cv_content"),
            jobdescription=row.get("jobdescription"),
            email=row.get("email"),
            phone=row.get("phone"),
            candidate_id=row.get("candidate_id"),
            job_id=row.get("job_id"),
        )